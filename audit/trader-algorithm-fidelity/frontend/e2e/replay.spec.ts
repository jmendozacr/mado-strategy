import { test, expect } from '@playwright/test';

const api = 'http://127.0.0.1:8766';

test('a real case stays causal and its human decision survives reload', async ({ page, request }) => {
  test.setTimeout(60_000); // the deep H4/Daily pan below drives several real historical_context() scans
  await page.route('**/api/**', route => {
    const url = new URL(route.request().url());
    url.port = '8766';
    return route.continue({ url: url.toString() });
  });
  await page.goto('/');

  const cases = await (await request.get(`${api}/api/cases`)).json();
  expect(cases).toHaveLength(30);
  expect(Object.keys(cases[0]).sort()).toEqual(['date_ny', 'id', 'metric_eligible', 'model', 'pair', 'status']);
  await expect(page.locator('#case-select option')).toHaveCount(30);

  const selected = cases.find((item: { pair: string; model: string; date_ny: string }) =>
    item.pair === 'EURUSD' && item.model === '9am' && item.date_ny === '2015-01-07');
  expect(selected).toBeTruthy();
  await page.locator('#case-select').selectOption(selected.id);
  await page.locator('#start').click();
  await expect(page.locator('#next')).toBeEnabled();
  const replayUrl = `${api}/api/cases/${selected.id}/replay`;
  const before = await (await request.get(replayUrl)).json();
  expect(before.m15.every((bar: { available_at: string }) => Date.parse(bar.available_at) <= Date.parse(before.cursor_utc))).toBe(true);

  await page.locator('#next').click();
  await expect.poll(async () => (await (await request.get(replayUrl)).json()).cursor_utc).not.toBe(before.cursor_utc);
  const after = await (await request.get(replayUrl)).json();
  expect(after.m15).toHaveLength(before.m15.length + 1);
  expect(after.m15.every((bar: { available_at: string }) => Date.parse(bar.available_at) <= Date.parse(after.cursor_utc))).toBe(true);
  expect(after.h4.some((bar: { complete: boolean; available_at: string | null }) => !bar.complete && bar.available_at === null)).toBe(true);
  await expect(page.locator('#h4-chart rect[fill="transparent"]').first()).toBeVisible();
  await expect(page.locator('#m15-chart rect[fill="transparent"]').first()).toBeVisible();

  await expect(page.locator('#daily-chart')).toBeVisible();
  await page.locator('#zone-utc').click();
  await expect(page.locator('#zone-utc')).toHaveClass(/button-primary/);
  await page.locator('#zone-ny').click();

  await page.locator('#final-decision').selectOption('wait');
  await page.locator('textarea[name="notes"]').fill('Browser verification only; not a trader judgment.');
  await page.locator('#save').click();
  await expect(page.locator('#decision-count')).toHaveText('1');

  await page.locator('#annotation-type').selectOption('horizontal_level');
  await page.locator('#annotation-price').fill('1.11111');
  await page.locator('#save-annotation').click();
  await expect(page.locator('#annotation-count')).toHaveText('1');

  // Problem C regression: pick H4 as the timeframe for a Key Level, then switch
  // the type to an M15 anchor -- the stale "h4" timeframe must not survive the
  // switch, and the M15 anchor must save correctly by clicking a real candle.
  await page.locator('#annotation-type').selectOption('key_level');
  await page.locator('#annotation-type').selectOption('m15_anchor');
  await expect(page.locator('#arm-annotation-source')).toHaveAttribute('data-state', 'idle');
  await page.locator('#arm-annotation-source').click();
  await expect(page.locator('#arm-annotation-source')).toHaveAttribute('data-state', 'armed');
  await page.locator('#m15-chart rect[fill="transparent"]').last().click();
  await expect(page.locator('#arm-annotation-source')).toHaveAttribute('data-state', 'selected');
  await page.locator('#save-annotation').click();
  await expect(page.locator('#annotation-count')).toHaveText('2');

  const saved = await (await request.get(replayUrl)).json();
  expect(saved.decisions[0]).toMatchObject({ case_id: selected.id, decision: 'wait', cursor_utc: after.cursor_utc });

  // Problem A: H4/Daily must be pannable for months, fed by historical_context()
  // pages, well past the original ~32h M15 execution window -- and the replay
  // cursor must never move while doing it.
  // historical_context() scans the real multi-year M15 CSV per page (~0.8-0.9s
  // each on this dataset -- a real but separate performance characteristic, not
  // one of the four named defects) -- so this real-browser proof targets a
  // modest depth that is still an order of magnitude past the old 32h ceiling.
  // tests/test_context.py separately proves the pagination chain itself keeps
  // extending correctly over many pages, several months back, using a fast
  // synthetic fixture.
  const cursorBeforePan = await page.locator('#cursor-utc').textContent();
  for (let i = 0; i < 6; i += 1) await page.locator('button[data-action="zoom-out"][data-chart="h4"]').click();
  const oldestVisible = async (chart: string) => {
    const times = await page.locator(`#${chart}-chart g[data-time]`).evaluateAll(nodes => nodes.map(n => n.getAttribute('data-time')));
    return times.length ? Math.min(...times.map(t => Date.parse(t!))) : Infinity;
  };
  const targetDaysMs = 10 * 24 * 60 * 60 * 1000;
  const target = Date.parse(before.cursor_utc) - targetDaysMs;
  for (let i = 0; i < 8; i += 1) {
    const [oldestH4, oldestDaily] = await Promise.all([oldestVisible('h4'), oldestVisible('daily')]);
    if (oldestH4 < target && oldestDaily < target) break;
    const nextH4 = page.waitForResponse(resp => resp.url().includes('timeframe=h4'), { timeout: 15000 }).catch(() => null);
    await page.locator('button[data-action="pan-earlier"][data-chart="h4"]').click();
    await nextH4;
  }
  const [finalH4, finalDaily] = await Promise.all([oldestVisible('h4'), oldestVisible('daily')]);
  expect(Date.parse(before.cursor_utc) - finalH4).toBeGreaterThan(targetDaysMs);
  expect(Date.parse(before.cursor_utc) - finalDaily).toBeGreaterThan(targetDaysMs);
  expect(await page.locator('#cursor-utc').textContent()).toBe(cursorBeforePan);

  await expect(page.locator('#finish')).toBeDisabled();
  for (let step = 0; step < 15; step += 1) {
    const cursor = await page.locator('#cursor-utc').textContent();
    await page.locator('#next').click();
    await expect.poll(() => page.locator('#cursor-utc').textContent()).not.toBe(cursor);
  }
  await page.locator('#final-decision').selectOption('wait');
  await page.locator('textarea[name="notes"]').fill('No trade by the end of the review window.');
  await page.locator('#save').click();
  await expect(page.locator('#decision-count')).toHaveText('2');
  await expect(page.locator('#finish')).toBeEnabled();
  await page.locator('#finish').click();
  await expect.poll(async () => (await (await request.get(replayUrl)).json()).case.status).toBe('finished');
  await page.reload();
  await page.locator('#case-select').selectOption(selected.id);
  await expect(page.locator('#decision-count')).toHaveText('2');
  await expect(page.locator('#case-select option:checked')).toHaveAttribute('data-status', 'finished');
});

