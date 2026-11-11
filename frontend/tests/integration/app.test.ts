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
});
