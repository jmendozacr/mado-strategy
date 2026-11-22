import { useRef, useState, type PointerEvent, type WheelEvent } from 'react';
import { dictionaries, type Lang } from './i18n.ts';
import { feederLabel, formatClock, utcMs, type Bar, type PriceLevel } from './model.ts';

const PALETTE = {
  dark: { bg: '#0d1724', gridMajor: '#253544', gridMinor: '#1c2c3a', bull: '#48c6a7', bear: '#ef7583', gap: '#9a6b2f', forming: '#f8d18b', marker: '#e8b96b' },
  light: { bg: '#FAFCFE', gridMajor: '#D7E1E8', gridMinor: '#E7EEF3', bull: '#1E8F66', bear: '#C9333F', gap: '#9A6B2F', forming: '#B97A1E', marker: '#B9790E' },
} as const;

type Props = {
  id: 'h4' | 'm15' | 'daily';
  lang: Lang;
  theme: 'dark' | 'light';
  title: string;
  subtitle: string;
  bars: Bar[];
  markers: PriceLevel[];
  end: number;
  span: number;
  zone: 'ny' | 'utc';
  selecting?: boolean;
  onPan: (delta: number) => void;
  onZoom: (factor: number) => void;
  onSelectCandle?: (bar: Bar) => void;
};

