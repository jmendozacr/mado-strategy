//+------------------------------------------------------------------+
//| Mado_1am9am_Backtest.mq5                                        |
//| EURUSD "1AM+9AM diversified" recipe, ported for MT5 Strategy     |
//| Tester. See mt5/README.md for the rule list and known            |
//| approximations vs. the Python recipe (same recipe as the         |
//| tradingview/mado_1am9am_backtest.pine port, same caveats).       |
//| REQUIRES a HEDGING-type test account: the 1AM and 9AM models can |
//| each hold their own open EURUSD position at the same time.       |
//+------------------------------------------------------------------+
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double RiskPct        = 1.0;     // risk % per trade, fixed, non-compounding
input double InitBalance    = 10000.0; // fixed balance used for sizing (matches scanner/main.py)
input double SLFloorPrice   = 0.0006;  // EURUSD SL floor, price units (~6 pips)
input double SLBufferAtrMul = 0.3;     // structural SL buffer, x ATR14 (M15, snapshotted at anchor)
input double MinRR          = 2.0;     // minimum R:R to accept a signal
input double FVGMinAtrMul   = 0.1;     // min H4 FVG size, x ATR14 (H4)
input double PartialFrac    = 0.5;     // partial-exit fraction at entry-to-target midpoint
input int    MaxLookback    = 20;      // M15 lookback for anchor / confirm / retest
input int    BrokerUTCOffsetHours = 0; // set if this broker's quote time is not UTC

#define MAGIC_1AM 190901
#define MAGIC_9AM 190909

int atrH4Handle, atrM15Handle;

struct FVGZone { double top; double bottom; int dir; datetime origin; }; // dir: 1=bull(below), -1=bear(above)
FVGZone fvgZones[];

struct ModelState
{
   bool   pendActive;  int pendDir;  double pendTP;
   int    stage;        // 0 idle/searching-anchor, 2 confirm, 3 retest, 4 entry
   double protectedLvl, bodyHi, bodyLo, retestOpen, runExt, swingSnap, atrAnchor;
   bool   inTrade, partialDone;
   ulong  ticket;
   double origVol, entryPx, stopPx, tpPx, partialPx;
};
ModelState m1, m9;

datetime lastM15Time = 0;
datetime lastH4Time  = 0;
bool     haveLastH4  = false, haveH4_2 = false;
double   lastH4H, lastH4L, lastH4C, h4_2H, h4_2L;

//+------------------------------------------------------------------+
int OnInit()
{
   if(Period() != PERIOD_M15)
   {
      Print("Mado_1am9am_Backtest: attach this EA on the M15 timeframe.");
      return INIT_FAILED;
   }
   atrH4Handle  = iATR(_Symbol, PERIOD_H4,  14);
   atrM15Handle = iATR(_Symbol, PERIOD_M15, 14);
   if(atrH4Handle == INVALID_HANDLE || atrM15Handle == INVALID_HANDLE)
      return INIT_FAILED;
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(atrH4Handle);
   IndicatorRelease(atrM15Handle);
}

//+------------------------------------------------------------------+
datetime ToUTC(datetime t) { return t - BrokerUTCOffsetHours * 3600; }

datetime NthSundayOfMonth(int year, int month, int n)
{
   datetime first = StringToTime(StringFormat("%04d.%02d.01 00:00", year, month));
   MqlDateTime dt; TimeToStruct(first, dt);
   int daysToFirstSunday = (7 - dt.day_of_week) % 7;
   int day = 1 + daysToFirstSunday + (n - 1) * 7;
   return StringToTime(StringFormat("%04d.%02d.%02d 00:00", year, month, day));
}

bool IsUSEasternDST(datetime utc)
{
   MqlDateTime dt; TimeToStruct(utc, dt);
   datetime dstStartUTC = NthSundayOfMonth(dt.year, 3,  2) + 2 * 3600 + 5 * 3600; // 2nd Sun Mar 02:00 EST -> UTC
   datetime dstEndUTC   = NthSundayOfMonth(dt.year, 11, 1) + 2 * 3600 + 4 * 3600; // 1st Sun Nov 02:00 EDT -> UTC
   return (utc >= dstStartUTC && utc < dstEndUTC);
}

