import { useState, type FormEvent } from 'react';
import { Field } from './Field.tsx';
import type { Dict } from './i18n.ts';
import { isDecisionReady, type DecisionFields, type SavedDecision } from './model.ts';

type Props = {
  t: Dict;
  active: boolean;
  busy: boolean;
  integrity: 'evaluable' | 'non_evaluable';
  decisions: SavedDecision[];
  onSave: (fields: DecisionFields) => Promise<boolean>;
};

export function DecisionForm({ t, active, busy, integrity, decisions, onSave }: Props) {
  const d = t.decision;
  const yesNo = [['', d.unspecified], ['yes', d.yes], ['no', d.no], ['uncertain', d.uncertain]] as const;
  const [fields, setFields] = useState<DecisionFields>({});
  const decision = fields.final_decision ?? '';

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form)) as DecisionFields;
    if (await onSave(values)) {
      form.reset();
      setFields({});
    }
  }

  return <aside className="decision-panel">
    <div className="panel-heading"><h2>{d.heading}</h2><p>{d.hint}</p></div>
    <form id="decision-form" onChange={event => setFields(Object.fromEntries(new FormData(event.currentTarget)) as DecisionFields)} onSubmit={event => void submit(event)}>
      <fieldset disabled={!active || busy}>
        <legend><span className="step-number">1</span>{d.stepCrtTitle}</legend>
        <Field label={d.crtValid} hint={d.crtValidHint}>
          <select name="crt_valid">{yesNo.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        </Field>
        <Field label={d.feederReference} hint={d.feederReferenceHint} wide>
          <input name="feeder_reference" placeholder={d.feederReferencePlaceholder} className="mono" />
        </Field>
        <Field label={d.sweptSide} hint={d.sweptSideHint}>
          <select name="swept_side">
            <option value="">{d.unspecified}</option>
            <option value="high">{d.high}</option>
            <option value="low">{d.low}</option>
            <option value="both">{d.both}</option>
            <option value="none">{d.sideNone}</option>
          </select>
        </Field>
        <Field label={d.sweepConfirmedAt} hint={d.sweepConfirmedAtHint}>
          <input name="sweep_confirmed_at" type="datetime-local" className="mono" />
        </Field>
      </fieldset>

      <fieldset disabled={!active || busy}>
        <legend><span className="step-number">2</span>{d.stepKeyLevelTitle}</legend>
        <Field label={d.keyLevelValid} hint={d.keyLevelValidHint}>
          <select name="key_level_valid">{yesNo.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        </Field>
        <Field label={d.keyLevelType} hint={d.keyLevelTypeHint} wide>
          <input name="key_level_type" placeholder={d.keyLevelTypePlaceholder} />
        </Field>
        <Field label={d.keyLevelPrice} hint={d.keyLevelPriceHint}>
          <input name="key_level_price" type="number" step="any" className="mono" />
        </Field>
        <Field label={d.keyLevelAvailableAt} hint={d.keyLevelAvailableAtHint}>
          <input name="key_level_available_at" type="datetime-local" className="mono" />
        </Field>
        <Field label={d.keyLevelTouchValid} hint={d.keyLevelTouchValidHint}>
          <select name="key_level_touch_valid">{yesNo.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        </Field>
      </fieldset>

      <fieldset disabled={!active || busy}>
        <legend><span className="step-number">3</span>{d.stepModel1Title}</legend>
        <Field label={d.beginConfirmationSearch} hint={d.beginConfirmationSearchHint}>
          <select name="begin_confirmation_search">{yesNo.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        </Field>
        <Field label={d.model1Exists} hint={d.model1ExistsHint}>
          <select name="model1_exists">{yesNo.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        </Field>
        <Field label={d.model1AnchorAt} hint={d.model1AnchorAtHint}>
          <input name="model1_anchor_at" type="datetime-local" className="mono" />
        </Field>
        <Field label={d.direction} hint={d.directionHint}>
          <select name="direction">
            <option value="">{d.unspecified}</option>
            <option value="bullish">{d.bullish}</option>
            <option value="bearish">{d.bearish}</option>
            <option value="undetermined">{d.undetermined}</option>
          </select>
        </Field>
        <Field label={d.model1ConfirmedAt} hint={d.model1ConfirmedAtHint}>
          <input name="model1_confirmed_at" type="datetime-local" className="mono" />
        </Field>
      </fieldset>

      <fieldset disabled={!active || busy} className="step-final">
        <legend><span className="step-number">4</span>{d.stepFinalTitle}</legend>
        <Field label={d.action} hint={d.actionHint} wide>
          <select name="final_decision" id="final-decision" required>
            <option value="">{d.actionPlaceholder}</option>
            <option value="buy">{d.buy}</option>
            <option value="sell">{d.sell}</option>
            <option value="wait">{d.wait}</option>
            <option value="discard">{d.discard}</option>
            {integrity === 'non_evaluable' && <option value="data_issue">{d.dataIssue}</option>}
          </select>
        </Field>
        <div className="price-grid" id="price-fields" hidden={decision !== 'buy' && decision !== 'sell'}>
          <Field label={d.entryPrice} hint={d.entryPriceHint}><input name="entry_price" type="number" step="any" className="mono" /></Field>
          <Field label={d.stopLoss} hint={d.stopLossHint}><input name="stop_loss" type="number" step="any" className="mono" /></Field>
          <Field label={d.takeProfit} hint={d.takeProfitHint}><input name="take_profit" type="number" step="any" className="mono" /></Field>
        </div>
        <div id="discard-field" hidden={decision !== 'discard'}>
          <Field label={d.discardReason} hint={d.discardReasonHint} wide>
            <select name="discard_reason">
              <option value="">{d.discardReasonPlaceholder}</option>
              <option value="invalid_crt">{d.discardInvalidCrt}</option>
              <option value="no_sweep">{d.discardNoSweep}</option>
              <option value="no_key_level">{d.discardNoKeyLevel}</option>
              <option value="invalid_touch">{d.discardInvalidTouch}</option>
              <option value="no_model1">{d.discardNoModel1}</option>
              <option value="timing">{d.discardTiming}</option>
              <option value="data_gap">{d.discardDataGap}</option>
              <option value="other">{d.discardOther}</option>
            </select>
          </Field>
        </div>
        <div className="notes-field" hidden={decision !== 'data_issue'}>
          <Field label={d.dataIssueReason} hint={d.dataIssueReasonHint} wide>
            <textarea name="data_issue_reason" placeholder={d.dataIssueReasonPlaceholder} rows={3} />
          </Field>
        </div>
        <div className="notes-field">
          <Field label={d.notes} hint={d.notesHint} wide>
            <textarea name="notes" placeholder={d.notesPlaceholder} rows={3} />
          </Field>
        </div>
        <button className="button-primary save-button" id="save" type="submit" disabled={busy || !active || !isDecisionReady(fields)}>{d.save}</button>
      </fieldset>
    </form>
    <div className="decision-history"><h3>{d.historyTitle} <span id="decision-count">{decisions.length}</span></h3>
      <ol id="decision-list">{decisions.map(entry => <li key={entry.id}><strong>{entry.decision || String(entry.final_decision || d.decisionFallback)}</strong><span className="mono">{entry.cursor_utc}</span></li>)}</ol>
      {decisions.length === 0 && <p id="decision-empty">{d.historyEmpty}</p>}
    </div>
  </aside>;
}
