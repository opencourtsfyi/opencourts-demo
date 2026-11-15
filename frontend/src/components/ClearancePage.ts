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
import { formatDateRange } from "../utils/formatters";
import { renderChoroplethMap, type ScTopology } from "./ChoroplethMap";
import { renderCountyRateTable } from "./CountyRateTable";
import {
  renderDateRangeSelector,
  updateDateRangeSelector,
  type DateRangeSelectorElement,
} from "./DateRangeSelector";

export interface ClearancePageOptions {
  summaries: readonly CountyClearanceSummary[];
  dateRange?: DateRangeFilter;
  availableRange?: DateRangeFilter;
  disabled?: boolean;
  loading?: boolean;
  topology?: ScTopology;
  onDateRangeChange?: (newRange: DateRangeFilter) => void;
  selectedCounty?: string | null;
  onSelectCounty?: (county: string | null) => void;
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
    selectedCounty: initialSelectedCounty = null,
    onSelectCounty,
  } = options;

  const isLoading = options.loading ?? false;
  let currentSelectedCounty: string | null = initialSelectedCounty;

  const isDataEmpty =
    !isLoading &&
    (options.disabled ??
      (summaries.length === DATE_SELECTION_CONSTRAINTS.EMPTY_COUNT &&
        !options.availableRange));
  const isSelectorDisabled = isLoading || isDataEmpty;

  let main = container.querySelector<HTMLElement>(".clearance-page");
  if (!main) {
    main = document.createElement("main");
    main.className = "clearance-page";
    container.replaceChildren(main);
  }
  const mainElement = main;

  function syncSelection(county: string | null): void {
    currentSelectedCounty = county;

    const allPaths =
      mainElement.querySelectorAll<SVGPathElement>("path.county-path");
    for (const path of allPaths) {
      const name = path.getAttribute("data-county") ?? "";
      const isTarget =
        county !== null && name.toLowerCase() === county.toLowerCase();
      if (isTarget) {
        path.classList.add("is-selected");
        path.setAttribute("aria-selected", "true");
      } else {
        path.classList.remove("is-selected");
        path.setAttribute("aria-selected", "false");
      }
    }

    const allRows =
      mainElement.querySelectorAll<HTMLTableRowElement>("tr.county-row");
    for (const row of allRows) {
      const name =
        row.getAttribute("data-county") ??
        row.querySelector(".county-name-cell")?.textContent ??
        "";
      const isTarget =
        county !== null && name.toLowerCase() === county.toLowerCase();
      if (isTarget) {
        row.classList.add("is-selected");
        row.setAttribute("aria-selected", "true");
      } else {
        row.classList.remove("is-selected");
        row.setAttribute("aria-selected", "false");
      }
    }

    onSelectCounty?.(county);
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

  let selectorContainer =
    header.querySelector<DateRangeSelectorElement>(".date-range-selector");
  if (!selectorContainer) {
    selectorContainer = renderDateRangeSelector({
      availableRange,
      selectedRange: dateRange,
      disabled: isSelectorDisabled,
      loading: isLoading,
      onDateRangeChange,
    });
    header.appendChild(selectorContainer);
  } else {
    updateDateRangeSelector(selectorContainer, {
      availableRange,
      selectedRange: dateRange,
      disabled: isSelectorDisabled,
      loading: isLoading,
      onDateRangeChange,
    });
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
  mapDateRange.textContent = isLoading
    ? t("loadingData")
    : formatDateRange(dateRange.start, dateRange.end);
  const svgMap = renderChoroplethMap(
    summaries,
    topology,
    dateRange,
    currentSelectedCounty,
    (county) => syncSelection(county),
  );
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
  const table = renderCountyRateTable(
    summaries,
    dateRange,
    isLoading,
    currentSelectedCounty,
    (county) => syncSelection(county),
  );
  tableSection.append(tableDateRange, table);

  const handleOutsideClick = (event: MouseEvent) => {
    const target = event.target as Node | null;
    if (!target) return;
    const isInsideMap = mapSection.contains(target);
    const isInsideTable = tableSection.contains(target);
    if (!isInsideMap && !isInsideTable && currentSelectedCounty !== null) {
      syncSelection(null);
    }
  };

  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape" && currentSelectedCounty !== null) {
      syncSelection(null);
    }
  };

  const doc = container.ownerDocument;
  const containerWithListener = container as HTMLElement & {
    _outsideClickListener?: (e: MouseEvent) => void;
    _docClickListener?: (e: MouseEvent) => void;
    _keyDownListener?: (e: KeyboardEvent) => void;
    _docKeyDownListener?: (e: KeyboardEvent) => void;
  };
  if (containerWithListener._outsideClickListener) {
    container.removeEventListener(
      "click",
      containerWithListener._outsideClickListener,
    );
  }
  if (containerWithListener._docClickListener && doc) {
    doc.removeEventListener("click", containerWithListener._docClickListener);
  }
  if (containerWithListener._keyDownListener) {
    container.removeEventListener(
      "keydown",
      containerWithListener._keyDownListener,
    );
  }
  if (containerWithListener._docKeyDownListener && doc) {
    doc.removeEventListener(
      "keydown",
      containerWithListener._docKeyDownListener,
    );
  }

  containerWithListener._outsideClickListener = handleOutsideClick;
  container.addEventListener("click", handleOutsideClick);
  containerWithListener._keyDownListener = handleKeyDown;
  container.addEventListener("keydown", handleKeyDown);
  if (doc) {
    containerWithListener._docClickListener = handleOutsideClick;
    doc.addEventListener("click", handleOutsideClick);
    containerWithListener._docKeyDownListener = handleKeyDown;
    doc.addEventListener("keydown", handleKeyDown);
  }
}
