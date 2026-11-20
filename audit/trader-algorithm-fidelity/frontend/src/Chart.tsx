import { useRef, useState, type PointerEvent, type WheelEvent } from 'react';
import { feederLabel, formatClock, utcMs, type Bar, type PriceLevel } from './model.ts';

type Props = {
  id: 'h4' | 'm15' | 'daily';
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

export function Chart({ id, title, subtitle, bars, markers, end, span, zone, selecting, onPan, onZoom, onSelectCandle }: Props) {
  const [tooltip, setTooltip] = useState('Hover a candle for OHLC');
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
    if (dragStart.current !== null) {
      onPan((event.clientX - dragStart.current) / event.currentTarget.clientWidth * span);
      dragStart.current = null;
    }
  }

  function wheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    onZoom(event.deltaY < 0 ? 0.8 : 1.25);
  }

  return <section className="chart-card" aria-label={`${title} candlestick chart`}>
    <div className="chart-heading"><div><h2>{title}</h2><span>{subtitle}</span></div><div className="chart-tools">
      <button type="button" aria-label={`Review earlier ${id.toUpperCase()} candles`} onClick={() => onPan(span * 0.3)}>←</button>
      <button type="button" aria-label={`Zoom in ${id.toUpperCase()}`} onClick={() => onZoom(0.7)}>+</button>
      <button type="button" aria-label={`Zoom out ${id.toUpperCase()}`} onClick={() => onZoom(1.4)}>−</button>
      <button type="button" aria-label={`Review later ${id.toUpperCase()} candles`} onClick={() => onPan(-span * 0.3)}>→</button>
    </div></div>
    <div className="chart-surface">
      <svg id={`${id}-chart`} viewBox="0 0 1000 260" role="img" aria-label={`Available ${id.toUpperCase()} candles`}
        onWheel={wheel} onPointerDown={event => { dragStart.current = event.clientX; event.currentTarget.setPointerCapture(event.pointerId); }}
        onPointerUp={endDrag} onPointerCancel={() => { dragStart.current = null; }}>
        <rect x="0" y="0" width={width} height={height} fill="#0d1724" />
        {Array.from({ length: 5 }, (_, index) => {
          const price = floor + (ceiling - floor) * index / 4;
          return <g key={`price-${index}`}>
            <line x1={left} y1={y(price)} x2={width - right} y2={y(price)} stroke="#253544" strokeDasharray="3 5" />
            <text x={width - right + 9} y={y(price) + 4} className="axis-label">{price.toFixed(5)}</text>
          </g>;
        })}
        {Array.from({ length: 6 }, (_, index) => {
          const time = start + span * index / 5;
          const tickX = left + plotWidth * index / 5;
          return <g key={`time-${index}`}>
            <line x1={tickX} y1={top} x2={tickX} y2={height - bottom} stroke="#1c2c3a" />
            <text x={tickX} y={height - 8} textAnchor="middle" className="axis-label">{formatClock(new Date(time).toISOString(), zone)}</text>
          </g>;
        })}
        {(id === 'h4' || id === 'm15') && visible.map(bar => {
          const label = feederLabel(bar.time);
          if (!label) return null;
          return <text key={`feeder-${bar.time}`} x={x(bar.time)} y={top - 4} textAnchor="middle" className="feeder-label">{label}</text>;
        })}
        {markers.map((marker, index) => <g key={`${marker.label}-${index}`}>
          <line x1={left} y1={y(marker.price)} x2={width - right} y2={y(marker.price)} stroke="#e8b96b" strokeDasharray="6 4" />
          <text x={left + 6} y={y(marker.price) - 5} className="marker-label">{marker.label} · {marker.price.toFixed(5)}</text>
        </g>)}
        {visible.map(bar => {
          const middle = x(bar.time);
          const color = bar.integrity === 'gap' ? '#9a6b2f' : bar.close >= bar.open ? '#48c6a7' : '#ef7583';
          const label = formatClock(bar.time, zone);
          return <g key={bar.time}
            onPointerEnter={() => setTooltip(`${label} ${zone.toUpperCase()} · O ${bar.open.toFixed(5)} H ${bar.high.toFixed(5)} L ${bar.low.toFixed(5)} C ${bar.close.toFixed(5)}${bar.complete === false ? ' · forming' : ''}${bar.integrity === 'gap' ? ' · data gap' : ''}`)}
            onPointerLeave={() => setTooltip('Hover a candle for OHLC')}
            onClick={() => onSelectCandle?.(bar)} style={{ cursor: selecting ? 'crosshair' : 'default' }}>
            <line x1={middle} y1={y(bar.high)} x2={middle} y2={y(bar.low)} stroke={color} strokeWidth="2" />
            <rect x={middle - candleWidth / 2} y={Math.min(y(bar.open), y(bar.close))} width={candleWidth} height={Math.max(2, Math.abs(y(bar.open) - y(bar.close)))} fill={color} opacity={bar.complete === false ? 0.64 : 1} stroke={bar.complete === false ? '#f8d18b' : 'none'} />
            <rect x={middle - Math.max(7, candleWidth / 2)} y={top} width={Math.max(14, candleWidth)} height={plotHeight} fill="transparent" />
          </g>;
        })}
      </svg>
      <div id={`${id}-empty`} className="empty-chart" hidden={visible.length > 0}>No candles in this view</div>
    </div>
    <div className="chart-footer"><span>{selecting ? 'Click a candle to use it as the annotation source' : 'Drag or use arrows to review · Scroll or use +/- to zoom'}</span><span id={`${id}-tooltip`}>{tooltip}</span></div>
  </section>;
}
