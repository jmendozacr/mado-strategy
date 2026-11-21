import { changeAnnotationType, type Annotation, type AnnotationDraft, type AnnotationType } from './model.ts';

type Props = {
  active: boolean;
  busy: boolean;
  draft: AnnotationDraft;
  armed: boolean;
  annotations: Annotation[];
  error: string | null;
  onChange: (draft: AnnotationDraft) => void;
  onArm: () => void;
  onSave: () => void;
};

const TYPES: { value: AnnotationType; label: string }[] = [
  { value: 'key_level', label: 'Key Level (documented type)' },
  { value: 'max', label: 'Max (swing high)' },
  { value: 'min', label: 'Min (swing low)' },
  { value: 'm15_anchor', label: 'Model #1 anchor (M15)' },
  { value: 'horizontal_level', label: 'Horizontal price level' },
];

const needsSource = (type: AnnotationType) => type === 'max' || type === 'min' || type === 'key_level' || type === 'm15_anchor';
const needsPrice = (type: AnnotationType) => type !== 'm15_anchor';

export function AnnotationPanel({ active, busy, draft, armed, annotations, error, onChange, onArm, onSave }: Props) {
  return <section className="annotation-panel" aria-label="Manual annotations">
    <div className="panel-heading"><span className="eyebrow">YOUR KEY LEVELS &amp; ANCHORS</span><h2>Mark what you see</h2>
      <p>Independent of D3/C2. Timestamps and timeframe convention are recorded with every entry.</p></div>
    <div className="annotation-form">
      <label className="field"><span>Type</span>
        <select id="annotation-type" value={draft.annotation_type} disabled={!active || busy}
          onChange={event => onChange(changeAnnotationType(draft, event.target.value as AnnotationType))}>
          {TYPES.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
        </select>
      </label>
      {draft.annotation_type !== 'm15_anchor' && <label className="field"><span>Timeframe</span>
        <select value={draft.timeframe} disabled={!active || busy}
          onChange={event => onChange({ ...draft, timeframe: event.target.value as AnnotationDraft['timeframe'], source_time: undefined })}>
          <option value="m15">M15</option><option value="h4">H4</option><option value="daily">Daily</option>
        </select>
      </label>}
      {needsSource(draft.annotation_type) && <div className="field">
        <span>Source candle</span>
        <button type="button" id="arm-annotation-source" className={armed ? 'button-primary' : ''} disabled={!active || busy} onClick={onArm}>
          {armed ? 'Click a candle on the chart…' : draft.source_time ? `Selected · ${draft.source_time}` : 'Select on chart'}
        </button>
      </div>}
      {needsPrice(draft.annotation_type) && <label className="field"><span>Price</span>
        <input id="annotation-price" type="number" step="any" value={draft.price ?? ''} disabled={!active || busy}
          onChange={event => onChange({ ...draft, price: event.target.value })} /></label>}
      {draft.annotation_type === 'key_level' && <label className="field"><span>Documented level type</span>
        <input id="annotation-level-type" placeholder="FVG, Order Block, Breaker…" value={draft.documented_level_type ?? ''} disabled={!active || busy}
          onChange={event => onChange({ ...draft, documented_level_type: event.target.value })} /></label>}
      <label className="field notes-field"><span>Notes</span>
        <textarea rows={2} value={draft.notes ?? ''} disabled={!active || busy}
          onChange={event => onChange({ ...draft, notes: event.target.value })} /></label>
      {error && <p className="notice error" role="alert">{error}</p>}
      <button type="button" id="save-annotation" className="button-primary" disabled={!active || busy} onClick={onSave}>Save annotation</button>
    </div>
    <div className="decision-history"><h3>Recorded annotations <span id="annotation-count">{annotations.length}</span></h3>
      <ol id="annotation-list">{annotations.map(entry => <li key={entry.id}>
        <strong>{entry.annotation_type}{entry.documented_level_type ? ` · ${entry.documented_level_type}` : ''}</strong>
        <span>{entry.timeframe} · {entry.price ?? '—'} · {entry.source_time ?? entry.cursor_utc}</span>
      </li>)}</ol>
      {annotations.length === 0 && <p>No annotation recorded for this case.</p>}
    </div>
  </section>;
}
