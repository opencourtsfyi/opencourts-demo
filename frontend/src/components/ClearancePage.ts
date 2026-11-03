import { ClearanceStatus } from '../constants/clearanceThresholds';
import { t } from '../i18n';
import {
  getDefaultDateRange,
  type CountyClearanceSummary,
  type DateRangeFilter,
} from '../services/clearanceData';
import { formatDateRange } from '../utils/formatters';
import { renderChoroplethMap, type ScTopology } from './ChoroplethMap';
import { renderCountyRateTable } from './CountyRateTable';

export interface ClearancePageOptions {
  summaries: readonly CountyClearanceSummary[];
  dateRange?: DateRangeFilter;
  topology?: ScTopology;
}

function createLegend(): HTMLElement {
  const legendContainer = document.createElement('div');
  legendContainer.className = 'clearance-legend';

  const prefix = document.createElement('span');
  prefix.className = 'legend-label';
  prefix.textContent = t('legendLabel');
  legendContainer.appendChild(prefix);

  const list = document.createElement('ul');
  list.className = 'legend-list';

  const items = [
    { status: ClearanceStatus.GREEN, text: t('legendGreen') },
    { status: ClearanceStatus.YELLOW, text: t('legendYellow') },
    { status: ClearanceStatus.RED, text: t('legendRed') },
  ];

  for (const item of items) {
    const li = document.createElement('li');
    li.className = 'legend-item';

    const swatch = document.createElement('span');
    swatch.className = `legend-swatch ${item.status}`;
    swatch.setAttribute('aria-hidden', 'true');

    const label = document.createElement('span');
    label.textContent = item.text;

    li.append(swatch, label);
    list.appendChild(li);
  }

  legendContainer.appendChild(list);
  return legendContainer;
}

export function renderClearancePage(
  container: HTMLElement,
  options: ClearancePageOptions,
): void {
  const { summaries, dateRange = getDefaultDateRange(), topology } = options;

  const main = document.createElement('main');
  main.className = 'clearance-page';

  const header = document.createElement('header');
  header.className = 'clearance-header';

  const heading = document.createElement('h1');
  heading.textContent = t('pageTitle');

  const legend = createLegend();

  const dateRangeBanner = document.createElement('p');
  dateRangeBanner.className = 'date-range-banner';
  dateRangeBanner.textContent = formatDateRange(dateRange.start, dateRange.end);

  header.append(heading, legend, dateRangeBanner);

  const mapSection = document.createElement('section');
  mapSection.className = 'map-box';
  const svgMap = renderChoroplethMap(summaries, topology);
  mapSection.appendChild(svgMap);

  const tableSection = document.createElement('section');
  tableSection.className = 'table-section';
  const table = renderCountyRateTable(summaries);
  tableSection.appendChild(table);

  main.append(header, mapSection, tableSection);
  container.replaceChildren(main);
}
