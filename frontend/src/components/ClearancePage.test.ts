import { describe, it, expect, beforeEach } from 'vitest';
import { renderClearancePage } from './ClearancePage';
import { t } from '../i18n';
import type { CountyClearanceSummary } from '../services/clearanceData';

describe('ClearancePage component', () => {
  let root: HTMLElement;
  const sampleSummaries: CountyClearanceSummary[] = [
    { county: 'Abbeville', added: 100, disposed: 22, clearanceRate: 0.22 },
    { county: 'Aiken', added: 100, disposed: 88, clearanceRate: 0.88 },
  ];

  beforeEach(() => {
    root = document.createElement('div');
  });

  it('renders page header, title, and date banner', () => {
    renderClearancePage(root, {
      summaries: sampleSummaries,
      dateRange: {
        start: { year: 2025, month: 7 },
        end: { year: 2026, month: 6 },
      },
    });

    const heading = root.querySelector('h1');
    expect(heading?.textContent).toBe(t('pageTitle'));

    const banner = root.querySelector('.date-range-banner');
    expect(banner?.textContent).toBe('July 2025 to June 2026');
  });

  it('renders the color legend with swatch indicators', () => {
    renderClearancePage(root, { summaries: sampleSummaries });

    const legendItems = Array.from(root.querySelectorAll('.legend-item')).map(
      (el) => el.textContent,
    );
    expect(legendItems).toEqual([
      t('legendGreen'),
      t('legendYellow'),
      t('legendRed'),
      t('legendNoData'),
    ]);

    expect(root.querySelector('.legend-swatch.status-green')).not.toBeNull();
    expect(root.querySelector('.legend-swatch.status-yellow')).not.toBeNull();
    expect(root.querySelector('.legend-swatch.status-red')).not.toBeNull();
  });

  it('renders both the map and table inside the layout container', () => {
    renderClearancePage(root, { summaries: sampleSummaries });

    expect(root.querySelector('.map-box svg.choropleth-svg')).not.toBeNull();
    expect(root.querySelector('.table-section table.clearance-table')).not.toBeNull();
  });
});