test('a slow context response for a previous case never contaminates the one switched to', async ({ page, request }) => {
  await page.route('**/api/**', route => {
    const url = new URL(route.request().url());
    url.port = '8766';
    return route.continue({ url: url.toString() });
  });
  await page.goto('/');

  const cases = await (await request.get(`${api}/api/cases`)).json();
  const eurusd = cases.find((item: { pair: string; status: string }) => item.pair === 'EURUSD' && item.status === 'not_started');
  const usdcad = cases.find((item: { pair: string; status: string }) => item.pair === 'USDCAD' && item.status === 'not_started');
  expect(eurusd).toBeTruthy();
  expect(usdcad).toBeTruthy();

  // The poison candle's time must land inside USDCAD's own default visible
  // window, or Chart's own time-range filter would hide it regardless of
  // whether it actually contaminated state -- so it's computed from USDCAD's
  // real cursor once known, just before the held EURUSD response is released.
  let poisonTime = '';
  let intercepted = false;
  let releaseEurusdResponse = () => {};
  const eurusdGate = new Promise<void>(resolve => { releaseEurusdResponse = resolve; });
  await page.route(`**/api/cases/${eurusd.id}/context*`, async route => {
    intercepted = true;
    await eurusdGate; // held open until the test explicitly releases it, below -- no timing guesswork
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        timeframe: 'h4',
        candles: [{ time: poisonTime, available_at: poisonTime, open: 1, high: 1, low: 1, close: 1, complete: true, integrity: 'complete', gap_slots: [] }],
        next_before: null,
        exhausted: true,
      }),
    });
  });

  await page.locator('#case-select').selectOption(eurusd.id);
  await page.locator('#start').click();
  await expect(page.locator('#next')).toBeEnabled();
  await page.locator('#next').click();
  await expect.poll(() => intercepted).toBe(true); // the slow EURUSD context request is now in flight

  // Switch to USDCAD before that slow EURUSD response arrives.
  await page.locator('#case-select').selectOption(usdcad.id);
  await page.locator('#start').click();
  await expect(page.locator('#next')).toBeEnabled();
  const usdcadStart = await page.locator('#cursor-utc').textContent();
  await page.locator('#next').click();
  await expect.poll(() => page.locator('#cursor-utc').textContent()).not.toBe(usdcadStart);
  const usdcadCursor = await page.locator('#cursor-utc').textContent();
  poisonTime = new Date(Date.parse(usdcadCursor!) - 2 * 60 * 60 * 1000).toISOString().replace('Z', '+00:00');

  // USDCAD is now fully active and settled; only now let the held EURUSD
  // response land, proving the race is resolved regardless of machine speed.
  const eurusdResponse = page.waitForResponse(resp => resp.url().includes(`/cases/${eurusd.id}/context`));
  releaseEurusdResponse();
  await eurusdResponse;
  await page.waitForTimeout(300); // let the resolved promise's .then/setState chain flush

  expect(await page.locator('#cursor-utc').textContent()).toBe(usdcadCursor);
  const h4Times = await page.locator('#h4-chart g[data-time]').evaluateAll(nodes => nodes.map(n => n.getAttribute('data-time')));
  expect(h4Times).not.toContain(poisonTime);

  // The user can still request further USDCAD pages (the stale response must not
  // have left this case's fetching flag permanently stuck).
  for (let i = 0; i < 4; i += 1) await page.locator('button[data-action="zoom-out"][data-chart="h4"]').click();
  const beforeOldest = await page.locator('#h4-chart g[data-time]').evaluateAll(nodes => nodes.map(n => n.getAttribute('data-time')));
  await page.locator('button[data-action="pan-earlier"][data-chart="h4"]').click();
  await expect.poll(async () => {
    const after = await page.locator('#h4-chart g[data-time]').evaluateAll(nodes => nodes.map(n => n.getAttribute('data-time')));
    return after.length !== beforeOldest.length || after.some(t => !beforeOldest.includes(t!));
  }, { timeout: 10000 }).toBe(true);
});