bool InNYWindow(datetime utc, int startH, int startM, int durMinutes)
{
   int offset = IsUSEasternDST(utc) ? -4 : -5;
   MqlDateTime dt; TimeToStruct(utc + offset * 3600, dt);
   int minsOfDay = dt.hour * 60 + dt.min;
   int startMins = startH * 60 + startM;
   return (minsOfDay >= startMins && minsOfDay < startMins + durMinutes);
}

double HighestHighExcl(int lookback)
{
   double hh = -DBL_MAX;
   for(int k = 2; k <= lookback + 1; k++) { double v = iHigh(_Symbol, PERIOD_M15, k); if(v > hh) hh = v; }
   return hh;
}
double LowestLowExcl(int lookback)
{
   double ll = DBL_MAX;
   for(int k = 2; k <= lookback + 1; k++) { double v = iLow(_Symbol, PERIOD_M15, k); if(v < ll) ll = v; }
   return ll;
}

double GetM15Atr() { double b[]; if(CopyBuffer(atrM15Handle, 0, 1, 1, b) != 1) return 0.0; return b[0]; }
double GetH4Atr()  { double b[]; if(CopyBuffer(atrH4Handle,  0, 1, 1, b) != 1) return 0.0; return b[0]; }

double NormalizeVolume(double v)
{
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   v = MathFloor(v / step) * step;
   if(v < vmin) v = vmin;
   if(v > vmax) v = vmax;
   return v;
}

void PushFVG(double bottom, double top, int dir, datetime origin)
{
   int n = ArraySize(fvgZones);
   ArrayResize(fvgZones, n + 1);
   fvgZones[n].top = top; fvgZones[n].bottom = bottom; fvgZones[n].dir = dir; fvgZones[n].origin = origin;
}

void PruneFVGs(double h4ClosePrice)
{
   FVGZone kept[];
   for(int i = 0; i < ArraySize(fvgZones); i++)
   {
      bool expired = (fvgZones[i].dir == 1  && h4ClosePrice < fvgZones[i].bottom) ||
                     (fvgZones[i].dir == -1 && h4ClosePrice > fvgZones[i].top);
      if(!expired)
      {
         int k = ArraySize(kept);
         ArrayResize(kept, k + 1);
         kept[k] = fvgZones[i];
      }
   }
   ArrayFree(fvgZones);
   ArrayResize(fvgZones, ArraySize(kept));
   for(int i = 0; i < ArraySize(kept); i++) fvgZones[i] = kept[i];
}