export function Chart({ id, lang, theme, title, subtitle, bars, markers, end, span, zone, selecting, onPan, onZoom, onSelectCandle }: Props) {
  const t = dictionaries[lang].chart;
  const palette = PALETTE[theme];
  const [tooltip, setTooltip] = useState(t.hoverHint);
  const dragStart = useRef<number | null>(null);
  const left = 14, right = 80, top = 16, bottom = 30, width = 1000, height = 260;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const start = end - span;
  const visible = bars.filter(bar => utcMs(bar.time) >= start && utcMs(bar.time) <= end);
  const prices = visible.flatMap(bar => [bar.high, bar.low]).concat(markers.map(marker => marker.price));
  const low = prices.length ? Math.min(...prices) : 0;
  const high = prices.length ? Math.max(...prices) : 1;
  const padding = Math.max((high - low) * 0.12, high > 10 ? 0.01 : 0.0002);
  const floor = low - padding, ceiling = high + padding;
  const x = (time: string) => left + ((utcMs(time) - start) / span) * plotWidth;
  const y = (price: number) => top + ((ceiling - price) / (ceiling - floor)) * plotHeight;
  const candleWidth = Math.max(3, Math.min(35, (visible.length > 1 ? x(visible[1].time) - x(visible[0].time) : plotWidth / 20) * 0.58));

  function endDrag(event: PointerEvent<SVGSVGElement>) {
    if (dragStart.current === null) return;
    const movedPx = event.clientX - dragStart.current;
    onPan(movedPx / event.currentTarget.clientWidth * span);
    // setPointerCapture (below) redirects the native click event's target to this
    // <svg>, so per-candle onClick handlers never fire. A near-zero-movement
    // pointerup is a tap/click: resolve the nearest visible candle ourselves from
    // the release position instead of relying on candle-level click handlers.
    if (Math.abs(movedPx) < 4 && onSelectCandle && visible.length) {
      const box = event.currentTarget.getBoundingClientRect();
      const svgX = (event.clientX - box.left) / box.width * width;
      const targetTime = start + ((svgX - left) / plotWidth) * span;
      const nearest = visible.reduce((best, bar) => {
        const diff = Math.abs(utcMs(bar.time) - targetTime);
        return diff < best.diff ? { bar, diff } : best;
      }, { bar: visible[0], diff: Infinity });
      onSelectCandle(nearest.bar);
    }
    dragStart.current = null;
  }

  function wheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    onZoom(event.deltaY < 0 ? 0.8 : 1.25);
  }

  const tf = id.toUpperCase();

  return <section className="chart-card" aria-label={`${title} candlestick chart`}>
    <div className="chart-heading"><div><h2>{title}</h2><span>{subtitle}</span></div><div className="chart-tools">
      <button type="button" data-action="pan-earlier" data-chart={id} aria-label={t.panEarlier(tf)} title={t.panEarlier(tf)} onClick={() => onPan(span * 0.3)}>←</button>
      <button type="button" data-action="zoom-in" data-chart={id} aria-label={t.zoomIn(tf)} title={t.zoomIn(tf)} onClick={() => onZoom(0.7)}>+</button>
      <button type="button" data-action="zoom-out" data-chart={id} aria-label={t.zoomOut(tf)} title={t.zoomOut(tf)} onClick={() => onZoom(1.4)}>−</button>
      <button type="button" data-action="pan-later" data-chart={id} aria-label={t.panLater(tf)} title={t.panLater(tf)} onClick={() => onPan(-span * 0.3)}>→</button>
    </div></div>
    <div className="chart-surface">
      <svg id={`${id}-chart`} viewBox="0 0 1000 260" role="img" aria-label={t.availableCandles(tf)}
        onWheel={wheel} onPointerDown={event => { dragStart.current = event.clientX; event.currentTarget.setPointerCapture(event.pointerId); }}
        onPointerUp={endDrag} onPointerCancel={() => { dragStart.current = null; }}>
        <rect x="0" y="0" width={width} height={height} fill={palette.bg} />
        {Array.from({ length: 5 }, (_, index) => {
          const price = floor + (ceiling - floor) * index / 4;
          return <g key={`price-${index}`}>
            <line x1={left} y1={y(price)} x2={width - right} y2={y(price)} stroke={palette.gridMajor} strokeDasharray="3 5" />
            <text x={width - right + 9} y={y(price) + 4} className="axis-label">{price.toFixed(5)}</text>
          </g>;
        })}
        {Array.from({ length: 6 }, (_, index) => {
          const time = start + span * index / 5;
          const tickX = left + plotWidth * index / 5;
          return <g key={`time-${index}`}>
            <line x1={tickX} y1={top} x2={tickX} y2={height - bottom} stroke={palette.gridMinor} />
            <text x={tickX} y={height - 8} textAnchor="middle" className="axis-label mono">{formatClock(new Date(time).toISOString(), zone)}</text>
          </g>;
        })}
        {(id === 'h4' || id === 'm15') && visible.map(bar => {
          // feederLabel matches by NY hour alone; on M15 every quarter-hour inside
          // that hour would repeat the same label, overlapping. Minutes are
          // identical in NY and UTC (offsets are whole hours), so this stays
          // timezone-safe while only marking the exact feeder-open candle.
          if (new Date(utcMs(bar.time)).getUTCMinutes() !== 0) return null;
          const label = feederLabel(bar.time);
          if (!label) return null;
          return <text key={`feeder-${bar.time}`} x={x(bar.time)} y={top - 4} textAnchor="middle" className="feeder-label mono">{label}</text>;
        })}
        {markers.map((marker, index) => <g key={`${marker.label}-${index}`}>
          <line x1={left} y1={y(marker.price)} x2={width - right} y2={y(marker.price)} stroke={palette.marker} strokeDasharray="6 4" />
          <text x={left + 6} y={y(marker.price) - 5} className="marker-label mono">{marker.label} · {marker.price.toFixed(5)}</text>
        </g>)}
        {visible.map(bar => {
          const middle = x(bar.time);
          const color = bar.integrity === 'gap' ? palette.gap : bar.close >= bar.open ? palette.bull : palette.bear;
          const label = formatClock(bar.time, zone);
          return <g key={bar.time} data-time={bar.time}
            onPointerEnter={() => setTooltip(t.tooltip(label, zone.toUpperCase(), bar.open.toFixed(5), bar.high.toFixed(5), bar.low.toFixed(5), bar.close.toFixed(5), bar.complete === false, bar.integrity === 'gap'))}
            onPointerLeave={() => setTooltip(t.hoverHint)}
            style={{ cursor: selecting ? 'crosshair' : 'default' }}>
            <line x1={middle} y1={y(bar.high)} x2={middle} y2={y(bar.low)} stroke={color} strokeWidth="2" />
            <rect x={middle - candleWidth / 2} y={Math.min(y(bar.open), y(bar.close))} width={candleWidth} height={Math.max(2, Math.abs(y(bar.open) - y(bar.close)))} fill={color} opacity={bar.complete === false ? 0.64 : 1} stroke={bar.complete === false ? palette.forming : 'none'} />
            <rect x={middle - Math.max(7, candleWidth / 2)} y={top} width={Math.max(14, candleWidth)} height={plotHeight} fill="transparent" />
          </g>;
        })}
      </svg>
      <div id={`${id}-empty`} className="empty-chart" hidden={visible.length > 0}>{t.empty}</div>
    </div>
    <div className="chart-footer"><span>{selecting ? t.selectingHint : t.reviewHint}</span><span id={`${id}-tooltip`} className="mono">{tooltip}</span></div>
  </section>;
}
