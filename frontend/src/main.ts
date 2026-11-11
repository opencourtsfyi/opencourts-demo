import { DATE_SELECTION_CONSTRAINTS } from "./constants/clearanceThresholds";
import {
  renderClearancePage,
  type ClearancePageOptions,
} from "./components/ClearancePage";
import { t } from "./i18n";
import {
  aggregateClearanceRates,
  getDataDateBounds,
  getDefaultDateRange,
  loadGoldCaseloadRecords,
  type DateRangeFilter,
  type GoldCaseloadRecord,
} from "./services/clearanceData";
import { compareYearMonth } from "./utils/formatters";
// @ts-ignore CSS imports are handled by the bundler.
import "./style.css";

export function renderApp(
  rootElement: HTMLElement,
  options?: ClearancePageOptions,
): void {
  renderClearancePage(rootElement, {
    summaries: options?.summaries ?? [],
    dateRange: options?.dateRange ?? getDefaultDateRange(),
    availableRange: options?.availableRange,
    disabled: options?.disabled,
    loading: options?.loading,
    topology: options?.topology,
    onDateRangeChange: options?.onDateRangeChange,
    selectedCounty: options?.selectedCounty,
    onSelectCounty: options?.onSelectCounty,
  });
}

export async function initApp(rootElement: HTMLElement): Promise<void> {
  let currentDateRange: DateRangeFilter = getDefaultDateRange();
  let loadedRecords: GoldCaseloadRecord[] = [];
  let availableRange: DateRangeFilter | undefined;

  function updateView(): void {
    const isDataEmpty =
      loadedRecords.length === DATE_SELECTION_CONSTRAINTS.EMPTY_COUNT;
    const summaries = aggregateClearanceRates(loadedRecords, currentDateRange);
    renderClearancePage(rootElement, {
      summaries,
      dateRange: currentDateRange,
      availableRange,
      disabled: isDataEmpty,
      onDateRangeChange: (newRange) => {
        currentDateRange = newRange;
        updateView();
      },
    });
  }

  renderApp(rootElement, {
    summaries: [],
    dateRange: currentDateRange,
    loading: true,
  });

  try {
    loadedRecords = await loadGoldCaseloadRecords();
    const bounds = getDataDateBounds(loadedRecords);
    if (bounds) {
      availableRange = bounds;
      if (
        compareYearMonth(currentDateRange.start, bounds.start) < 0 ||
        compareYearMonth(currentDateRange.end, bounds.end) > 0 ||
        compareYearMonth(currentDateRange.start, bounds.end) > 0 ||
        compareYearMonth(currentDateRange.end, bounds.start) < 0
      ) {
        currentDateRange = { ...bounds };
      }
    }
    updateView();
  } catch {
    const errorBanner = document.createElement("p");
    errorBanner.className = "error-banner";
    errorBanner.textContent = t("errorLoadingData");
    rootElement.appendChild(errorBanner);
  }
}

const appContainer = document.querySelector<HTMLElement>("#app");
if (appContainer) {
  void initApp(appContainer);
}
