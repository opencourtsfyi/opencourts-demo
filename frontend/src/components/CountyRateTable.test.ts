import { describe, it, expect, vi } from "vitest";
import { renderCountyRateTable } from "./CountyRateTable";
import { CompletenessTier } from "../constants/clearanceThresholds";
import { t } from "../i18n";
import type { CountyClearanceSummary } from "../services/clearanceData";

describe("CountyRateTable component", () => {
  const sampleSummaries: CountyClearanceSummary[] = [
    {
      county: "Abbeville",
      added: 100,
      disposed: 22,
      clearanceRate: 0.22,
      reportedPeriods: 12,
      totalPeriods: 12,
      completenessRatio: 1,
      completenessTier: CompletenessTier.COMPLETE,
      isSufficientData: true,
    },
    {
      county: "Aiken",
      added: 100,
      disposed: 88,
      clearanceRate: 0.88,
      reportedPeriods: 9,
      totalPeriods: 12,
      completenessRatio: 0.75,
      completenessTier: CompletenessTier.PARTIAL,
      isSufficientData: true,
    },
    {
      county: "Charleston",
      added: 100,
      disposed: 104,
      clearanceRate: 1.04,
      reportedPeriods: 12,
      totalPeriods: 12,
      completenessRatio: 1,
      completenessTier: CompletenessTier.COMPLETE,
      isSufficientData: true,
    },
    {
      county: "Allendale",
      added: 0,
      disposed: 0,
      clearanceRate: null,
      reportedPeriods: 2,
      totalPeriods: 12,
      completenessRatio: 2 / 12,
      completenessTier: CompletenessTier.INSUFFICIENT,
      isSufficientData: false,
    },
  ];

  it("renders table headers with localized titles and scope='col'", () => {
    const table = renderCountyRateTable(sampleSummaries);
    const headerEls = Array.from(
      table.querySelectorAll<HTMLTableCellElement>("thead th"),
    );
    expect(headerEls.map((th) => th.textContent)).toEqual([
      t("tableHeaderCounty"),
      t("tableHeaderRate"),
      t("tableHeaderCompleteness"),
      t("tableHeaderReportedPeriods"),
    ]);
    expect(headerEls.every((th) => th.scope === "col")).toBe(true);
  });

  it("renders county name cells as row headers with scope='row'", () => {
    const table = renderCountyRateTable(sampleSummaries);
    const rowHeaders = Array.from(
      table.querySelectorAll<HTMLTableCellElement>("tbody th.county-name-cell"),
    );
    expect(rowHeaders).toHaveLength(sampleSummaries.length);
    expect(rowHeaders.every((th) => th.scope === "row")).toBe(true);
  });

  it("always renders a caption describing the table's purpose", () => {
    const table = renderCountyRateTable(sampleSummaries);
    const caption = table.querySelector("caption");
    expect(caption).not.toBeNull();
    expect(caption?.textContent).toContain(t("pageTitle"));
  });

  it("renders all county rows with formatted percentages, tiers, and completeness", () => {
    const table = renderCountyRateTable(sampleSummaries);
    const rows = Array.from(table.querySelectorAll("tbody tr"));
    expect(rows).toHaveLength(4);

    expect(rows[0].querySelector(".county-name-cell")?.textContent).toBe(
      "Abbeville",
    );
    expect(rows[0].querySelector(".county-rate-cell")?.textContent).toBe("22%");
    expect(rows[0].classList.contains("tier-1")).toBe(true);
    expect(rows[0].querySelector(".county-completeness-cell")?.textContent).toBe(
      t("completenessComplete"),
    );

    expect(rows[1].querySelector(".county-name-cell")?.textContent).toBe(
      "Aiken",
    );
    expect(rows[1].querySelector(".county-rate-cell")?.textContent).toBe("88%");
    expect(rows[1].classList.contains("tier-2")).toBe(true);
    expect(rows[1].querySelector(".county-completeness-cell")?.textContent).toBe(
      t("completenessPartial"),
    );
    expect(rows[1].querySelector(".county-periods-cell")?.textContent).toBe(
      "9/12 (75%)",
    );

    expect(rows[2].querySelector(".county-name-cell")?.textContent).toBe(
      "Charleston",
    );
    expect(rows[2].querySelector(".county-rate-cell")?.textContent).toBe(
      "104%",
    );
    expect(rows[2].classList.contains("tier-3")).toBe(true);
  });

  it("renders Insufficient Data when county is below reporting threshold", () => {
    const table = renderCountyRateTable(sampleSummaries);
    const rows = Array.from(table.querySelectorAll("tbody tr"));
    const allendaleRow = rows[3];

    expect(allendaleRow.querySelector(".county-name-cell")?.textContent).toBe(
      "Allendale",
    );
    expect(allendaleRow.querySelector(".county-rate-cell")?.textContent).toBe(
      t("insufficientDataLabel"),
    );
    expect(allendaleRow.classList.contains("status-insufficient-data")).toBe(
      true,
    );
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
    const table = renderCountyRateTable(sampleSummaries, dateRange);
    expect(table.textContent).toMatch(/July 2024\s+to\s+June 2025/i);
  });

  it("shows loading text in table-date-range-caption while loading and shows formatted date range once loaded", () => {
    const dateRange = {
      start: { year: 2024, month: 7 },
      end: { year: 2025, month: 6 },
    };

    const loadingTable = renderCountyRateTable([], dateRange, true);
    expect(
      loadingTable.querySelector(".table-date-range-caption")?.textContent,
    ).toBe(t("loadingData"));

    const loadedTable = renderCountyRateTable(
      sampleSummaries,
      dateRange,
      false,
    );
    const loadedCaption = loadedTable.querySelector(
      ".table-date-range-caption",
    );
    expect(loadedCaption?.textContent).toContain(t("pageTitle"));
    expect(loadedCaption?.textContent).toMatch(/July 2024\s+to\s+June 2025/i);
  });

  it("displays no table body rows while loading is in progress", () => {
    const loadingTable = renderCountyRateTable([], undefined, true);
    expect(loadingTable.querySelectorAll("tbody tr")).toHaveLength(0);
    expect(loadingTable.querySelector(".empty-table-row")).toBeNull();
  });

  describe("interactivity, selection, and accessibility", () => {
    it("renders county rows with keyboard focusability and initial aria-selected attribute", () => {
      const table = renderCountyRateTable(sampleSummaries);
      const rows = table.querySelectorAll<HTMLTableRowElement>(
        "tbody tr.county-row",
      );

      expect(rows.length).toBeGreaterThan(0);
      for (const row of rows) {
        expect(row.getAttribute("tabindex")).toBe("0");
        expect(row.getAttribute("aria-selected")).toBe("false");
        expect(row.classList.contains("is-selected")).toBe(false);
      }
    });

    it("applies is-selected class and aria-selected='true' to the row matching selectedCounty", () => {
      const table = renderCountyRateTable(
        sampleSummaries,
        undefined,
        false,
        "Aiken",
      );

      const aikenRow = Array.from(
        table.querySelectorAll<HTMLTableRowElement>("tbody tr.county-row"),
      ).find(
        (r) => r.querySelector(".county-name-cell")?.textContent === "Aiken",
      );
      const abbevilleRow = Array.from(
        table.querySelectorAll<HTMLTableRowElement>("tbody tr.county-row"),
      ).find(
        (r) =>
          r.querySelector(".county-name-cell")?.textContent === "Abbeville",
      );

      expect(aikenRow?.classList.contains("is-selected")).toBe(true);
      expect(aikenRow?.getAttribute("aria-selected")).toBe("true");
      expect(abbevilleRow?.classList.contains("is-selected")).toBe(false);
      expect(abbevilleRow?.getAttribute("aria-selected")).toBe("false");
    });

    it("invokes onSelectCounty callback with county name when an unselected row is clicked", () => {
      const onSelectCounty = vi.fn();
      const table = renderCountyRateTable(
        sampleSummaries,
        undefined,
        false,
        null,
        onSelectCounty,
      );

      const aikenRow = Array.from(
        table.querySelectorAll<HTMLTableRowElement>("tbody tr.county-row"),
      ).find(
        (r) => r.querySelector(".county-name-cell")?.textContent === "Aiken",
      );
      aikenRow?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

      expect(onSelectCounty).toHaveBeenCalledWith("Aiken");
    });

    it("invokes onSelectCounty callback with null when the already-selected row is clicked", () => {
      const onSelectCounty = vi.fn();
      const table = renderCountyRateTable(
        sampleSummaries,
        undefined,
        false,
        "Aiken",
        onSelectCounty,
      );

      const aikenRow = Array.from(
        table.querySelectorAll<HTMLTableRowElement>("tbody tr.county-row"),
      ).find(
        (r) => r.querySelector(".county-name-cell")?.textContent === "Aiken",
      );
      aikenRow?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

      expect(onSelectCounty).toHaveBeenCalledWith(null);
    });

    it("supports keyboard selection on rows using Enter and Space keys", () => {
      const onSelectCounty = vi.fn();
      const table = renderCountyRateTable(
        sampleSummaries,
        undefined,
        false,
        null,
        onSelectCounty,
      );

      const aikenRow = Array.from(
        table.querySelectorAll<HTMLTableRowElement>("tbody tr.county-row"),
      ).find(
        (r) => r.querySelector(".county-name-cell")?.textContent === "Aiken",
      );

      aikenRow?.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
      );
      expect(onSelectCounty).toHaveBeenCalledWith("Aiken");

      onSelectCounty.mockClear();

      aikenRow?.dispatchEvent(
        new KeyboardEvent("keydown", { key: " ", bubbles: true }),
      );
      expect(onSelectCounty).toHaveBeenCalledWith("Aiken");
    });
  });
});
