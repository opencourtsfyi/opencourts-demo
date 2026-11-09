import { getClearanceStatus } from "../constants/clearanceThresholds";
import { t } from "../i18n";
import type { CountyClearanceSummary } from "../services/clearanceData";
import { formatClearanceRate } from "../utils/formatters";

export function renderCountyRateTable(
  summaries: readonly CountyClearanceSummary[],
): HTMLTableElement {
  const table = document.createElement("table");
  table.className = "clearance-table";

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

  table.append(thead, tbody);
  return table;
}
