import { expect, test } from '@playwright/test';

import { auditEvents, claimDetail, claimSummaries, timelineEntries } from './fixtures';

test.beforeEach(async ({ page }) => {
  await page.route('**/v1/claims?*', async (route) => {
    await route.fulfill({ json: { items: claimSummaries, next_cursor: null } });
  });
  await page.route('**/v1/claims/MER-2026-000101', async (route) => {
    await route.fulfill({ json: claimDetail });
  });
  await page.route('**/v1/claims/MER-2026-000101/timeline', async (route) => {
    await route.fulfill({ json: timelineEntries });
  });
  await page.route('**/v1/claims/MER-2026-000101/audit-events*', async (route) => {
    await route.fulfill({ json: { items: auditEvents, next_cursor: null } });
  });
});

test('a handler can read the queue and open a claim', async ({ page }) => {
  await page.goto('/queue');

  await expect(page.getByRole('heading', { name: 'Claims queue' })).toBeVisible();
  await expect(page.getByRole('table', { name: 'Claims queue' })).toContainText('MER-2026-000101');

  await page.getByRole('link', { name: 'MER-2026-000101' }).click();

  await expect(page.getByRole('heading', { name: 'MER-2026-000101' })).toBeVisible();
  await expect(page.getByLabel('Claim timeline')).toContainText('Claim registered');
  await expect(page.getByLabel('Audit trail')).toContainText('claim.registered');
});

test('the queue filters are applied to the API request', async ({ page }) => {
  await page.goto('/queue');
  await expect(page.getByRole('table', { name: 'Claims queue' })).toBeVisible();

  const request = page.waitForRequest((candidate) => candidate.url().includes('breached=true'));
  await page.getByLabel('Breached only').check();

  expect((await request).url()).toContain('breached=true');
});
