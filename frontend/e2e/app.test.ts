import { describe, it, expect, beforeEach } from 'vitest';
import { renderApp } from '../src/main';
import { t } from '../src/i18n';
import {
  ClearanceStatus,
  getClearanceStatus,
} from '../src/constants/clearanceThresholds';
import {
  aggregateClearanceRates,
  type CountyClearanceSummary,
  type GoldCaseloadRecord,
} from '../src/services/clearanceData';

const SAMPLE_SUMMARIES: CountyClearanceSummary[] = [
  { county: 'Abbeville', added: 100, disposed: 22, clearanceRate: 0.22 },
  { county: 'Aiken', added: 100, disposed: 88, clearanceRate: 0.88 },
  { county: 'Charleston', added: 100, disposed: 104, clearanceRate: 1.04 },
];

describe('SC County Clearance Rates Page', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="app"></div>';
  });

  it('renders the title, legend, and static date range banner', () => {
    const root = document.getElementById('app') as HTMLElement;
    renderApp(root, {
      summaries: SAMPLE_SUMMARIES,
      dateRange: {
        start: { year: 2025, month: 7 },
        end: { year: 2026, month: 6 },
      },
    });

    const heading = root.querySelector('h1');
    expect(heading?.textContent).toBe(t('pageTitle'));

    const legendItems = Array.from(root.querySelectorAll('.legend-item')).map(
      (el) => el.textContent,
    );
    expect(legendItems).toEqual([
      t('legendGreen'),
      t('legendYellow'),
      t('legendRed'),
    ]);

    const dateBanner = root.querySelector('.date-range-banner');
    expect(dateBanner?.textContent).toBe('July 2025 to June 2026');
  });

  it('renders the TopoJSON -> D3 choropleth SVG map with color status classes', () => {
    const root = document.getElementById('app') as HTMLElement;
    renderApp(root, { summaries: SAMPLE_SUMMARIES });

    const svg = root.querySelector('svg.choropleth-svg');
    expect(svg).not.toBeNull();

    const paths = root.querySelectorAll('path.county-path');
    expect(paths.length).toBe(46);

    const abbevillePath = root.querySelector('path[data-county="Abbeville"]');
    const aikenPath = root.querySelector('path[data-county="Aiken"]');
    const charlestonPath = root.querySelector('path[data-county="Charleston"]');

    expect(abbevillePath?.classList.contains(ClearanceStatus.RED)).toBe(true);
    expect(aikenPath?.classList.contains(ClearanceStatus.YELLOW)).toBe(true);
    expect(charlestonPath?.classList.contains(ClearanceStatus.GREEN)).toBe(true);
    expect(abbevillePath?.getAttribute('d')).toMatch(/^M/);
  });

  it('renders the county clearance rate table with formatted percentages', () => {
    const root = document.getElementById('app') as HTMLElement;
    renderApp(root, { summaries: SAMPLE_SUMMARIES });

    const headers = Array.from(root.querySelectorAll('.clearance-table th')).map(
      (th) => th.textContent,
    );
    expect(headers).toEqual([t('tableHeaderCounty'), t('tableHeaderRate')]);

    const rows = Array.from(root.querySelectorAll('.clearance-table tbody tr')).map(
      (tr) =>
        Array.from(tr.querySelectorAll('td')).map((td) => td.textContent),
    );
    expect(rows).toEqual([
      ['Abbeville', '22%'],
      ['Aiken', '88%'],
      ['Charleston', '104%'],
    ]);
  });
});

describe('Clearance Rate Calculations & Thresholds', () => {
  it('classifies clearance rates into Green, Yellow, Red, and No Data', () => {
    expect(getClearanceStatus(1.04)).toBe(ClearanceStatus.GREEN);
    expect(getClearanceStatus(1.0)).toBe(ClearanceStatus.GREEN);
    expect(getClearanceStatus(0.88)).toBe(ClearanceStatus.YELLOW);
    expect(getClearanceStatus(0.8)).toBe(ClearanceStatus.YELLOW);
    expect(getClearanceStatus(0.22)).toBe(ClearanceStatus.RED);
    expect(getClearanceStatus(null)).toBe(ClearanceStatus.NO_DATA);
  });

  it('aggregates Gold JSON records within the date range and ignores non-numeric values', () => {
    const records: GoldCaseloadRecord[] = [
      {
        file: 'sample.parquet',
        category: 'Estate',
        year: 2025,
        month: 7,
        county: 'Abbeville',
        metric: 'Added',
        value: 50,
      },
      {
        file: 'sample.parquet',
        category: 'Estate',
        year: 2025,
        month: 8,
        county: 'Abbeville',
        metric: 'Added',
        value: 'DNR',
      },
      {
        file: 'sample.parquet',
        category: 'Estate',
        year: 2025,
        month: 7,
        county: 'Abbeville',
        metric: 'Disposed',
        value: 44,
      },
      {
        file: 'sample.parquet',
        category: 'Estate',
        year: 2024,
        month: 6,
        county: 'Abbeville',
        metric: 'Added',
        value: 999,
      },
    ];

    const result = aggregateClearanceRates(records, {
      start: { year: 2025, month: 7 },
      end: { year: 2026, month: 6 },
    });

    expect(result).toEqual([
      {
        county: 'Abbeville',
        added: 50,
        disposed: 44,
        clearanceRate: 0.88,
      },
    ]);
  });
});
