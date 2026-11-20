import { useState, type FormEvent } from 'react';
import { isDecisionReady, type DecisionFields, type SavedDecision } from './model.ts';

type Props = {
  active: boolean;
  busy: boolean;
  decisions: SavedDecision[];
  onSave: (fields: DecisionFields) => Promise<boolean>;
};

const yesNo = [
  ['', 'Unspecified'],
  ['yes', 'Yes'],
  ['no', 'No'],
  ['uncertain', 'Uncertain'],
];

export function DecisionForm({ active, busy, decisions, onSave }: Props) {
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
    <div className="panel-heading"><span className="eyebrow">HUMAN ASSESSMENT</span><h2>Record your read</h2><p>Every save creates a separate entry with the visible historical cursor.</p></div>
    <form id="decision-form" onChange={event => setFields(Object.fromEntries(new FormData(event.currentTarget)) as DecisionFields)} onSubmit={event => void submit(event)}>
      <fieldset disabled={!active || busy}><legend>CRT evaluation</legend>
        <label className="field"><span>Valid CRT?</span><select name="crt_valid">{yesNo.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="field"><span>Reference feeder candle (NY open)</span><input name="feeder_reference" placeholder="YYYY-MM-DD HH:MM NY" /></label>
        <label className="field"><span>Swept side</span><select name="swept_side"><option value="">Unspecified</option><option value="high">High</option><option value="low">Low</option><option value="both">Both</option><option value="none">None</option></select></label>
        <label className="field"><span>Sweep confirmed at (UTC)</span><input name="sweep_confirmed_at" type="datetime-local" /></label>
      </fieldset>
      <fieldset disabled={!active || busy}><legend>Key Level</legend>
        <label className="field"><span>Valid Key Level?</span><select name="key_level_valid">{yesNo.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="field"><span>Key Level type</span><input name="key_level_type" placeholder="Documented level type" /></label>
        <label className="field"><span>Key Level price</span><input name="key_level_price" type="number" step="any" /></label>
        <label className="field"><span>Available at (UTC)</span><input name="key_level_available_at" type="datetime-local" /></label>
        <label className="field"><span>Valid touch?</span><select name="key_level_touch_valid">{yesNo.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      </fieldset>
      <fieldset disabled={!active || busy}><legend>Model #1</legend>
        <label className="field"><span>Begin confirmation search?</span><select name="begin_confirmation_search">{yesNo.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="field"><span>Model #1 exists?</span><select name="model1_exists">{yesNo.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="field"><span>Anchor M15 open (UTC)</span><input name="model1_anchor_at" type="datetime-local" /></label>
        <label className="field"><span>Direction</span><select name="direction"><option value="">Unspecified</option><option value="bullish">Bullish</option><option value="bearish">Bearish</option><option value="undetermined">Undetermined</option></select></label>
        <label className="field"><span>Confirmed at (UTC)</span><input name="model1_confirmed_at" type="datetime-local" /></label>
      </fieldset>
      <fieldset disabled={!active || busy}><legend>Final decision</legend>
        <label className="field"><span>Action</span><select name="final_decision" id="final-decision" required><option value="">Select action</option><option value="buy">Buy</option><option value="sell">Sell</option><option value="wait">Keep waiting</option><option value="discard">Discard opportunity</option></select></label>
        <div className="price-grid" id="price-fields" hidden={decision !== 'buy' && decision !== 'sell'}>
          <label className="field"><span>Entry price</span><input name="entry_price" type="number" step="any" /></label>
          <label className="field"><span>Stop Loss</span><input name="stop_loss" type="number" step="any" /></label>
          <label className="field"><span>Take Profit</span><input name="take_profit" type="number" step="any" /></label>
        </div>
        <label className="field" id="discard-field" hidden={decision !== 'discard'}><span>Discard reason</span><select name="discard_reason"><option value="">Select reason</option><option value="invalid_crt">Invalid CRT</option><option value="no_sweep">No valid sweep</option><option value="no_key_level">No valid Key Level</option><option value="invalid_touch">Invalid Key Level touch</option><option value="no_model1">No Model #1</option><option value="timing">Timing outside rules</option><option value="data_gap">Missing data</option><option value="other">Other documented reason</option></select></label>
        <label className="field notes-field"><span>Observations / reason</span><textarea name="notes" placeholder="What did you see, and why does it matter?" rows={3} /></label>
        <button className="button-primary save-button" id="save" type="submit" disabled={busy || !active || !isDecisionReady(fields)}>Save decision</button>
      </fieldset>
    </form>
    <div className="decision-history"><h3>Recorded decisions <span id="decision-count">{decisions.length}</span></h3>
      <ol id="decision-list">{decisions.map(entry => <li key={entry.id}><strong>{entry.decision || String(entry.final_decision || 'Decision')}</strong><span>{entry.cursor_utc}</span></li>)}</ol>
      {decisions.length === 0 && <p id="decision-empty">No decision recorded for this case.</p>}
    </div>
  </aside>;
}
