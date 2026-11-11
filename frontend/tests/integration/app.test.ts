import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { initApp, renderApp } from '../../src/main';
import { t } from '../../src/i18n';
import type { CountyClearanceSummary } from '../../src/services/clearanceData';
import * as clearanceDataService from '../../src/services/clearanceData';

describe('App Integration', () => {
  let root: HTMLElement;
  const sampleSummaries: CountyClearanceSummary[] = [
    { county: 'Abbeville', added: 100, disposed: 22, clearanceRate: 0.22 },
    { county: 'Charleston', added: 100, disposed: 104, clearanceRate: 1.04 },
  ];

  beforeEach(() => {
    root = document.createElement('div');
    root.id = 'app';
    document.body.appendChild(root);
  });

  afterEach(() => {
    root.remove();
    vi.restoreAllMocks();
  });

  it('renders the complete clearance rates application', () => {
    renderApp(root, { summaries: sampleSummaries });

    expect(root.querySelector('h1')?.textContent).toBe(t('pageTitle'));
    expect(root.querySelector('svg.choropleth-svg')).not.toBeNull();
    expect(root.querySelector('table.clearance-table')).not.toBeNull();
  });

  it('initializes app, loads data, and renders aggregated summaries', async () => {
    vi.spyOn(clearanceDataService, 'loadGoldCaseloadRecords').mockResolvedValueOnce([
      {
        file: 'test.csv',
        category: 'Estate',
        year: 2025,
        month: 7,
        county: 'Abbeville',
        metric: 'Added',
        value: 10,
      },
      {
        file: 'test.csv',
        category: 'Estate',
        year: 2025,
        month: 7,
        county: 'Abbeville',
        metric: 'Disposed',
        value: 10,
      },
    ]);

    await initApp(root);

    expect(root.querySelector('.county-name-cell')?.textContent).toBe('Abbeville');
    expect(root.querySelector('.county-rate-cell')?.textContent).toBe('100%');
  });

  it('displays an error banner when data loading fails', async () => {
    vi.spyOn(clearanceDataService, 'loadGoldCaseloadRecords').mockRejectedValueOnce(
      new Error('Network error'),
    );

    await initApp(root);

    const errorBanner = root.querySelector('.error-banner');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.textContent).toBe(t('errorLoadingData'));
  });

  it('reloads map and table when date range selector is changed across multi-year data', async () => {
    vi.spyOn(clearanceDataService, 'loadGoldCaseloadRecords').mockResolvedValueOnce([
      // 2024-2025 records
      {
        file: 'test.csv',
        category: 'Estate',
        year: 2024,
        month: 8,
        county: 'Abbeville',
        metric: 'Added',
        value: 100,
      },
      {
        file: 'test.csv',
        category: 'Estate',
        year: 2024,
        month: 8,
        county: 'Abbeville',
        metric: 'Disposed',
        value: 89,
      },
      // 2023-2024 records
      {
        file: 'test.csv',
        category: 'Estate',
        year: 2023,
        month: 8,
        county: 'Abbeville',
        metric: 'Added',
        value: 50,
      },
      {
        file: 'test.csv',
        category: 'Estate',
        year: 2023,
        month: 8,
        county: 'Abbeville',
        metric: 'Disposed',
        value: 69,
      },
    ]);

    await initApp(root);

    const startSelect = root.querySelector<HTMLSelectElement>(
      'select[aria-label*="start" i], select[name="startDate"], select#start-date',
    );
    const endSelect = root.querySelector<HTMLSelectElement>(
      'select[aria-label*="end" i], select[name="endDate"], select#end-date',
    );

    expect(startSelect).not.toBeNull();
    expect(endSelect).not.toBeNull();

    // Select 2023-2024
    if (startSelect && endSelect) {
      startSelect.value = '2023-07';
      startSelect.dispatchEvent(new Event('change', { bubbles: true }));
      endSelect.value = '2024-06';
      endSelect.dispatchEvent(new Event('change', { bubbles: true }));

      // Abbeville rate for 2023-2024 is 138%
      expect(root.querySelector('.county-name-cell')?.textContent).toBe('Abbeville');
      expect(root.querySelector('.county-rate-cell')?.textContent).toBe('138%');
    }
  });

  it('disables date selectors and indicates no records found when data is empty', async () => {
    vi.spyOn(clearanceDataService, 'loadGoldCaseloadRecords').mockResolvedValueOnce([]);

    await initApp(root);

    const startSelect = root.querySelector<HTMLSelectElement>(
      'select[aria-label*="start" i], select[name="startDate"], select#start-date',
    );
    const endSelect = root.querySelector<HTMLSelectElement>(
      'select[aria-label*="end" i], select[name="endDate"], select#end-date',
    );

    expect(startSelect?.disabled).toBe(true);
    expect(endSelect?.disabled).toBe(true);
    expect(root.textContent).toMatch(/no records found/i);
  });
});
