import {
  ClearanceStatus,
  DATE_SELECTION_CONSTRAINTS,
} from "../constants/clearanceThresholds";
import { t } from "../i18n";
import {
  getDefaultDateRange,
  type CountyClearanceSummary,
  type DateRangeFilter,
} from "../services/clearanceData";
import { formatDateRange, toYearMonthValue } from "../utils/formatters";
import { renderChoroplethMap, type ScTopology } from "./ChoroplethMap";
import { renderCountyRateTable } from "./CountyRateTable";
import { renderDateRangeSelector } from "./DateRangeSelector";

export interface ClearancePageOptions {
  summaries: readonly CountyClearanceSummary[];
  dateRange?: DateRangeFilter;
  availableRange?: DateRangeFilter;
  disabled?: boolean;
  topology?: ScTopology;
  onDateRangeChange?: (newRange: DateRangeFilter) => void;
}

const DEFAULT_AVAILABLE_RANGE: DateRangeFilter = {
  start: { year: 2023, month: 7 },
  end: { year: 2026, month: 6 },
};

function createLegend(): HTMLElement {
  const legendContainer = document.createElement("div");
  legendContainer.className = "clearance-legend";

  const prefix = document.createElement("span");
  prefix.className = "legend-label";
  prefix.textContent = t("legendLabel");
  legendContainer.appendChild(prefix);

  const list = document.createElement("ul");
  list.className = "legend-list";

  const items = [
    { status: ClearanceStatus.GREEN, text: t("legendGreen") },
    { status: ClearanceStatus.YELLOW, text: t("legendYellow") },
    { status: ClearanceStatus.RED, text: t("legendRed") },
    { status: ClearanceStatus.NO_DATA, text: t("legendNoData") },
  ];

  for (const item of items) {
    const li = document.createElement("li");
    li.className = "legend-item";

    const swatch = document.createElement("span");
    swatch.className = `legend-swatch ${item.status}`;
    swatch.setAttribute("aria-hidden", "true");

    const label = document.createElement("span");
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
  const {
    summaries,
    dateRange = getDefaultDateRange(),
    availableRange = DEFAULT_AVAILABLE_RANGE,
    topology,
    onDateRangeChange,
  } = options;

  const isDataEmpty =
    options.disabled ??
    (summaries.length === DATE_SELECTION_CONSTRAINTS.EMPTY_COUNT &&
      !options.availableRange);

  let main = container.querySelector<HTMLElement>(".clearance-page");
  if (!main) {
    main = document.createElement("main");
    main.className = "clearance-page";
    container.replaceChildren(main);
  }

  let header = main.querySelector<HTMLElement>(".clearance-header");
  if (!header) {
    header = document.createElement("header");
    header.className = "clearance-header";
    main.appendChild(header);
  }

  let heading = header.querySelector("h1");
  if (!heading) {
    heading = document.createElement("h1");
    heading.textContent = t("pageTitle");
    header.appendChild(heading);
  }

  if (!header.querySelector(".clearance-legend")) {
    header.appendChild(createLegend());
  }

  let selectorContainer = header.querySelector<
    HTMLElement & { _onDateRangeChange?: (r: DateRangeFilter) => void }
  >(".date-range-selector");
  if (!selectorContainer) {
    selectorContainer = renderDateRangeSelector({
      availableRange,
      selectedRange: dateRange,
      disabled: isDataEmpty,
      onDateRangeChange,
    });
    header.appendChild(selectorContainer);
  } else {
    selectorContainer._onDateRangeChange = onDateRangeChange;
    const startSelect =
      selectorContainer.querySelector<HTMLSelectElement>("#start-date");
    const endSelect =
      selectorContainer.querySelector<HTMLSelectElement>("#end-date");
    if (startSelect && endSelect) {
      startSelect.disabled = isDataEmpty;
      endSelect.disabled = isDataEmpty;
      startSelect.value = toYearMonthValue(dateRange.start);
      endSelect.value = toYearMonthValue(dateRange.end);
    }
  }

  let emptyNotice =
    header.querySelector<HTMLParagraphElement>(".no-records-notice");
  if (isDataEmpty) {
    if (!emptyNotice) {
      emptyNotice = document.createElement("p");
      emptyNotice.className = "no-records-notice";
      emptyNotice.textContent = t("noRecordsFound");
      header.appendChild(emptyNotice);
    }
  } else if (emptyNotice) {
    emptyNotice.remove();
  }

  let mapSection = main.querySelector<HTMLElement>(".map-box");
  if (!mapSection) {
    mapSection = document.createElement("section");
    mapSection.className = "map-box";
    main.appendChild(mapSection);
  }
  mapSection.replaceChildren();
  const mapDateRange = document.createElement("p");
  mapDateRange.className = "map-date-range";
  mapDateRange.textContent = formatDateRange(dateRange.start, dateRange.end);
  const svgMap = renderChoroplethMap(summaries, topology, dateRange);
  mapSection.append(mapDateRange, svgMap);

  const tableSection =
    main.querySelector<HTMLElement>(".table-section") ??
    document.createElement("section");
  tableSection.className = "table-section";
  if (!main.contains(tableSection)) {
    main.appendChild(tableSection);
  }
  tableSection.replaceChildren();
  const tableDateRange = document.createElement("p");
  // tableDateRange.className = "table-date-range";
  // tableDateRange.textContent = formatDateRange(dateRange.start, dateRange.end);
  const table = renderCountyRateTable(summaries, dateRange);
  tableSection.append(tableDateRange, table);
}