test('switching cases clears an unsaved annotation draft and the manual price marker', async ({ page, request }) => {
  await page.route('**/api/**', route => {
    const url = new URL(route.request().url());
    url.port = '8766';
    return route.continue({ url: url.toString() });
  });
  await page.goto('/');

  const cases = await (await request.get(`${api}/api/cases`)).json();
  const eurusd = cases.find((item: { pair: string; status: string }) => item.pair === 'EURUSD' && item.status === 'not_started');
  const usdcad = cases.find((item: { pair: string; status: string }) => item.pair === 'USDCAD' && item.status === 'not_started');
  expect(eurusd).toBeTruthy();
  expect(usdcad).toBeTruthy();

  await page.locator('#case-select').selectOption(eurusd.id);
  await page.locator('#start').click();
  await expect(page.locator('#next')).toBeEnabled();

  // A saved EURUSD annotation, to prove switching never deletes it.
  await page.locator('#annotation-type').selectOption('horizontal_level');
  await page.locator('#annotation-price').fill('1.23456');
  await page.locator('#save-annotation').click();
  await expect(page.locator('#annotation-count')).toHaveText('1');

  // An UNSAVED EURUSD draft: a historical H4 candle selected, a price and a
  // documented level type typed, plus the manual price marker -- none saved.
  await page.locator('#annotation-type').selectOption('key_level');
  await page.locator('#arm-annotation-source').click();
  await page.locator('#h4-chart g[data-time]').first().click();
  await page.locator('#annotation-price').fill('1.3579');
  await page.locator('#annotation-level-type').fill('Order Block (unsaved draft)');
  await page.locator('#manual-price').fill('1.4242');
  await expect(page.locator('#arm-annotation-source')).toHaveAttribute('data-state', 'selected');

  // Switch to USDCAD before saving any of that.
  await page.locator('#case-select').selectOption(usdcad.id);
  await page.locator('#start').click();
  await expect(page.locator('#next')).toBeEnabled();

  await expect(page.locator('#annotation-price')).toHaveValue('');
  await expect(page.locator('#manual-price')).toHaveValue('');
  // key_level is the panel's default type, so the level-type field is visible again.
  await expect(page.locator('#annotation-level-type')).toHaveValue('');
  await expect(page.locator('#arm-annotation-source')).toHaveAttribute('data-state', 'idle');
  await expect(page.locator('#annotation-count')).toHaveText('0');

  // USDCAD can still create its own annotation.
  await page.locator('#annotation-type').selectOption('horizontal_level');
  await page.locator('#annotation-price').fill('1.11111');
  await page.locator('#save-annotation').click();
  await expect(page.locator('#annotation-count')).toHaveText('1');

  // EURUSD's saved annotation from earlier is untouched.
  const eurusdReplay = await (await request.get(`${api}/api/cases/${eurusd.id}/replay`)).json();
  expect(eurusdReplay.annotations).toHaveLength(1);
  expect(eurusdReplay.annotations[0].price).toBe(1.23456);
});

test('an unavailable API reports its 502 error clearly', async ({ page }) => {
  await page.route('**/api/cases', route => route.fulfill({
    status: 502,
    contentType: 'text/plain',
    body: 'Bad Gateway',
  }));
  await page.goto('/');
  await expect(page.locator('#notice')).toContainText('502');
});
