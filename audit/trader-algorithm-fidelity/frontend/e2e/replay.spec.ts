import { test, expect } from '@playwright/test';

const api = 'http://127.0.0.1:8766';

test('a real case stays causal and its human decision survives reload', async ({ page, request }) => {
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

  await page.locator('#final-decision').selectOption('wait');
  await page.locator('textarea[name="notes"]').fill('Browser verification only; not a trader judgment.');
  await page.locator('#save').click();
  await expect(page.locator('#decision-count')).toHaveText('1');
  const saved = await (await request.get(replayUrl)).json();
  expect(saved.decisions[0]).toMatchObject({ case_id: selected.id, decision: 'wait', cursor_utc: after.cursor_utc });

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
  await expect(page.locator('#case-select option:checked')).toContainText('finished');
});

test('an unavailable API reports its 502 error clearly', async ({ page }) => {
  await page.route('**/api/cases', route => route.fulfill({
    status: 502,
    contentType: 'text/plain',
    body: 'Bad Gateway',
  }));
  await page.goto('/');
  await expect(page.locator('#notice')).toContainText('Request failed: 502');
});