//+------------------------------------------------------------------+
// Hand-rolled H4 Turtle Soup + H4 FVG key-level gate. MT5's native H4
// bars for this broker/feed are already UTC-aligned (00/04/08/12/16/20),
// matching the exported CSVs the rest of this repo uses -- see
// BrokerUTCOffsetHours if that is not true for your broker.
void CheckH4Close()
{
   datetime h4t0 = iTime(_Symbol, PERIOD_H4, 0);
   if(h4t0 == lastH4Time) return;
   bool first = (lastH4Time == 0);
   lastH4Time = h4t0;
   if(first) return;

   double h4h = iHigh(_Symbol, PERIOD_H4, 1), h4l = iLow(_Symbol, PERIOD_H4, 1), h4c = iClose(_Symbol, PERIOD_H4, 1);
   datetime h4OpenTime = iTime(_Symbol, PERIOD_H4, 1);
   MqlDateTime dt; TimeToStruct(ToUTC(h4OpenTime), dt);
   int openHourUTC = dt.hour;

   if(haveLastH4 && (openHourUTC == 4 || openHourUTC == 12))
   {
      bool bearishTrig = (h4h > lastH4H && h4c <= lastH4H);
      bool bullishTrig = (h4l < lastH4L && h4c >= lastH4L);
      if(bearishTrig || bullishTrig)
      {
         int    dir     = bearishTrig ? -1 : 1;
         double tp      = bearishTrig ? lastH4L : lastH4H;
         double extreme = bearishTrig ? h4h : h4l;
         bool   gated    = false;
         for(int i = 0; i < ArraySize(fvgZones); i++)
            if(fvgZones[i].origin < h4OpenTime && extreme >= fvgZones[i].bottom && extreme <= fvgZones[i].top)
               gated = true;
         if(gated)
         {
            if(openHourUTC == 4) { m1.pendActive = true; m1.pendDir = dir; m1.pendTP = tp; }
            else                 { m9.pendActive = true; m9.pendDir = dir; m9.pendTP = tp; }
         }
      }
   }

   if(haveH4_2)
   {
      double h4Atr = GetH4Atr();
      if(h4_2H < h4l && (h4l - h4_2H) >= FVGMinAtrMul * h4Atr) PushFVG(h4_2H, h4l, 1,  h4OpenTime);
      if(h4_2L > h4h && (h4_2L - h4h) >= FVGMinAtrMul * h4Atr) PushFVG(h4h, h4_2L, -1, h4OpenTime);
   }
   PruneFVGs(h4c);

   h4_2H = lastH4H; h4_2L = lastH4L; haveH4_2 = haveLastH4;
   lastH4H = h4h; lastH4L = h4l; lastH4C = h4c; haveLastH4 = true;
}

//+------------------------------------------------------------------+
void OpenTrade(ModelState &s, double entryPx, double stopFinal, double tp, ulong magic)
{
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double riskAmount = InitBalance * RiskPct / 100.0;
   double distTicks  = MathAbs(entryPx - stopFinal) / tickSize;
   double lossPerLot = distTicks * tickValue;
   if(lossPerLot <= 0) return;
   double vol = NormalizeVolume(riskAmount / lossPerLot);

   trade.SetExpertMagicNumber(magic);
   bool isBuy = s.pendDir > 0;
   bool ok = isBuy ? trade.Buy(vol, _Symbol, 0.0, stopFinal, tp, magic == MAGIC_1AM ? "1am" : "9am")
                   : trade.Sell(vol, _Symbol, 0.0, stopFinal, tp, magic == MAGIC_1AM ? "1am" : "9am");
   if(!ok) return;

   ulong foundTicket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(PositionSelectByTicket(tk) && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)magic)
      { foundTicket = tk; break; }
   }
   if(foundTicket == 0) return;

   s.ticket       = foundTicket;
   s.origVol      = vol;
   s.entryPx      = PositionGetDouble(POSITION_PRICE_OPEN);
   s.stopPx       = stopFinal;
   s.tpPx         = tp;
   s.partialPx    = (s.entryPx + tp) / 2.0;
   s.inTrade      = true;
   s.partialDone  = false;
}

void ManageOpenTrade(ModelState &s)
{
   if(!s.inTrade) return;
   if(!PositionSelectByTicket(s.ticket)) { s.inTrade = false; return; }

   double curVol = PositionGetDouble(POSITION_VOLUME);
   if(!s.partialDone)
   {
      bool isBuy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      bool reached = isBuy ? (bid >= s.partialPx) : (ask <= s.partialPx);
      if(reached)
      {
         double closeVol = NormalizeVolume(curVol * PartialFrac);
         if(closeVol > 0 && closeVol < curVol)
         {
            trade.PositionClosePartial(s.ticket, closeVol);
            trade.PositionModify(s.ticket, s.entryPx, s.tpPx); // true breakeven on the remainder
            s.partialDone = true;
         }
      }
   }
}

