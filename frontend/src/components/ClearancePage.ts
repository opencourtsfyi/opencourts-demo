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
import { renderTimeSeriesDrawer } from "./TimeSeriesDrawer";

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
  list.setAttribute("role", "list");

  const items = [
    { status: ClearanceStatus.TIER_1, text: t("legendTier1") },
    { status: ClearanceStatus.TIER_2, text: t("legendTier2") },
    { status: ClearanceStatus.TIER_3, text: t("legendTier3") },
    { status: ClearanceStatus.TIER_4, text: t("legendTier4") },
    {
      status: ClearanceStatus.INSUFFICIENT_DATA,
      text: t("legendInsufficientData"),
    },
  ];

  for (const item of items) {
    const li = document.createElement("li");
    li.className = "legend-item";
    li.setAttribute("role", "listitem");

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
  let lastTriggerElement: HTMLElement | SVGElement | null = null;

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

  let selectorContainer = header.querySelector<DateRangeSelectorElement>(
    ".date-range-selector",
  );
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

  let workspace = main.querySelector<HTMLElement>(".workspace-layout");
  if (!workspace) {
    workspace = document.createElement("div");
    workspace.className = "workspace-layout";
    main.appendChild(workspace);
  }

  let mapSection = workspace.querySelector<HTMLElement>(".map-box");
  if (!mapSection) {
    mapSection = document.createElement("section");
    mapSection.className = "map-box";
    workspace.appendChild(mapSection);
  }

  let drawerSlot = workspace.querySelector<HTMLElement>(".drawer-slot");
  if (!drawerSlot) {
    drawerSlot = document.createElement("div");
    drawerSlot.className = "drawer-slot";
    workspace.appendChild(drawerSlot);
  }

  function updateDrawer(county: string | null, manageFocus = false): void {
    if (!drawerSlot || !workspace) return;
    drawerSlot.replaceChildren();
    if (!county) {
      workspace.classList.remove("has-drawer");
      if (manageFocus && lastTriggerElement) {
        lastTriggerElement.focus();
        lastTriggerElement = null;
      }
      return;
    }

    const summary = summaries.find(
      (s) => s.county.toLowerCase() === county.toLowerCase(),
    ) ?? {
      county,
      added: 0,
      disposed: 0,
      clearanceRate: null,
      isSufficientData: false,
      monthlySeries: [],
    };

    const drawerEl = renderTimeSeriesDrawer(summary, () => {
      syncSelection(null, true);
    });
    drawerSlot.appendChild(drawerEl);
    workspace.classList.add("has-drawer");

    if (manageFocus) {
      const closeBtn =
        drawerEl.querySelector<HTMLButtonElement>(".drawer-close-btn");
      closeBtn?.focus();
    }
  }

  function syncSelection(county: string | null, manageFocus = false): void {
    if (
      county !== null &&
      currentSelectedCounty === null &&
      container.ownerDocument?.activeElement
    ) {
      const active = container.ownerDocument.activeElement;
      if (active instanceof HTMLElement || active instanceof SVGElement) {
        lastTriggerElement = active;
      }
    }
    currentSelectedCounty = county;

    const allPaths =
      mainElement.querySelectorAll<SVGPathElement>("path.county-path");
    for (const path of allPaths) {
      const name = path.getAttribute("data-county") ?? "";
      const isTarget =
        county !== null && name.toLowerCase() === county.toLowerCase();
      if (isTarget) {
        path.classList.add("is-selected");
        path.setAttribute("aria-pressed", "true");
      } else {
        path.classList.remove("is-selected");
        path.setAttribute("aria-pressed", "false");
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

    updateDrawer(county, manageFocus);
    onSelectCounty?.(county);
  }

  mapSection.replaceChildren();
  const mapHeading = document.createElement("h2");
  mapHeading.id = "mapHeading";
  mapHeading.className = "map-heading";
  mapHeading.textContent = t("mapHeading");

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
    (county) => syncSelection(county, true),
    "mapMethodology",
    "mapHeading",
  );
  const legend = createLegend();
  mapSection.append(mapHeading, mapDateRange, svgMap, legend);

  updateDrawer(currentSelectedCounty, false);

  let tableSection = main.querySelector<HTMLElement>(".table-section");
  const wasTableExpanded =
    tableSection
      ?.querySelector<HTMLButtonElement>(".table-toggle-btn")
      ?.getAttribute("aria-expanded") === "true";

  if (!tableSection) {
    tableSection = document.createElement("section");
    tableSection.className = "table-section";
    main.appendChild(tableSection);
  }
  tableSection.replaceChildren();

  const toggleBtn = document.createElement("button");
  toggleBtn.type = "button";
  toggleBtn.className = "table-toggle-btn";
  toggleBtn.setAttribute("aria-controls", "countyTableWrapper");
  toggleBtn.setAttribute("aria-expanded", wasTableExpanded ? "true" : "false");
  toggleBtn.textContent = wasTableExpanded
    ? t("tableToggleHide")
    : t("tableToggleShow");

  const tableWrapper = document.createElement("div");
  tableWrapper.id = "countyTableWrapper";
  tableWrapper.className = "table-wrapper";
  tableWrapper.hidden = !wasTableExpanded;

  toggleBtn.addEventListener("click", () => {
    const nextExpanded = toggleBtn.getAttribute("aria-expanded") !== "true";
    toggleBtn.setAttribute("aria-expanded", nextExpanded ? "true" : "false");
    toggleBtn.textContent = nextExpanded
      ? t("tableToggleHide")
      : t("tableToggleShow");
    tableWrapper.hidden = !nextExpanded;
  });

  const table = renderCountyRateTable(
    summaries,
    dateRange,
    isLoading,
    currentSelectedCounty,
    (county) => syncSelection(county, true),
  );
  tableWrapper.appendChild(table);
  tableSection.append(toggleBtn, tableWrapper);

  let methodologySection = main.querySelector<HTMLElement>(
    ".methodology-section",
  );
  if (!methodologySection) {
    methodologySection = document.createElement("section");
    methodologySection.className = "methodology-section";
    main.appendChild(methodologySection);
  }
  methodologySection.replaceChildren();
  const methodologyHeading = document.createElement("h2");
  methodologyHeading.textContent = t("methodologyHeading");
  const methodologyText = document.createElement("p");
  methodologyText.id = "mapMethodology";
  methodologyText.className = "methodology-text";
  methodologyText.textContent = t("methodologyText");
  methodologySection.append(methodologyHeading, methodologyText);

  const handleOutsideClick = (event: MouseEvent) => {
    const target = event.target as Node | null;
    if (!target) return;
    const isInsideMap = mapSection.contains(target);
    const isInsideTable = tableSection.contains(target);
    const isInsideDrawer = drawerSlot.contains(target);
    if (
      !isInsideMap &&
      !isInsideTable &&
      !isInsideDrawer &&
      currentSelectedCounty !== null
    ) {
      syncSelection(null, false);
    }
  };

  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape" && currentSelectedCounty !== null) {
      syncSelection(null, true);
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
