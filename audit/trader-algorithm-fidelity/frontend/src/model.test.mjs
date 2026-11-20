import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { barsThrough, decisionPayload, isDecisionReady } from './model.ts';

describe('causal replay view', () => {
  const bars = [
    { time: '2025-01-07T14:00:00+00:00', available_at: '2025-01-07T14:15:00+00:00', open: 1, high: 2, low: 0.5, close: 1.5 },
    { time: '2025-01-07T14:15:00+00:00', available_at: '2025-01-07T14:30:00+00:00', open: 1.5, high: 2, low: 1, close: 1.8 },
  ];

  it('never presents an M15 before its close', () => {
    assert.deepEqual(barsThrough(bars, '2025-01-07T14:15:00+00:00'), [bars[0]]);
  });

  it('retains a partial H4 supplied by the bounded API', () => {
    const h4 = { ...bars[0], available_at: null };
    assert.deepEqual(barsThrough([h4], '2025-01-07T14:15:00+00:00'), [h4]);
  });

  it('requires a reason and trade prices before saving', () => {
    assert.equal(isDecisionReady({ final_decision: 'wait' }), false);
    assert.equal(isDecisionReady({ final_decision: 'buy', notes: 'Valid', entry_price: '1.2', stop_loss: '1.1' }), false);
    assert.equal(isDecisionReady({ final_decision: 'wait', notes: 'No confirmation yet' }), true);
  });

  it('rejects a forming M15 anchor and normalizes the saved payload', () => {
    assert.throws(() => decisionPayload({ final_decision: 'wait', notes: 'Wait', model1_anchor_at: '2025-01-07T14:15' }, '2025-01-07T14:15:00+00:00'), /replay cursor/);
    const payload = decisionPayload({ final_decision: 'buy', notes: 'Confirmed', entry_price: '1.2', stop_loss: '1.1', take_profit: '1.4' }, '2025-01-07T14:15:00+00:00');
    assert.equal(payload.entry_price, 1.2);
    assert.equal(payload.reason, 'Confirmed');
  });
});
