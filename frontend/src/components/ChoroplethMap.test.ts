import { describe, it, expect, vi } from "vitest";
import { renderChoroplethMap } from "./ChoroplethMap";
import { MAP_DIMENSIONS } from "../constants/clearanceThresholds";
import { t } from "../../src/i18n";
import type { CountyClearanceSummary } from "../services/clearanceData";

describe("ChoroplethMap component", () => {
  const sampleSummaries: CountyClearanceSummary[] = [
    { county: "Abbeville", added: 100, disposed: 22, clearanceRate: 0.22 },
    { county: "Aiken", added: 100, disposed: 88, clearanceRate: 0.88 },
    { county: "Charleston", added: 100, disposed: 104, clearanceRate: 1.04 },
  ];

  it("renders SVG with correct attributes and accessibility roles", () => {
    const svg = renderChoroplethMap(sampleSummaries);
    expect(svg.tagName.toLowerCase()).toBe("svg");
    expect(svg.getAttribute("viewBox")).toBe(
      `0 0 ${MAP_DIMENSIONS.WIDTH} ${MAP_DIMENSIONS.HEIGHT}`,
    );
    expect(svg.getAttribute("role")).toBe("img");
    expect(svg.getAttribute("aria-label")).toBe(t("mapAriaLabel"));
  });

  it("renders paths for all 46 South Carolina counties", () => {
    const svg = renderChoroplethMap(sampleSummaries);
    const paths = svg.querySelectorAll("path.county-path");
    expect(paths).toHaveLength(46);
  });

  it("assigns clearance status classes to county paths based on rates", () => {
    const svg = renderChoroplethMap(sampleSummaries);

    const abbevillePath = svg.querySelector('path[data-county="Abbeville"]');
    const aikenPath = svg.querySelector('path[data-county="Aiken"]');
    const charlestonPath = svg.querySelector('path[data-county="Charleston"]');
    const pickensPath = svg.querySelector('path[data-county="Pickens"]'); // not in sample

    expect(abbevillePath?.classList.contains("status-red")).toBe(true);
    expect(aikenPath?.classList.contains("status-yellow")).toBe(true);
    expect(charlestonPath?.classList.contains("status-green")).toBe(true);
    expect(pickensPath?.classList.contains("status-no-data")).toBe(true);
  });

  it("renders descriptive SVG title tooltips on county paths", () => {
    const svg = renderChoroplethMap(sampleSummaries);
    const aikenTitle = svg.querySelector(
      'path[data-county="Aiken"] title',
    )?.textContent;
    expect(aikenTitle).toBe("Aiken: 88%");

    const unrankedTitle = svg.querySelector(
      'path[data-county="Pickens"] title',
    )?.textContent;
    expect(unrankedTitle).toBe("Pickens: N/A");
  });

  it("displays the start and end date on the map to indicate its date range", () => {
    const dateRange = {
      start: { year: 2024, month: 7 },
      end: { year: 2025, month: 6 },
    };
    const svg = (renderChoroplethMap as any)(
      sampleSummaries,
      undefined,
      dateRange,
    );
    const textContent = svg.textContent || svg.getAttribute("aria-label") || "";
    expect(textContent).toMatch(/July 2024\s+to\s+June 2025/i);
  });

  describe("interactivity, selection, and accessibility", () => {
    it("renders county paths with keyboard focusability and initial aria-selected attribute", () => {
      const svg = renderChoroplethMap(sampleSummaries);
      const paths = svg.querySelectorAll<SVGPathElement>("path.county-path");

      expect(paths.length).toBeGreaterThan(0);
      for (const path of paths) {
        expect(path.getAttribute("tabindex")).toBe("0");
        expect(path.getAttribute("aria-selected")).toBe("false");
        expect(path.classList.contains("is-selected")).toBe(false);
      }
    });

    it("applies is-selected class and aria-selected='true' to the path matching selectedCounty", () => {
      const svg: SVGSVGElement = (renderChoroplethMap as any)(
        sampleSummaries,
        undefined,
        undefined,
        "Aiken",
      );

      const aikenPath = svg.querySelector('path[data-county="Aiken"]');
      const abbevillePath = svg.querySelector('path[data-county="Abbeville"]');

      expect(aikenPath?.classList.contains("is-selected")).toBe(true);
      expect(aikenPath?.getAttribute("aria-selected")).toBe("true");

      expect(abbevillePath?.classList.contains("is-selected")).toBe(false);
      expect(abbevillePath?.getAttribute("aria-selected")).toBe("false");
    });

    it("invokes onSelectCounty callback with county name when an unselected path is clicked", () => {
      const onSelectCounty = vi.fn();
      const svg: SVGSVGElement = (renderChoroplethMap as any)(
        sampleSummaries,
        undefined,
        undefined,
        null,
        onSelectCounty,
      );

      const aikenPath = svg.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      expect(aikenPath).not.toBeNull();
      aikenPath?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

      expect(onSelectCounty).toHaveBeenCalledWith("Aiken");
    });

    it("invokes onSelectCounty callback with null when the already-selected path is clicked", () => {
      const onSelectCounty = vi.fn();
      const svg: SVGSVGElement = (renderChoroplethMap as any)(
        sampleSummaries,
        undefined,
        undefined,
        "Aiken",
        onSelectCounty,
      );

      const aikenPath = svg.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      expect(aikenPath).not.toBeNull();
      aikenPath?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

      expect(onSelectCounty).toHaveBeenCalledWith(null);
    });

    it("supports keyboard selection using Enter and Space keys", () => {
      const onSelectCounty = vi.fn();
      const svg: SVGSVGElement = (renderChoroplethMap as any)(
        sampleSummaries,
        undefined,
        undefined,
        null,
        onSelectCounty,
      );

      const aikenPath = svg.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      expect(aikenPath).not.toBeNull();

      aikenPath?.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
      );
      expect(onSelectCounty).toHaveBeenCalledWith("Aiken");

      onSelectCounty.mockClear();

      aikenPath?.dispatchEvent(
        new KeyboardEvent("keydown", { key: " ", bubbles: true }),
      );
      expect(onSelectCounty).toHaveBeenCalledWith("Aiken");
    });
  });
});
