export type CaseSummary = {
  id: string;
  pair: string;
  date_ny: string;
  model: string;
  status: 'not_started' | 'in_progress' | 'finished';
  integrity?: 'evaluable' | 'non_evaluable';
  metric_eligible: boolean | null;
  can_finish?: boolean;
};

export type Bar = {
  time: string;
  available_at: string | null;
  open: number;
  high: number;
  low: number;
  close: number;
  complete?: boolean;
};

export type PriceLevel = { price: number; label: string; time?: string };

export type SavedDecision = {
  id: string;
  case_id: string;
  decision: string;
  cursor_utc: string;
  [field: string]: unknown;
};

export type Replay = {
  case: CaseSummary;
  cursor_utc: string;
  cursor_ny: string;
  m15: Bar[];
  h4: Bar[];
  reference_levels: PriceLevel[];
  key_levels: PriceLevel[];
  last_available_m15: string | null;
  decisions: SavedDecision[];
};

export type DecisionFields = Record<string, string | undefined>;

export function utcMs(value: string): number {
  return Date.parse(/[Zz]$|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
}

export function barsThrough<T extends { time: string; available_at: string | null }>(bars: T[], cursor: string): T[] {
  const limit = utcMs(cursor);
  return bars.filter(bar => utcMs(bar.available_at ?? bar.time) <= limit);
}

export function isDecisionReady(decision: DecisionFields): boolean {
  if (!decision.final_decision) return false;
  if (decision.final_decision === 'discard') return Boolean(decision.discard_reason);
  if (decision.final_decision === 'data_issue') return Boolean(decision.data_issue_reason?.trim());
  if (!decision.notes?.trim()) return false;
  if (decision.final_decision === 'buy' || decision.final_decision === 'sell') {
    return ['entry_price', 'stop_loss', 'take_profit'].every(field => Number(decision[field]) > 0);
  }
  return true;
}

export function decisionPayload(decision: DecisionFields, cursor: string): Record<string, string | number | null | undefined> {
  if (!isDecisionReady(decision)) throw new Error('Add a decision and its reason; trades also need entry, stop, and target prices.');
  const payload: Record<string, string | number | null | undefined> = {
    ...decision,
    decision: decision.final_decision,
    reason: decision.final_decision === 'discard' ? decision.discard_reason
      : decision.final_decision === 'data_issue' ? decision.data_issue_reason!.trim()
        : decision.notes!.trim(),
  };
  for (const field of ['sweep_confirmed_at', 'key_level_available_at', 'model1_anchor_at', 'model1_confirmed_at']) {
    const value = payload[field];
    if (!value || typeof value !== 'string') continue;
    const instant = utcMs(value);
    const availableAt = field === 'model1_anchor_at' ? instant + 15 * 60 * 1000 : instant;
    if (!Number.isFinite(instant) || availableAt > utcMs(cursor)) throw new Error(`${field.replaceAll('_', ' ')} must be available by the replay cursor.`);
    payload[field] = new Date(instant).toISOString();
  }
  for (const field of ['entry_price', 'stop_loss', 'take_profit', 'key_level_price']) {
    const value = payload[field];
    if (value == null || value === '') {
      payload[field] = null;
      continue;
    }
    const price = Number(value);
    if (!Number.isFinite(price) || price <= 0) throw new Error(`${field.replaceAll('_', ' ')} must be a positive price.`);
    payload[field] = price;
  }
  return payload;
}
