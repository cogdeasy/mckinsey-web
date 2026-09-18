import { describe, expect, it } from 'vitest';

import { formatDateTime, formatMoney, humanise } from './format';

describe('formatting helpers', () => {
  it('renders minor units as major units', () => {
    expect(formatMoney(480_000, 'GBP')).toBe('£4,800.00');
    expect(formatMoney(0, 'EUR')).toBe('€0.00');
  });

  it('renders timestamps in UTC', () => {
    expect(formatDateTime('2026-09-14T09:30:00Z')).toBe('14 Sept 2026, 09:30');
    expect(formatDateTime(null)).toBe('Not set');
  });

  it('humanises enumerations', () => {
    expect(humanise('SPECIAL_INVESTIGATION')).toBe('Special Investigation');
  });
});
