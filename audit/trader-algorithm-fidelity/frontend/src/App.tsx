import { useEffect, useRef, useState } from 'react';
import { Chart } from './Chart.tsx';
import { DecisionForm } from './DecisionForm.tsx';
import { barsThrough, decisionPayload, utcMs, type CaseSummary, type DecisionFields, type PriceLevel, type Replay } from './model.ts';

const initialSpan = 24 * 60 * 60 * 1000;

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { error?: string };
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return await response.json() as T;
}

export function App() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [caseId, setCaseId] = useState('');
  const [replay, setReplay] = useState<Replay | null>(null);
  const [viewEnd, setViewEnd] = useState<number | null>(null);
  const [span, setSpan] = useState(initialSpan);
  const [manualPrice, setManualPrice] = useState('');
  const [notice, setNotice] = useState<{ message: string; error: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [playing, setPlaying] = useState(false);
  const busyRef = useRef(false);
  const playTimer = useRef<number | null>(null);
  const selectionToken = useRef(0);

  function stopPlayback() {
    if (playTimer.current !== null) window.clearInterval(playTimer.current);
    playTimer.current = null;
    setPlaying(false);
  }

  async function selectCase(id: string, available = cases) {
    stopPlayback();
    const token = ++selectionToken.current;
    setCaseId(id);
    setReplay(null);
    setViewEnd(null);
    setNotice(null);
    if (!id || available.find(item => item.id === id)?.status === 'not_started') return;
    try {
      const snapshot = await request<Replay>(`/api/cases/${encodeURIComponent(id)}/replay`);
      if (selectionToken.current === token) setReplay(snapshot);
    } catch (error) {
      if (selectionToken.current === token) setNotice({ message: String(error), error: true });
    }
  }

  useEffect(() => {
    void request<CaseSummary[]>('/api/cases').then(items => {
      setCases(items);
      if (items.length) void selectCase(items[0].id, items);
    }).catch(error => setNotice({ message: String(error), error: true }));
    return () => {
      if (playTimer.current !== null) window.clearInterval(playTimer.current);
    };
  }, []);

  async function action(name: 'start' | 'next' | 'finish') {
    if (!caseId || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setNotice(null);
    try {
      if (name === 'finish') {
        const result = await request<{ status: CaseSummary['status'] }>(`/api/cases/${encodeURIComponent(caseId)}/finish`, 'POST');
        stopPlayback();
        setReplay(current => current && { ...current, case: { ...current.case, status: result.status } });
        setNotice({ message: 'Case finished. Your recorded decisions remain available for review.', error: false });
      } else {
        const result = await request<Replay>(`/api/cases/${encodeURIComponent(caseId)}/${name}`, 'POST');
        setReplay(result);
        setViewEnd(utcMs(result.cursor_utc));
      }
      setCases(await request<CaseSummary[]>('/api/cases'));
    } catch (error) {
      stopPlayback();
      setNotice({ message: String(error), error: true });
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  async function saveDecision(fields: DecisionFields): Promise<boolean> {
    if (!replay || busyRef.current) return false;
    stopPlayback();
    busyRef.current = true;
    setBusy(true);
    try {
      const payload = decisionPayload(fields, replay.cursor_utc);
      await request(`/api/cases/${encodeURIComponent(caseId)}/decisions`, 'POST', payload);
      setReplay(await request<Replay>(`/api/cases/${encodeURIComponent(caseId)}/replay`));
      setNotice({ message: 'Decision saved as a new immutable record.', error: false });
      return true;
    } catch (error) {
      setNotice({ message: String(error), error: true });
      return false;
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  function pan(delta: number) {
    const cursor = replay ? utcMs(replay.cursor_utc) : Date.now();
    const earliest = replay?.m15.length ? utcMs(replay.m15[0].time) : cursor - span;
    setViewEnd(previous => Math.min(cursor, Math.max(earliest + span * 0.2, (previous ?? cursor) - delta)));
  }

  function zoom(factor: number) {
    setSpan(previous => Math.min(7 * initialSpan, Math.max(4 * 60 * 60 * 1000, previous * factor)));
  }

  const selected = cases.find(item => item.id === caseId);
  const item = replay?.case ?? selected;
  const status = item?.status;
  const active = status === 'in_progress';
  const cursor = replay ? utcMs(replay.cursor_utc) : Date.now();
  const end = Math.min(viewEnd ?? cursor, cursor);
  const markers: PriceLevel[] = [...(replay?.reference_levels ?? [])];
  if (manualPrice && Number.isFinite(Number(manualPrice))) markers.push({ price: Number(manualPrice), label: 'Your level' });

  return <div className="app-shell">
    <header className="app-header"><div className="brand"><div className="brand-mark">CR</div><div><span className="eyebrow">LOCAL RESEARCH WORKSPACE</span><h1>CRT Fidelity Audit</h1></div></div><div className="header-status"><span className="status-dot" /> Human review · Stage 1</div></header>
    <main>
      <section className="intro"><div><span className="eyebrow">BLIND HISTORICAL REPLAY</span><h2>Read the market, one closed candle at a time.</h2><p>Record your reasoning before any algorithm comparison is available.</p></div><span className="privacy-chip">Future data locked</span></section>
      <section className="case-toolbar"><label className="case-picker"><span>Historical case</span><select id="case-select" value={caseId} disabled={busy} onChange={event => void selectCase(event.target.value)}>{cases.map(item => <option key={item.id} value={item.id}>{item.pair} · {item.date_ny} · {item.model.toUpperCase()} · {item.status}</option>)}</select></label><div className="case-metadata"><div><span>PAIR</span><strong id="pair">{item?.pair ?? '—'}</strong></div><div><span>MODEL</span><strong id="model">{item?.model.toUpperCase() ?? '—'}</strong></div><div><span>DATE · NY</span><strong id="date-ny">{item?.date_ny ?? '—'}</strong></div><div><span>REPLAY TIME · NY</span><strong id="cursor-ny">{replay?.cursor_ny ?? '—'}</strong></div><div><span>UTC</span><strong id="cursor-utc">{replay?.cursor_utc ?? '—'}</strong></div></div></section>
      {notice && <div id="notice" className={`notice ${notice.error ? 'error' : 'success'}`} role="status">{notice.message}</div>}
      {replay?.case.integrity === 'non_evaluable' && <div id="integrity-notice" className="notice error">This case has an incomplete data bucket. Record the data gap, and do not assess strategy fidelity from this case.</div>}
      <section className="replay-controls" aria-label="Replay controls"><div className="control-group">
        <button id="start" className="button-primary" type="button" disabled={busy || status !== 'not_started'} onClick={() => void action('start')}>Start case</button>
        <button id="next" type="button" disabled={busy || !active} onClick={() => void action('next')}>Next M15 candle →</button>
        <button id="play" type="button" disabled={busy || !active || playing} onClick={() => { if (playTimer.current === null) playTimer.current = window.setInterval(() => void action('next'), 1100); setPlaying(true); }}>Play</button>
        <button id="pause" type="button" disabled={!playing} onClick={stopPlayback}>Pause</button>
        <button id="finish" type="button" disabled={busy || !active || !replay?.case.can_finish} onClick={() => void action('finish')}>Finish case</button>
      </div><div className="replay-caption" id="last-m15">{replay ? `Last closed M15 open · ${replay.last_available_m15 ?? 'none'} UTC` : 'Start a case to reveal the first closed candle'}</div></section>
      <div className="workspace-grid"><div className="charts-column">
        <Chart id="h4" title="H4 · NY feeder" subtitle={`NY-anchored grid · key opens 9PM / 1AM / 5AM / 9AM · ${replay?.h4.at(-1)?.complete === false ? 'current candle forming' : 'closed candles'}`} bars={replay ? barsThrough(replay.h4, replay.cursor_utc) : []} markers={markers} end={end} span={span} onPan={pan} onZoom={zoom} />
        <Chart id="m15" title="M15 · execution" subtitle="A candle enters the chart only after its close" bars={replay ? barsThrough(replay.m15, replay.cursor_utc) : []} markers={markers} end={end} span={span} onPan={pan} onZoom={zoom} />
        <div className="manual-level"><label htmlFor="manual-price">Your price marker</label><input id="manual-price" type="number" step="any" placeholder="Enter a level to inspect on both charts" value={manualPrice} onChange={event => setManualPrice(event.target.value)} /><button id="clear-price" type="button" onClick={() => setManualPrice('')}>Clear</button></div>
      </div>
      <DecisionForm key={caseId} active={active} busy={busy} integrity={replay?.case.integrity ?? 'evaluable'} decisions={replay?.decisions ?? []} onSave={saveDecision} />
      </div>
    </main>
  </div>;
}