//+------------------------------------------------------------------+
void ProcessModel(ModelState &s, bool inWindow, ulong magic)
{
   if(!s.pendActive) return;
   if(!inWindow) { s.pendActive = false; s.stage = 0; return; }

   double o = iOpen(_Symbol, PERIOD_M15, 1), h = iHigh(_Symbol, PERIOD_M15, 1);
   double l = iLow(_Symbol, PERIOD_M15, 1),  c = iClose(_Symbol, PERIOD_M15, 1);
   int dir = s.pendDir;

   if(s.stage == 0)
   {
      bool anchorBear = dir < 0 && h > HighestHighExcl(MaxLookback);
      bool anchorBull = dir > 0 && l < LowestLowExcl(MaxLookback);
      if(anchorBear || anchorBull)
      {
         s.protectedLvl = dir < 0 ? h : l;
         s.bodyHi = MathMax(o, c); s.bodyLo = MathMin(o, c);
         s.runExt = dir < 0 ? l : h;
         s.atrAnchor = GetM15Atr();
         s.stage = 2;
      }
      return;
   }

   bool invalid = dir < 0 ? (c > s.protectedLvl) : (c < s.protectedLvl);
   if(invalid)
   {
      bool reBear = dir < 0 && h > HighestHighExcl(MaxLookback);
      bool reBull = dir > 0 && l < LowestLowExcl(MaxLookback);
      if(reBear || reBull)
      {
         s.protectedLvl = dir < 0 ? h : l;
         s.bodyHi = MathMax(o, c); s.bodyLo = MathMin(o, c);
         s.runExt = dir < 0 ? l : h;
         s.atrAnchor = GetM15Atr();
         s.stage = 2;
      }
      else { s.pendActive = false; s.stage = 0; }
      return;
   }

   if(s.stage == 2)
   {
      bool engulf = dir < 0 ? (c < s.bodyLo) : (c > s.bodyHi);
      if(engulf) s.stage = 3;
      else s.runExt = dir < 0 ? MathMax(s.runExt, h) : MathMin(s.runExt, l);
   }
   else if(s.stage == 3)
   {
      bool retestHit = (l <= s.bodyHi && h >= s.bodyLo);
      if(retestHit) { s.swingSnap = s.runExt; s.retestOpen = o; s.stage = 4; }
      else s.runExt = dir < 0 ? MathMax(s.runExt, h) : MathMin(s.runExt, l);
   }
   else if(s.stage == 4)
   {
      bool triggered = dir < 0 ? (c < s.retestOpen) : (c > s.retestOpen);
      if(triggered && !s.inTrade)
      {
         double entryPx     = c;
         double structLevel = dir < 0 ? MathMax(s.protectedLvl, s.swingSnap) : MathMin(s.protectedLvl, s.swingSnap);
         double buffer      = SLBufferAtrMul * s.atrAnchor;
         double stopPre     = dir < 0 ? structLevel + buffer : structLevel - buffer;
         double dist        = MathAbs(entryPx - stopPre);
         double stopFinal   = dist >= SLFloorPrice ? stopPre : (dir < 0 ? entryPx + SLFloorPrice : entryPx - SLFloorPrice);
         double rr          = MathAbs(s.pendTP - entryPx) / MathAbs(entryPx - stopFinal);
         if(rr >= MinRR)
            OpenTrade(s, entryPx, stopFinal, s.pendTP, magic);
         s.pendActive = false; s.stage = 0;
      }
   }
}

//+------------------------------------------------------------------+
void OnTick()
{
   ManageOpenTrade(m1);
   ManageOpenTrade(m9);

   datetime t0 = iTime(_Symbol, PERIOD_M15, 0);
   if(t0 == lastM15Time) return;
   bool first = (lastM15Time == 0);
   lastM15Time = t0;
   if(first) return;

   CheckH4Close();

   datetime barUTC = ToUTC(iTime(_Symbol, PERIOD_M15, 1));
   ProcessModel(m1, InNYWindow(barUTC, 2, 0, 120), MAGIC_1AM);
   ProcessModel(m9, InNYWindow(barUTC, 9, 0, 90),  MAGIC_9AM);
}
