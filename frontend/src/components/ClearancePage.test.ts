import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderClearancePage } from "./ClearancePage";
import { t } from "../i18n";
import type { CountyClearanceSummary } from "../services/clearanceData";

describe("ClearancePage component", () => {
  let root: HTMLElement;
  const sampleSummaries: CountyClearanceSummary[] = [
    { county: "Abbeville", added: 100, disposed: 22, clearanceRate: 0.22 },
    { county: "Aiken", added: 100, disposed: 88, clearanceRate: 0.88 },
  ];

  beforeEach(() => {
    root = document.createElement("div");
  });

  it("renders page header and title", () => {
    renderClearancePage(root, {
      summaries: sampleSummaries,
      dateRange: {
        start: { year: 2025, month: 7 },
        end: { year: 2026, month: 6 },
      },
    });

    const heading = root.querySelector("h1");
    expect(heading?.textContent).toBe(t("pageTitle"));
  });

  it("renders the color legend with swatch indicators", () => {
    renderClearancePage(root, { summaries: sampleSummaries });

    const legendItems = Array.from(root.querySelectorAll(".legend-item")).map(
      (el) => el.textContent,
    );
    expect(legendItems).toEqual([
      t("legendGreen"),
      t("legendYellow"),
      t("legendRed"),
      t("legendNoData"),
    ]);

    expect(root.querySelector(".legend-swatch.status-green")).not.toBeNull();
    expect(root.querySelector(".legend-swatch.status-yellow")).not.toBeNull();
    expect(root.querySelector(".legend-swatch.status-red")).not.toBeNull();
  });

  it("renders both the map and table inside the layout container", () => {
    renderClearancePage(root, { summaries: sampleSummaries });

    expect(root.querySelector(".map-box svg.choropleth-svg")).not.toBeNull();
    expect(
      root.querySelector(".table-section table.clearance-table"),
    ).not.toBeNull();
  });

  it("renders start date and end date dropdown selectors at the top of the page with screen reader support", () => {
    renderClearancePage(root, {
      summaries: sampleSummaries,
      dateRange: {
        start: { year: 2025, month: 7 },
        end: { year: 2026, month: 6 },
      },
    });

    const startSelect = root.querySelector<HTMLSelectElement>(
      'select[aria-label*="start" i], select[name="startDate"], select#start-date',
    );
    const endSelect = root.querySelector<HTMLSelectElement>(
      'select[aria-label*="end" i], select[name="endDate"], select#end-date',
    );

    expect(startSelect).not.toBeNull();
    expect(endSelect).not.toBeNull();

    const hasStartAccessibleLabel = Boolean(
      startSelect?.getAttribute("aria-label") ||
      root.querySelector(`label[for="${startSelect?.id}"]`),
    );
    expect(hasStartAccessibleLabel).toBe(true);

    const hasEndAccessibleLabel = Boolean(
      endSelect?.getAttribute("aria-label") ||
      root.querySelector(`label[for="${endSelect?.id}"]`),
    );
    expect(hasEndAccessibleLabel).toBe(true);
  });

  it("disables date selectors and indicates 'No records found' when there is no data", () => {
    renderClearancePage(root, {
      summaries: [],
    });

    const startSelect = root.querySelector<HTMLSelectElement>(
      'select[aria-label*="start" i], select[name="startDate"], select#start-date',
    );
    const endSelect = root.querySelector<HTMLSelectElement>(
      'select[aria-label*="end" i], select[name="endDate"], select#end-date',
    );

    expect(startSelect?.disabled).toBe(true);
    expect(endSelect?.disabled).toBe(true);

    expect(root.textContent).toMatch(/no records found/i);
  });

  it("constrains selectable start dates so dates before the earliest data date cannot be selected", () => {
    (renderClearancePage as any)(root, {
      summaries: sampleSummaries,
      availableRange: {
        start: { year: 2023, month: 7 },
        end: { year: 2026, month: 6 },
      },
    });

    const startSelect = root.querySelector<HTMLSelectElement>(
      'select[aria-label*="start" i], select[name="startDate"], select#start-date',
    );
    expect(startSelect).not.toBeNull();
    const options = Array.from(startSelect?.options ?? []).map((o) => o.text);
    expect(options.length).toBeGreaterThan(0);

    for (const opt of options) {
      expect(opt).not.toMatch(/2022|June 2023|May 2023|January 2023/i);
    }
  });

  it("constrains selectable end dates so dates later than the latest data date cannot be selected", () => {
    (renderClearancePage as any)(root, {
      summaries: sampleSummaries,
      availableRange: {
        start: { year: 2023, month: 7 },
        end: { year: 2026, month: 6 },
      },
    });

    const endSelect = root.querySelector<HTMLSelectElement>(
      'select[aria-label*="end" i], select[name="endDate"], select#end-date',
    );
    expect(endSelect).not.toBeNull();
    const options = Array.from(endSelect?.options ?? []).map((o) => o.text);
    expect(options.length).toBeGreaterThan(0);

    for (const opt of options) {
      expect(opt).not.toMatch(/2027|July 2026|August 2026|December 2026/i);
    }
  });

  it("enforces that end date must be at least 1 month later than start date without greyed out options", () => {
    (renderClearancePage as any)(root, {
      summaries: sampleSummaries,
      dateRange: {
        start: { year: 2024, month: 10 },
        end: { year: 2025, month: 6 },
      },
    });

    const startSelect = root.querySelector<HTMLSelectElement>(
      'select[aria-label*="start" i], select[name="startDate"], select#start-date',
    );
    const endSelect = root.querySelector<HTMLSelectElement>(
      'select[aria-label*="end" i], select[name="endDate"], select#end-date',
    );
    expect(startSelect).not.toBeNull();
    expect(endSelect).not.toBeNull();

    // Verify options are selectable without greyed out text
    const disabledStartOpts = Array.from(startSelect?.options ?? []).filter(
      (o) => o.disabled,
    );
    const disabledEndOpts = Array.from(endSelect?.options ?? []).filter(
      (o) => o.disabled,
    );
    expect(disabledStartOpts).toHaveLength(0);
    expect(disabledEndOpts).toHaveLength(0);
  });

  it("displays the start and end date on both the map section and table section", () => {
    renderClearancePage(root, {
      summaries: sampleSummaries,
      dateRange: {
        start: { year: 2024, month: 7 },
        end: { year: 2025, month: 6 },
      },
    });

    const mapSection = root.querySelector(".map-box");
    const tableSection = root.querySelector(".table-section");

    expect(mapSection?.textContent).toMatch(/July 2024\s+to\s+June 2025/i);
    expect(tableSection?.textContent).toMatch(/July 2024\s+to\s+June 2025/i);
  });

  it("shows loading text in map-date-range while loading is true and shows the formatted date range once loaded", () => {
    renderClearancePage(root, {
      summaries: [],
      loading: true,
    });

    const mapDateRangeDuringLoad = root.querySelector(".map-date-range");
    expect(mapDateRangeDuringLoad?.textContent).toBe(t("loadingData"));

    renderClearancePage(root, {
      summaries: sampleSummaries,
      dateRange: {
        start: { year: 2024, month: 7 },
        end: { year: 2025, month: 6 },
      },
      loading: false,
    });

    const mapDateRangeAfterLoad = root.querySelector(".map-date-range");
    expect(mapDateRangeAfterLoad?.textContent).toMatch(
      /July 2024\s+to\s+June 2025/i,
    );
  });

  describe("bi-directional map and table selection synchronization", () => {
    it("clicking a county path on the map visually highlights both the map path and corresponding table row with .is-selected and aria-selected='true'", () => {
      renderClearancePage(root, { summaries: sampleSummaries });

      const aikenPath = root.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      expect(aikenPath).not.toBeNull();
      aikenPath?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

      expect(aikenPath?.classList.contains("is-selected")).toBe(true);
      expect(aikenPath?.getAttribute("aria-selected")).toBe("true");

      const aikenRow = Array.from(
        root.querySelectorAll<HTMLTableRowElement>("tr.county-row"),
      ).find(
        (row) =>
          row.querySelector(".county-name-cell")?.textContent === "Aiken",
      );
      expect(aikenRow?.classList.contains("is-selected")).toBe(true);
      expect(aikenRow?.getAttribute("aria-selected")).toBe("true");

      // Verify unselected counties remain unselected
      const abbevillePath = root.querySelector<SVGPathElement>(
        'path[data-county="Abbeville"]',
      );
      const abbevilleRow = Array.from(
        root.querySelectorAll<HTMLTableRowElement>("tr.county-row"),
      ).find(
        (row) =>
          row.querySelector(".county-name-cell")?.textContent === "Abbeville",
      );
      expect(abbevillePath?.classList.contains("is-selected")).toBe(false);
      expect(abbevillePath?.getAttribute("aria-selected")).toBe("false");
      expect(abbevilleRow?.classList.contains("is-selected")).toBe(false);
      expect(abbevilleRow?.getAttribute("aria-selected")).toBe("false");
    });

    it("does not scroll corresponding table row into view when county is selected on the map", () => {
      renderClearancePage(root, { summaries: sampleSummaries });

      const aikenRow = Array.from(
        root.querySelectorAll<HTMLTableRowElement>("tr.county-row"),
      ).find(
        (row) =>
          row.querySelector(".county-name-cell")?.textContent === "Aiken",
      );
      expect(aikenRow).not.toBeNull();
      const scrollSpy = vi.fn();
      aikenRow!.scrollIntoView = scrollSpy;

      const aikenPath = root.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      aikenPath?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

      expect(scrollSpy).not.toHaveBeenCalled();
    });

    it("clicking a table row visually highlights both the table row and corresponding map path with .is-selected and aria-selected='true'", () => {
      renderClearancePage(root, { summaries: sampleSummaries });

      const aikenRow = Array.from(
        root.querySelectorAll<HTMLTableRowElement>("tr.county-row"),
      ).find(
        (row) =>
          row.querySelector(".county-name-cell")?.textContent === "Aiken",
      );
      expect(aikenRow).not.toBeNull();
      aikenRow?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

      expect(aikenRow?.classList.contains("is-selected")).toBe(true);
      expect(aikenRow?.getAttribute("aria-selected")).toBe("true");

      const aikenPath = root.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      expect(aikenPath?.classList.contains("is-selected")).toBe(true);
      expect(aikenPath?.getAttribute("aria-selected")).toBe("true");
    });

    it("clicking an already-selected county on the map clears selection on both map and table", () => {
      renderClearancePage(root, { summaries: sampleSummaries });

      const aikenPath = root.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      const aikenRow = Array.from(
        root.querySelectorAll<HTMLTableRowElement>("tr.county-row"),
      ).find(
        (row) =>
          row.querySelector(".county-name-cell")?.textContent === "Aiken",
      );

      // Select
      aikenPath?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(aikenPath?.classList.contains("is-selected")).toBe(true);
      expect(aikenRow?.classList.contains("is-selected")).toBe(true);

      // Re-click to clear
      aikenPath?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(aikenPath?.classList.contains("is-selected")).toBe(false);
      expect(aikenPath?.getAttribute("aria-selected")).toBe("false");
      expect(aikenRow?.classList.contains("is-selected")).toBe(false);
      expect(aikenRow?.getAttribute("aria-selected")).toBe("false");
    });

    it("clicking an already-selected county row in the table clears selection on both map and table", () => {
      renderClearancePage(root, { summaries: sampleSummaries });

      const aikenPath = root.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      const aikenRow = Array.from(
        root.querySelectorAll<HTMLTableRowElement>("tr.county-row"),
      ).find(
        (row) =>
          row.querySelector(".county-name-cell")?.textContent === "Aiken",
      );

      // Select via table row
      aikenRow?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(aikenRow?.classList.contains("is-selected")).toBe(true);
      expect(aikenPath?.classList.contains("is-selected")).toBe(true);

      // Re-click table row to clear
      aikenRow?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(aikenRow?.classList.contains("is-selected")).toBe(false);
      expect(aikenRow?.getAttribute("aria-selected")).toBe("false");
      expect(aikenPath?.classList.contains("is-selected")).toBe(false);
      expect(aikenPath?.getAttribute("aria-selected")).toBe("false");
    });

    it("clicking anywhere outside the map and table clears the selection", () => {
      renderClearancePage(root, { summaries: sampleSummaries });

      const aikenPath = root.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      const aikenRow = Array.from(
        root.querySelectorAll<HTMLTableRowElement>("tr.county-row"),
      ).find(
        (row) =>
          row.querySelector(".county-name-cell")?.textContent === "Aiken",
      );

      // Select
      aikenPath?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(aikenPath?.classList.contains("is-selected")).toBe(true);

      // Click outside (e.g. heading or page header or outside area)
      const heading = root.querySelector("h1");
      heading?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

      expect(aikenPath?.classList.contains("is-selected")).toBe(false);
      expect(aikenPath?.getAttribute("aria-selected")).toBe("false");
      expect(aikenRow?.classList.contains("is-selected")).toBe(false);
      expect(aikenRow?.getAttribute("aria-selected")).toBe("false");
    });

    it("supports keyboard selection using Enter and Space on map paths and table rows", () => {
      renderClearancePage(root, { summaries: sampleSummaries });

      const aikenPath = root.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      const aikenRow = Array.from(
        root.querySelectorAll<HTMLTableRowElement>("tr.county-row"),
      ).find(
        (row) =>
          row.querySelector(".county-name-cell")?.textContent === "Aiken",
      );

      // Enter on map path
      aikenPath?.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
      );
      expect(aikenPath?.classList.contains("is-selected")).toBe(true);
      expect(aikenRow?.classList.contains("is-selected")).toBe(true);

      // Space on table row toggles it off
      aikenRow?.dispatchEvent(
        new KeyboardEvent("keydown", { key: " ", bubbles: true }),
      );
      expect(aikenPath?.classList.contains("is-selected")).toBe(false);
      expect(aikenRow?.classList.contains("is-selected")).toBe(false);
    });

    it("maintains a unified selected county state so selecting another county switches selection", () => {
      renderClearancePage(root, { summaries: sampleSummaries });

      const aikenPath = root.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      const abbevillePath = root.querySelector<SVGPathElement>(
        'path[data-county="Abbeville"]',
      );
      const aikenRow = Array.from(
        root.querySelectorAll<HTMLTableRowElement>("tr.county-row"),
      ).find(
        (row) =>
          row.querySelector(".county-name-cell")?.textContent === "Aiken",
      );
      const abbevilleRow = Array.from(
        root.querySelectorAll<HTMLTableRowElement>("tr.county-row"),
      ).find(
        (row) =>
          row.querySelector(".county-name-cell")?.textContent === "Abbeville",
      );

      // Select Aiken
      aikenPath?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(aikenPath?.classList.contains("is-selected")).toBe(true);
      expect(aikenRow?.classList.contains("is-selected")).toBe(true);

      // Select Abbeville
      abbevillePath?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(abbevillePath?.classList.contains("is-selected")).toBe(true);
      expect(abbevilleRow?.classList.contains("is-selected")).toBe(true);
      expect(aikenPath?.classList.contains("is-selected")).toBe(false);
      expect(aikenRow?.classList.contains("is-selected")).toBe(false);
    });

    it("clears county selection on map and table when interacting with date range dropdowns", () => {
      renderClearancePage(root, {
        summaries: sampleSummaries,
        dateRange: {
          start: { year: 2024, month: 7 },
          end: { year: 2025, month: 6 },
        },
      });

      const aikenPath = root.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      const aikenRow = Array.from(
        root.querySelectorAll<HTMLTableRowElement>("tr.county-row"),
      ).find(
        (row) =>
          row.querySelector(".county-name-cell")?.textContent === "Aiken",
      );

      // Select Aiken
      aikenPath?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(aikenPath?.classList.contains("is-selected")).toBe(true);
      expect(aikenRow?.classList.contains("is-selected")).toBe(true);

      // Click start date dropdown selector
      const startSelect = root.querySelector<HTMLSelectElement>("#start-date");
      expect(startSelect).not.toBeNull();
      startSelect?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

      expect(aikenPath?.classList.contains("is-selected")).toBe(false);
      expect(aikenPath?.getAttribute("aria-selected")).toBe("false");
      expect(aikenRow?.classList.contains("is-selected")).toBe(false);
      expect(aikenRow?.getAttribute("aria-selected")).toBe("false");
    });

    it("[A11y] clears active county selection on map and table when Escape key is pressed", () => {
      renderClearancePage(root, { summaries: sampleSummaries });

      const aikenPath = root.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      const aikenRow = Array.from(
        root.querySelectorAll<HTMLTableRowElement>("tr.county-row"),
      ).find(
        (row) =>
          row.querySelector(".county-name-cell")?.textContent === "Aiken",
      );

      // Select Aiken
      aikenPath?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(aikenPath?.classList.contains("is-selected")).toBe(true);
      expect(aikenRow?.classList.contains("is-selected")).toBe(true);

      // Press Escape
      root.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );

      expect(aikenPath?.classList.contains("is-selected")).toBe(false);
      expect(aikenPath?.getAttribute("aria-selected")).toBe("false");
      expect(aikenRow?.classList.contains("is-selected")).toBe(false);
      expect(aikenRow?.getAttribute("aria-selected")).toBe("false");
    });
  });
});
