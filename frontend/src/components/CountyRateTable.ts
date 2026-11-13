import {
  DATE_SELECTION_CONSTRAINTS,
  getClearanceStatus,
} from "../constants/clearanceThresholds";
import { t } from "../i18n";
import type {
  CountyClearanceSummary,
  DateRangeFilter,
} from "../services/clearanceData";
import { formatClearanceRate, formatDateRange } from "../utils/formatters";

const TABLE_COL_SPAN = 2;

export function renderCountyRateTable(
  summaries: readonly CountyClearanceSummary[],
  dateRange?: DateRangeFilter,
  loading = false,
): HTMLTableElement {
  const table = document.createElement("table");
  table.className = "clearance-table";

  if (dateRange) {
    const caption = document.createElement("caption");
    caption.className = "table-date-range-caption";
    caption.textContent = loading
      ? t("loadingData")
      : formatDateRange(dateRange.start, dateRange.end);
    table.appendChild(caption);
  }

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");

  const countyHeader = document.createElement("th");
  countyHeader.scope = "col";
  countyHeader.textContent = t("tableHeaderCounty");

  const rateHeader = document.createElement("th");
  rateHeader.scope = "col";
  rateHeader.textContent = t("tableHeaderRate");

  headerRow.append(countyHeader, rateHeader);
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
      const statusClass = getClearanceStatus(item.clearanceRate);
      row.className = `county-row ${statusClass}`;

      const countyCell = document.createElement("td");
      countyCell.className = "county-name-cell";
      countyCell.textContent = item.county;

      const rateCell = document.createElement("td");
      rateCell.className = `county-rate-cell ${statusClass}`;
      rateCell.textContent = formatClearanceRate(item.clearanceRate);

      row.append(countyCell, rateCell);
      tbody.appendChild(row);
    }
  }

  table.append(thead, tbody);
  return table;
}
