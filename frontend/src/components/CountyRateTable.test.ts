import { describe, it, expect } from "vitest";
import { renderCountyRateTable } from "./CountyRateTable";
import { t } from "../i18n";
import type { CountyClearanceSummary } from "../services/clearanceData";

describe("CountyRateTable component", () => {
  const sampleSummaries: CountyClearanceSummary[] = [
    { county: "Abbeville", added: 100, disposed: 22, clearanceRate: 0.22 },
    { county: "Aiken", added: 100, disposed: 88, clearanceRate: 0.88 },
    { county: "Charleston", added: 100, disposed: 104, clearanceRate: 1.04 },
    { county: "Allendale", added: 0, disposed: 0, clearanceRate: null },
  ];

  it("renders table headers with localized titles", () => {
    const table = renderCountyRateTable(sampleSummaries);
    const headers = Array.from(table.querySelectorAll("thead th")).map(
      (th) => th.textContent,
    );
    expect(headers).toEqual([t("tableHeaderCounty"), t("tableHeaderRate")]);
  });

  it("renders all county rows with formatted percentages and status classes", () => {
    const table = renderCountyRateTable(sampleSummaries);
    const rows = Array.from(table.querySelectorAll("tbody tr"));
    expect(rows).toHaveLength(4);

    expect(rows[0].querySelector(".county-name-cell")?.textContent).toBe(
      "Abbeville",
    );
    expect(rows[0].querySelector(".county-rate-cell")?.textContent).toBe("22%");
    expect(rows[0].classList.contains("status-red")).toBe(true);

    expect(rows[1].querySelector(".county-name-cell")?.textContent).toBe(
      "Aiken",
    );
    expect(rows[1].querySelector(".county-rate-cell")?.textContent).toBe("88%");
    expect(rows[1].classList.contains("status-yellow")).toBe(true);

    expect(rows[2].querySelector(".county-name-cell")?.textContent).toBe(
      "Charleston",
    );
    expect(rows[2].querySelector(".county-rate-cell")?.textContent).toBe(
      "104%",
    );
    expect(rows[2].classList.contains("status-green")).toBe(true);
  });

  it("renders N/A and status-no-data when clearance rate is null", () => {
    const table = renderCountyRateTable(sampleSummaries);
    const rows = Array.from(table.querySelectorAll("tbody tr"));
    const allendaleRow = rows[3];

    expect(allendaleRow.querySelector(".county-name-cell")?.textContent).toBe(
      "Allendale",
    );
    expect(allendaleRow.querySelector(".county-rate-cell")?.textContent).toBe(
      "N/A",
    );
    expect(allendaleRow.classList.contains("status-no-data")).toBe(true);
  });

  it("indicates 'No records found' when there is no data for a given date range", () => {
    const table = renderCountyRateTable([]);
    expect(table.textContent).toMatch(/no records found/i);
  });

  it("displays the start and end date to indicate the date range of the table", () => {
    const dateRange = {
      start: { year: 2024, month: 7 },
      end: { year: 2025, month: 6 },
    };
    // When dateRange is provided in table options or context
    const table = (renderCountyRateTable as any)(sampleSummaries, dateRange);
    expect(table.textContent).toMatch(/July 2024\s+to\s+June 2025/i);
  });

  it("shows loading text in table-date-range-caption while loading and shows formatted date range once loaded", () => {
    const dateRange = {
      start: { year: 2024, month: 7 },
      end: { year: 2025, month: 6 },
    };

    const loadingTable = renderCountyRateTable([], dateRange, true);
    const loadingCaption = loadingTable.querySelector(
      ".table-date-range-caption",
    );
    expect(loadingCaption?.textContent).toBe(t("loadingData"));

    const loadedTable = renderCountyRateTable(sampleSummaries, dateRange, false);
    const loadedCaption = loadedTable.querySelector(
      ".table-date-range-caption",
    );
    expect(loadedCaption?.textContent).toMatch(/July 2024\s+to\s+June 2025/i);
  });

  it("displays no table body rows while loading is in progress", () => {
    const loadingTable = renderCountyRateTable([], undefined, true);
    const rows = loadingTable.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(0);
    expect(loadingTable.querySelector(".empty-table-row")).toBeNull();
  });
});
