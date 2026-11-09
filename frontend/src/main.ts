import {
  renderClearancePage,
  type ClearancePageOptions,
} from "./components/ClearancePage";
import { t } from "./i18n";
import {
  aggregateClearanceRates,
  getDefaultDateRange,
  loadGoldCaseloadRecords,
} from "./services/clearanceData";
// @ts-ignore CSS imports are handled by the bundler.
import "./style.css";

export function renderApp(
  rootElement: HTMLElement,
  options?: ClearancePageOptions,
): void {
  renderClearancePage(rootElement, {
    summaries: options?.summaries ?? [],
    dateRange: options?.dateRange ?? getDefaultDateRange(),
    topology: options?.topology,
  });
}

export async function initApp(rootElement: HTMLElement): Promise<void> {
  const dateRange = getDefaultDateRange();
  renderApp(rootElement, { summaries: [], dateRange });

  try {
    const records = await loadGoldCaseloadRecords();
    const summaries = aggregateClearanceRates(records, dateRange);
    renderApp(rootElement, { summaries, dateRange });
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
