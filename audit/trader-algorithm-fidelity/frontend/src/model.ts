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
  integrity?: 'complete' | 'forming' | 'gap';
  gap_slots?: string[];
};

export type PriceLevel = { price: number; label: string; time?: string };

export type HistoricalContext = {
  timeframe: 'h4' | 'daily';
  candles: Bar[];
  next_before: string | null;
  exhausted: boolean;
};

export type AnnotationType = 'max' | 'min' | 'horizontal_level' | 'key_level' | 'm15_anchor';

export type Annotation = {
  id: string;
  case_id: string;
  annotation_type: AnnotationType;
  timeframe: 'm15' | 'h4' | 'daily';
  time_convention: string;
  source_time: string | null;
  source_available_at: string | null;
  price: number | null;
  documented_level_type: string | null;
  notes: string | null;
  cursor_utc: string;
  cursor_ny: string;
  recorded_at: string;
};

const FEEDER_LABELS: Record<number, string> = { 21: '9PM', 1: '1AM', 5: '5AM', 9: '9AM' };

export function feederLabel(utcIso: string): string | null {
  const hour = Number(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', hour12: false }).format(new Date(utcMs(utcIso))));
  return FEEDER_LABELS[hour % 24] ?? null;
}

export function formatClock(utcIso: string, zone: 'ny' | 'utc'): string {
  if (zone === 'utc') return utcIso.slice(0, 16).replace('T', ' ');
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(new Date(utcMs(utcIso)));
  const get = (type: string) => parts.find(part => part.type === type)?.value ?? '';
  return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}`;
}

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
  annotations: Annotation[];
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

export function changeAnnotationType(draft: AnnotationDraft, nextType: AnnotationType): AnnotationDraft {
  return {
    ...draft,
    annotation_type: nextType,
    timeframe: nextType === 'm15_anchor' ? 'm15' : draft.timeframe,
    source_time: undefined,
  };
}

export function earliestPannableMs(bars: { h4: Bar[]; daily: Bar[]; m15: Bar[] }, fallback: number): number {
  const candidates = [bars.h4[0]?.time, bars.daily[0]?.time, bars.m15[0]?.time]
    .filter((time): time is string => Boolean(time))
    .map(utcMs);
  return candidates.length ? Math.min(...candidates) : fallback;
}

export type DecisionTimeField = 'sweep_confirmed_at' | 'key_level_available_at' | 'model1_anchor_at' | 'model1_confirmed_at';
export type DecisionFillField = DecisionTimeField | 'feeder_reference';

/** The UTC wall-clock numbers of a candle's real timestamp, formatted for a
 * `datetime-local` input -- matching this app's existing convention that a
 * typed "UTC" field means the literal clock digits, not the browser's own
 * timezone. Picking a candle should produce exactly what the user would have
 * had to type by hand. */
export function utcToDatetimeLocal(iso: string): string {
  const date = new Date(utcMs(iso));
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}T${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`;
}

export function mergeOlderBars(current: Bar[], older: Bar[]): Bar[] {
  const seen = new Set(current.map(bar => bar.time));
  const merged = [...older.filter(bar => !seen.has(bar.time)), ...current];
  return merged.sort((a, b) => utcMs(a.time) - utcMs(b.time));
}

export type AnnotationDraft = {
  annotation_type: AnnotationType;
  timeframe: 'm15' | 'h4' | 'daily';
  source_time?: string;
  price?: string;
  documented_level_type?: string;
  notes?: string;
};

export function annotationPayload(draft: AnnotationDraft): Record<string, string | number | undefined> {
  const payload: Record<string, string | number | undefined> = {
    annotation_type: draft.annotation_type, timeframe: draft.timeframe,
    source_time: draft.source_time, documented_level_type: draft.documented_level_type, notes: draft.notes,
  };
  if (draft.annotation_type !== 'm15_anchor') {
    const price = Number(draft.price);
    if (!draft.price || !Number.isFinite(price) || price <= 0) throw new Error('A positive price is required for this annotation.');
    payload.price = price;
  }
  if (draft.annotation_type === 'key_level' && !draft.documented_level_type?.trim()) {
    throw new Error('Describe the documented Key Level type (charter terminology).');
  }
  if (['max', 'min', 'key_level', 'm15_anchor'].includes(draft.annotation_type) && !draft.source_time) {
    throw new Error('Select a candle on the chart first.');
  }
  return payload;
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
