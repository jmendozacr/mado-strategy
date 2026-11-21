import { Field } from './Field.tsx';
import type { Dict } from './i18n.ts';
import { changeAnnotationType, type Annotation, type AnnotationDraft, type AnnotationType } from './model.ts';

type Props = {
  t: Dict;
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

const needsSource = (type: AnnotationType) => type === 'max' || type === 'min' || type === 'key_level' || type === 'm15_anchor';
const needsPrice = (type: AnnotationType) => type !== 'm15_anchor';

export function AnnotationPanel({ t, active, busy, draft, armed, annotations, error, onChange, onArm, onSave }: Props) {
  const a = t.annotation;
  const types: { value: AnnotationType; label: string }[] = [
    { value: 'key_level', label: a.typeKeyLevel },
    { value: 'max', label: a.typeMax },
    { value: 'min', label: a.typeMin },
    { value: 'm15_anchor', label: a.typeM15Anchor },
    { value: 'horizontal_level', label: a.typeHorizontal },
  ];
  const sourceState = armed ? 'armed' : draft.source_time ? 'selected' : 'idle';
  const sourceLabel = armed ? a.sourceArmed : draft.source_time ? a.sourceSelected(draft.source_time) : a.sourceIdle;

  return <section className="annotation-panel" aria-label="Manual annotations">
    <div className="panel-heading"><h2>{a.heading}</h2><p>{a.hint}</p></div>
    <div className="annotation-form">
      <Field label={a.type} hint={a.typeHint}>
        <select id="annotation-type" value={draft.annotation_type} disabled={!active || busy}
          onChange={event => onChange(changeAnnotationType(draft, event.target.value as AnnotationType))}>
          {types.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
        </select>
      </Field>
      {draft.annotation_type !== 'm15_anchor' && <Field label={a.timeframe} hint={a.timeframeHint}>
        <select value={draft.timeframe} disabled={!active || busy}
          onChange={event => onChange({ ...draft, timeframe: event.target.value as AnnotationDraft['timeframe'], source_time: undefined })}>
          <option value="m15">M15</option><option value="h4">H4</option><option value="daily">Daily</option>
        </select>
      </Field>}
      {needsSource(draft.annotation_type) && <Field label={a.sourceCandle} hint={a.sourceCandleHint}>
        <button type="button" id="arm-annotation-source" data-state={sourceState} className={armed ? 'button-primary' : ''} disabled={!active || busy} onClick={onArm}>
          {sourceLabel}
        </button>
      </Field>}
      {needsPrice(draft.annotation_type) && <Field label={a.price} hint={a.priceHint}>
        <input id="annotation-price" type="number" step="any" className="mono" value={draft.price ?? ''} disabled={!active || busy}
          onChange={event => onChange({ ...draft, price: event.target.value })} />
      </Field>}
      {draft.annotation_type === 'key_level' && <Field label={a.levelType} hint={a.levelTypeHint}>
        <input id="annotation-level-type" placeholder={a.levelTypePlaceholder} value={draft.documented_level_type ?? ''} disabled={!active || busy}
          onChange={event => onChange({ ...draft, documented_level_type: event.target.value })} />
      </Field>}
      <Field label={a.notes} hint={a.notesHint} wide>
        <textarea rows={2} value={draft.notes ?? ''} disabled={!active || busy}
          onChange={event => onChange({ ...draft, notes: event.target.value })} />
      </Field>
      {error && <p className="notice error" role="alert">{error}</p>}
      <button type="button" id="save-annotation" className="button-primary" disabled={!active || busy} onClick={onSave}>{a.save}</button>
    </div>
    <div className="decision-history"><h3>{a.historyTitle} <span id="annotation-count">{annotations.length}</span></h3>
      <ol id="annotation-list">{annotations.map(entry => <li key={entry.id}>
        <strong>{entry.annotation_type}{entry.documented_level_type ? ` · ${entry.documented_level_type}` : ''}</strong>
        <span className="mono">{entry.timeframe} · {entry.price ?? '—'} · {entry.source_time ?? entry.cursor_utc}</span>
      </li>)}</ol>
      {annotations.length === 0 && <p>{a.historyEmpty}</p>}
    </div>
  </section>;
}
