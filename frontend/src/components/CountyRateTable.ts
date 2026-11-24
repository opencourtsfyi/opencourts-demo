import {
  COMPLETENESS_CONFIG,
  CompletenessTier,
  DATE_SELECTION_CONSTRAINTS,
  getClearanceStatus,
} from "../constants/clearanceThresholds";
import { t } from "../i18n";
import type {
  CountyClearanceSummary,
  DateRangeFilter,
} from "../services/clearanceData";
import { formatClearanceRate, formatDateRange } from "../utils/formatters";

const TABLE_COL_SPAN = 4;

function getCompletenessText(item: CountyClearanceSummary): string {
  switch (item.completenessTier) {
    case CompletenessTier.COMPLETE:
      return t("completenessComplete");
    case CompletenessTier.PARTIAL:
      return t("completenessPartial");
    case CompletenessTier.INSUFFICIENT:
      return t("completenessInsufficient");
    default:
      return item.clearanceRate !== null
        ? t("completenessComplete")
        : t("completenessInsufficient");
  }
}

export function renderCountyRateTable(
  summaries: readonly CountyClearanceSummary[],
  dateRange?: DateRangeFilter,
  loading = false,
  selectedCounty?: string | null,
  onSelectCounty?: (county: string | null) => void,
): HTMLTableElement {
  const table = document.createElement("table");
  table.className = "clearance-table";

  const caption = document.createElement("caption");
  caption.className = "table-date-range-caption";
  if (loading) {
    caption.textContent = t("loadingData");
  } else if (dateRange) {
    caption.textContent = `${t("pageTitle")} (${formatDateRange(dateRange.start, dateRange.end)})`;
  } else {
    caption.textContent = t("pageTitle");
  }
  table.appendChild(caption);

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");

  const countyHeader = document.createElement("th");
  countyHeader.scope = "col";
  countyHeader.textContent = t("tableHeaderCounty");

  const rateHeader = document.createElement("th");
  rateHeader.scope = "col";
  rateHeader.textContent = t("tableHeaderRate");

  const completenessHeader = document.createElement("th");
  completenessHeader.scope = "col";
  completenessHeader.textContent = t("tableHeaderCompleteness");

  const periodsHeader = document.createElement("th");
  periodsHeader.scope = "col";
  periodsHeader.textContent = t("tableHeaderReportedPeriods");

  headerRow.append(countyHeader, rateHeader, completenessHeader, periodsHeader);
  thead.appendChild(headerRow);

  const tbody = document.createElement("tbody");
  if (summaries.length === DATE_SELECTION_CONSTRAINTS.EMPTY_COUNT) {
    if (!loading) {
      const emptyRow = document.createElement("tr");
      emptyRow.className = "empty-table-row";
      const emptyCell = document.createElement("td");
      emptyCell.colSpan = TABLE_COL_SPAN;
      emptyCell.className = "empty-table-cell";
      emptyCell.textContent = t("noRecordsFound");
      emptyRow.appendChild(emptyCell);
      tbody.appendChild(emptyRow);
    }
  } else {
    for (const item of summaries) {
      const row = document.createElement("tr");
      const isSufficient = item.isSufficientData ?? item.clearanceRate !== null;
      const statusClass = getClearanceStatus(item.clearanceRate, isSufficient);
      const isSelected = Boolean(
        selectedCounty &&
        item.county.toLowerCase() === selectedCounty.toLowerCase(),
      );
      row.className = `county-row ${statusClass}${isSelected ? " is-selected" : ""}`;
      row.setAttribute("data-county", item.county);
      row.tabIndex = 0;
      row.setAttribute("aria-selected", isSelected ? "true" : "false");

      const triggerSelect = () => {
        const willSelect = !row.classList.contains("is-selected");
        const nextSelected = willSelect ? item.county : null;
        onSelectCounty?.(nextSelected);
        row.dispatchEvent(
          new CustomEvent("countySelected", {
            bubbles: true,
            detail: { county: nextSelected },
          }),
        );
      };

      row.addEventListener("click", () => {
        triggerSelect();
      });

      row.addEventListener("keydown", (event: KeyboardEvent) => {
        if (event.key === "Escape") {
          onSelectCounty?.(null);
          row.dispatchEvent(
            new CustomEvent("countySelected", {
              bubbles: true,
              detail: { county: null },
            }),
          );
          return;
        }
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          triggerSelect();
        }
      });

      const countyCell = document.createElement("th");
      countyCell.scope = "row";
      countyCell.className = "county-name-cell";
      countyCell.textContent = item.county;

      const rateCell = document.createElement("td");
      rateCell.className = `county-rate-cell ${statusClass}`;
      rateCell.textContent = isSufficient
        ? formatClearanceRate(item.clearanceRate)
        : t("insufficientDataLabel");

      const completenessCell = document.createElement("td");
      completenessCell.className = "county-completeness-cell";
      completenessCell.textContent = getCompletenessText(item);

      const periodsCell = document.createElement("td");
      periodsCell.className = "county-periods-cell";
      if (item.totalPeriods !== undefined) {
        const reported = item.reportedPeriods ?? 0;
        const pct = Math.round(
          (item.completenessRatio ?? 0) *
            COMPLETENESS_CONFIG.PERCENT_MULTIPLIER,
        );
        periodsCell.textContent = `${reported}/${item.totalPeriods} (${pct}%)`;
      } else {
        periodsCell.textContent = t("noDataLabel");
      }

      row.append(countyCell, rateCell, completenessCell, periodsCell);
      tbody.appendChild(row);
    }
  }

  table.append(thead, tbody);
  return table;
}
