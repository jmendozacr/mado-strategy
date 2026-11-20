import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { annotationPayload, barsThrough, changeAnnotationType, decisionPayload, feederLabel, formatClock, isDecisionReady, mergeOlderBars } from './model.ts';

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
    assert.equal(isDecisionReady({ final_decision: 'data_issue', notes: 'Some note' }), false);
    assert.equal(isDecisionReady({ final_decision: 'data_issue', data_issue_reason: 'M15 gap at 14:15 UTC' }), true);
  });

  it('rejects a forming M15 anchor and normalizes the saved payload', () => {
    assert.throws(() => decisionPayload({ final_decision: 'wait', notes: 'Wait', model1_anchor_at: '2025-01-07T14:15' }, '2025-01-07T14:15:00+00:00'), /replay cursor/);
    const payload = decisionPayload({ final_decision: 'buy', notes: 'Confirmed', entry_price: '1.2', stop_loss: '1.1', take_profit: '1.4' }, '2025-01-07T14:15:00+00:00');
    assert.equal(payload.entry_price, 1.2);
    assert.equal(payload.reason, 'Confirmed');
  });

  it('records data issues as a distinct non-judgment and interprets entered wall time as UTC', () => {
    const payload = decisionPayload({
      final_decision: 'data_issue',
      data_issue_reason: 'Missing M15 candle at 14:15 UTC',
      sweep_confirmed_at: '2025-01-07T14:00',
    }, '2025-01-07T14:15:00+00:00');
    assert.equal(payload.decision, 'data_issue');
    assert.equal(payload.data_issue_reason, 'Missing M15 candle at 14:15 UTC');
    assert.equal(payload.reason, 'Missing M15 candle at 14:15 UTC');
    assert.equal(payload.sweep_confirmed_at, '2025-01-07T14:00:00.000Z');
  });

  it('merges an older historical context page without duplicating bars', () => {
    const current = [{ time: '2025-01-08T00:00:00+00:00', available_at: '2025-01-08T04:00:00+00:00', open: 1, high: 1, low: 1, close: 1 }];
    const older = [
      { time: '2025-01-07T20:00:00+00:00', available_at: '2025-01-08T00:00:00+00:00', open: 1, high: 1, low: 1, close: 1 },
      { time: '2025-01-08T00:00:00+00:00', available_at: '2025-01-08T04:00:00+00:00', open: 9, high: 9, low: 9, close: 9 },
    ];
    const merged = mergeOlderBars(current, older);
    assert.equal(merged.length, 2);
    assert.equal(merged[0].time, '2025-01-07T20:00:00+00:00');
    assert.equal(merged[1].open, 1);
  });

  it('labels only the four documented feeder opens, in New York time', () => {
    assert.equal(feederLabel('2025-01-07T14:00:00+00:00'), '9AM');
    assert.equal(feederLabel('2025-01-07T18:00:00+00:00'), null);
  });

  it('formats a UTC instant in New York wall time when requested', () => {
    assert.equal(formatClock('2025-01-07T14:00:00+00:00', 'ny'), '2025-01-07 09:00');
    assert.equal(formatClock('2025-01-07T14:00:00+00:00', 'utc'), '2025-01-07 14:00');
  });

  it('requires a selected candle for candle-sourced annotation types', () => {
    assert.throws(() => annotationPayload({ annotation_type: 'max', timeframe: 'm15', price: '1.2' }), /Select a candle/);
    assert.throws(() => annotationPayload({ annotation_type: 'key_level', timeframe: 'h4', price: '1.2', source_time: '2025-01-07T09:00:00+00:00' }), /documented Key Level/);
    const payload = annotationPayload({ annotation_type: 'horizontal_level', timeframe: 'h4', price: '1.2345' });
    assert.equal(payload.price, 1.2345);
    assert.equal(payload.source_time, undefined);
  });

  it('forces the m15 timeframe and clears a stale source candle when switching to an M15 anchor', () => {
    const fromH4 = { annotation_type: 'key_level', timeframe: 'h4', source_time: '2025-01-07T14:00:00+00:00', price: '1.2' };
    const switched = changeAnnotationType(fromH4, 'm15_anchor');
    assert.equal(switched.timeframe, 'm15');
    assert.equal(switched.source_time, undefined);
    assert.equal(switched.price, '1.2');

    const backToKeyLevel = changeAnnotationType(switched, 'key_level');
    assert.equal(backToKeyLevel.timeframe, 'm15');
    assert.equal(backToKeyLevel.source_time, undefined);
  });
});
