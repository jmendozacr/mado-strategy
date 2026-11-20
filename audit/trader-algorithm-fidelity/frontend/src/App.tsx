import { useEffect, useRef, useState } from 'react';
import { AnnotationPanel } from './AnnotationPanel.tsx';
import { Chart } from './Chart.tsx';
import { DecisionForm } from './DecisionForm.tsx';
import {
  annotationPayload, barsThrough, decisionPayload, earliestPannableMs, formatClock, mergeOlderBars, utcMs,
  type AnnotationDraft, type Bar, type CaseSummary, type DecisionFields, type HistoricalContext,
  type PriceLevel, type Replay,
} from './model.ts';

const initialSpan = 24 * 60 * 60 * 1000;

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { error?: string };
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return await response.json() as T;
}

export function App() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [caseId, setCaseId] = useState('');
  const [replay, setReplay] = useState<Replay | null>(null);
  const [viewEnd, setViewEnd] = useState<number | null>(null);
  const [span, setSpan] = useState(initialSpan);
  const [manualPrice, setManualPrice] = useState('');
  const [notice, setNotice] = useState<{ message: string; error: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [zone, setZone] = useState<'ny' | 'utc'>('ny');
  const [extraH4, setExtraH4] = useState<Bar[]>([]);
  const [extraDaily, setExtraDaily] = useState<Bar[]>([]);
  const [contextExhausted, setContextExhausted] = useState({ h4: false, daily: false });
  const [armedTimeframe, setArmedTimeframe] = useState<AnnotationDraft['timeframe'] | null>(null);
  const [annotationDraft, setAnnotationDraft] = useState<AnnotationDraft>({ annotation_type: 'key_level', timeframe: 'h4' });
  const [annotationError, setAnnotationError] = useState<string | null>(null);
  const busyRef = useRef(false);
  const playTimer = useRef<number | null>(null);
  const selectionToken = useRef(0);
  const oldestFetched = useRef<{ h4: string | null; daily: string | null }>({ h4: null, daily: null });
  const fetchingContext = useRef<{ h4: boolean; daily: boolean }>({ h4: false, daily: false });

  function stopPlayback() {
    if (playTimer.current !== null) window.clearInterval(playTimer.current);
    playTimer.current = null;
    setPlaying(false);
  }

  async function selectCase(id: string, available = cases) {
    stopPlayback();
    const token = ++selectionToken.current;
    setCaseId(id);
    setReplay(null);
    setViewEnd(null);
    setNotice(null);
    setExtraH4([]);
    setExtraDaily([]);
    setContextExhausted({ h4: false, daily: false });
    setArmedTimeframe(null);
    setAnnotationError(null);
    oldestFetched.current = { h4: null, daily: null };
    fetchingContext.current = { h4: false, daily: false };
    if (!id || available.find(item => item.id === id)?.status === 'not_started') return;
    try {
      const snapshot = await request<Replay>(`/api/cases/${encodeURIComponent(id)}/replay`);
      if (selectionToken.current === token) setReplay(snapshot);
    } catch (error) {
      if (selectionToken.current === token) setNotice({ message: String(error), error: true });
    }
  }

  useEffect(() => {
    void request<CaseSummary[]>('/api/cases').then(items => {
      setCases(items);
      if (items.length) void selectCase(items[0].id, items);
    }).catch(error => setNotice({ message: String(error), error: true }));
    return () => {
      if (playTimer.current !== null) window.clearInterval(playTimer.current);
    };
  }, []);

  async function action(name: 'start' | 'next' | 'finish') {
    if (!caseId || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setNotice(null);
    try {
      if (name === 'finish') {
        const result = await request<{ status: CaseSummary['status'] }>(`/api/cases/${encodeURIComponent(caseId)}/finish`, 'POST');
        stopPlayback();
        setReplay(current => current && { ...current, case: { ...current.case, status: result.status } });
        setNotice({ message: 'Case finished. Your recorded decisions remain available for review.', error: false });
      } else {
        const result = await request<Replay>(`/api/cases/${encodeURIComponent(caseId)}/${name}`, 'POST');
        setReplay(result);
        setViewEnd(utcMs(result.cursor_utc));
      }
      setCases(await request<CaseSummary[]>('/api/cases'));
    } catch (error) {
      stopPlayback();
      setNotice({ message: String(error), error: true });
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  async function saveDecision(fields: DecisionFields): Promise<boolean> {
    if (!replay || busyRef.current) return false;
    stopPlayback();
    busyRef.current = true;
    setBusy(true);
    try {
      const payload = decisionPayload(fields, replay.cursor_utc);
      await request(`/api/cases/${encodeURIComponent(caseId)}/decisions`, 'POST', payload);
      setReplay(await request<Replay>(`/api/cases/${encodeURIComponent(caseId)}/replay`));
      setNotice({ message: 'Decision saved as a new immutable record.', error: false });
      return true;
    } catch (error) {
      setNotice({ message: String(error), error: true });
      return false;
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  function pan(delta: number) {
    const cursor = replay ? utcMs(replay.cursor_utc) : Date.now();
    const fallback = replay?.m15.length ? utcMs(replay.m15[0].time) : cursor - span;
    // H4/Daily can keep paging back toward the real dataset start; M15 keeps its
    // original short execution window (Problem A) -- the pan floor is whichever
    // of the three currently-loaded series reaches furthest back.
    const earliest = earliestPannableMs({ h4: h4All, daily: dailyAll, m15: replay?.m15 ?? [] }, fallback);
    setViewEnd(previous => Math.min(cursor, Math.max(earliest + span * 0.2, (previous ?? cursor) - delta)));
  }

  function zoom(factor: number) {
    setSpan(previous => Math.min(7 * initialSpan, Math.max(4 * 60 * 60 * 1000, previous * factor)));
  }

  async function fetchOlderContext(timeframe: 'h4' | 'daily') {
    if (!replay || !caseId || fetchingContext.current[timeframe] || contextExhausted[timeframe]) return;
    const token = selectionToken.current;
    const requestCaseId = caseId;
    fetchingContext.current[timeframe] = true;
    try {
      const before = oldestFetched.current[timeframe] ?? replay.cursor_utc;
      const page = await request<HistoricalContext>(
        `/api/cases/${encodeURIComponent(requestCaseId)}/context?timeframe=${timeframe}&before=${encodeURIComponent(before)}&page_days=14`);
      if (selectionToken.current !== token) return; // the user switched case while this was in flight; discard
      if (page.candles.length) {
        if (timeframe === 'h4') setExtraH4(previous => mergeOlderBars(previous, page.candles));
        else setExtraDaily(previous => mergeOlderBars(previous, page.candles));
      }
      oldestFetched.current[timeframe] = page.next_before;
      if (page.exhausted) setContextExhausted(previous => ({ ...previous, [timeframe]: true }));
    } catch {
      // Leave state as-is; panning further will retry.
    } finally {
      if (selectionToken.current === token) fetchingContext.current[timeframe] = false;
    }
  }

  function selectCandle(timeframe: AnnotationDraft['timeframe'], bar: Bar) {
    if (armedTimeframe !== timeframe) return;
    setAnnotationDraft(previous => ({ ...previous, timeframe, source_time: bar.time }));
    setArmedTimeframe(null);
  }

  function armAnnotationSelection() {
    setArmedTimeframe(annotationDraft.timeframe);
  }

  async function saveAnnotation() {
    if (!replay || busyRef.current) return;
    setAnnotationError(null);
    let payload;
    try {
      payload = annotationPayload(annotationDraft);
    } catch (error) {
      setAnnotationError(error instanceof Error ? error.message : String(error));
      return;
    }
    busyRef.current = true;
    setBusy(true);
    try {
      await request(`/api/cases/${encodeURIComponent(caseId)}/annotations`, 'POST', payload);
      setReplay(await request<Replay>(`/api/cases/${encodeURIComponent(caseId)}/replay`));
      setAnnotationDraft({ annotation_type: annotationDraft.annotation_type, timeframe: annotationDraft.timeframe });
    } catch (error) {
      setAnnotationError(String(error));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  const selected = cases.find(item => item.id === caseId);
  const item = replay?.case ?? selected;
  const status = item?.status;
  const active = status === 'in_progress';
  const cursor = replay ? utcMs(replay.cursor_utc) : Date.now();
  const end = Math.min(viewEnd ?? cursor, cursor);
  const h4All = replay ? mergeOlderBars(barsThrough(replay.h4, replay.cursor_utc), extraH4) : [];
  const dailyAll = replay ? barsThrough(extraDaily, replay.cursor_utc) : [];
  const markers: PriceLevel[] = [...(replay?.reference_levels ?? [])];
  if (manualPrice && Number.isFinite(Number(manualPrice))) markers.push({ price: Number(manualPrice), label: 'Your level' });
  for (const annotation of replay?.annotations ?? []) {
    if (annotation.price != null) {
      markers.push({ price: annotation.price, label: `${annotation.annotation_type}${annotation.documented_level_type ? ` · ${annotation.documented_level_type}` : ''}` });
    }
  }

  useEffect(() => {
    if (!replay || !active) return;
    const start = end - span;
    const h4Earliest = h4All.length ? utcMs(h4All[0].time) : Infinity;
    const dailyEarliest = dailyAll.length ? utcMs(dailyAll[0].time) : Infinity;
    if (!contextExhausted.h4 && start < h4Earliest + span * 0.5) void fetchOlderContext('h4');
    if (!contextExhausted.daily && start < dailyEarliest + span * 0.5) void fetchOlderContext('daily');
    // h4All/dailyAll/fetchOlderContext are derived from replay/extraH4/extraDaily each render; re-running on those
    // directly would refetch mid-flight, so this effect only reacts to the view window and case identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [end, span, replay?.cursor_utc, caseId, active]);

  return <div className="app-shell">
    <header className="app-header"><div className="brand"><div className="brand-mark">CR</div><div><span className="eyebrow">LOCAL RESEARCH WORKSPACE</span><h1>CRT Fidelity Audit</h1></div></div>
      <div className="header-tools">
        <div className="zone-toggle" role="group" aria-label="Time reference">
          <button type="button" id="zone-ny" className={zone === 'ny' ? 'button-primary' : ''} onClick={() => setZone('ny')}>New York</button>
          <button type="button" id="zone-utc" className={zone === 'utc' ? 'button-primary' : ''} onClick={() => setZone('utc')}>UTC</button>
        </div>
        <div className="header-status"><span className="status-dot" /> Human review · Stage 1</div>
      </div></header>
    <main>
      <section className="intro"><div><span className="eyebrow">BLIND HISTORICAL REPLAY</span><h2>Read the market, one closed candle at a time.</h2><p>Record your reasoning before any algorithm comparison is available.</p></div><span className="privacy-chip">Future data locked</span></section>
      <section className="case-toolbar"><label className="case-picker"><span>Historical case</span><select id="case-select" value={caseId} disabled={busy} onChange={event => void selectCase(event.target.value)}>{cases.map(item => <option key={item.id} value={item.id}>{item.pair} · {item.date_ny} · {item.model.toUpperCase()} · {item.status}</option>)}</select></label><div className="case-metadata"><div><span>PAIR</span><strong id="pair">{item?.pair ?? '—'}</strong></div><div><span>MODEL</span><strong id="model">{item?.model.toUpperCase() ?? '—'}</strong></div><div><span>DATE · NY</span><strong id="date-ny">{item?.date_ny ?? '—'}</strong></div><div><span>REPLAY TIME · {zone.toUpperCase()}</span><strong id="cursor-primary">{replay ? formatClock(replay.cursor_utc, zone) : '—'}</strong></div><div><span>UTC</span><strong id="cursor-utc">{replay?.cursor_utc ?? '—'}</strong></div></div></section>
      {notice && <div id="notice" className={`notice ${notice.error ? 'error' : 'success'}`} role="status">{notice.message}</div>}
      {replay?.case.integrity === 'non_evaluable' && <div id="integrity-notice" className="notice error">This case has an incomplete data bucket. Record the data gap, and do not assess strategy fidelity from this case.</div>}
      <section className="replay-controls" aria-label="Replay controls"><div className="control-group">
        <button id="start" className="button-primary" type="button" disabled={busy || status !== 'not_started'} onClick={() => void action('start')}>Start case</button>
        <button id="next" type="button" disabled={busy || !active} onClick={() => void action('next')}>Next M15 candle →</button>
        <button id="play" type="button" disabled={busy || !active || playing} onClick={() => { if (playTimer.current === null) playTimer.current = window.setInterval(() => void action('next'), 1100); setPlaying(true); }}>Play</button>
        <button id="pause" type="button" disabled={!playing} onClick={stopPlayback}>Pause</button>
        <button id="finish" type="button" disabled={busy || !active || !replay?.case.can_finish} onClick={() => void action('finish')}>Finish case</button>
      </div><div className="replay-caption" id="last-m15">{replay ? `Last closed M15 open · ${replay.last_available_m15 ?? 'none'} UTC` : 'Start a case to reveal the first closed candle'}</div></section>
      <div className="workspace-grid"><div className="charts-column">
        <Chart id="h4" title="H4 · NY feeder" subtitle={`NY-anchored grid · key opens 9PM / 1AM / 5AM / 9AM · ${replay?.h4.at(-1)?.complete === false ? 'current candle forming' : 'closed candles'}${contextExhausted.h4 ? ' · full history loaded' : ''}`}
          bars={h4All} markers={markers} end={end} span={span} zone={zone} selecting={armedTimeframe === 'h4'}
          onPan={pan} onZoom={zoom} onSelectCandle={bar => selectCandle('h4', bar)} />
        <Chart id="daily" title="Daily · 17:00 NY (engineering convention)" subtitle={`Reconstructed from M15 only · not the broker's native Daily${contextExhausted.daily ? ' · full history loaded' : ''}`}
          bars={dailyAll} markers={markers} end={end} span={span} zone={zone} selecting={armedTimeframe === 'daily'}
          onPan={pan} onZoom={zoom} onSelectCandle={bar => selectCandle('daily', bar)} />
        <Chart id="m15" title="M15 · execution" subtitle="A candle enters the chart only after its close"
          bars={replay ? barsThrough(replay.m15, replay.cursor_utc) : []} markers={markers} end={end} span={span} zone={zone} selecting={armedTimeframe === 'm15'}
          onPan={pan} onZoom={zoom} onSelectCandle={bar => selectCandle('m15', bar)} />
        <div className="manual-level"><label htmlFor="manual-price">Your price marker</label><input id="manual-price" type="number" step="any" placeholder="Enter a level to inspect on all charts" value={manualPrice} onChange={event => setManualPrice(event.target.value)} /><button id="clear-price" type="button" onClick={() => setManualPrice('')}>Clear</button></div>
      </div>
      <div className="side-column">
        <DecisionForm key={caseId} active={active} busy={busy} integrity={replay?.case.integrity ?? 'evaluable'} decisions={replay?.decisions ?? []} onSave={saveDecision} />
        <AnnotationPanel active={active} busy={busy} draft={annotationDraft} armed={armedTimeframe === annotationDraft.timeframe}
          annotations={replay?.annotations ?? []} error={annotationError} onChange={setAnnotationDraft}
          onArm={armAnnotationSelection} onSave={() => void saveAnnotation()} />
      </div>
      </div>
    </main>
  </div>;
}
