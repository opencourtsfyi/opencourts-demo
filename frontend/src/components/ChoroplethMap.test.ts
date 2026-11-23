import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderChoroplethMap, type ScTopology } from "./ChoroplethMap";
import scTopologyJson from "../data/sc-counties-topo.json";
import { MAP_DIMENSIONS } from "../constants/clearanceThresholds";
import { t } from "../../src/i18n";
import type { CountyClearanceSummary } from "../services/clearanceData";

const topology = scTopologyJson as unknown as ScTopology;

describe("ChoroplethMap component", () => {
  const sampleSummaries: CountyClearanceSummary[] = [
    { county: "Abbeville", added: 100, disposed: 22, clearanceRate: 0.22 },
    { county: "Aiken", added: 100, disposed: 88, clearanceRate: 0.88 },
    { county: "Charleston", added: 100, disposed: 104, clearanceRate: 1.04 },
  ];

  it("renders SVG with correct attributes and accessibility roles", () => {
    const svg = renderChoroplethMap(sampleSummaries, topology);
    expect(svg.tagName.toLowerCase()).toBe("svg");
    expect(svg.getAttribute("viewBox")).toBe(
      `0 0 ${MAP_DIMENSIONS.WIDTH} ${MAP_DIMENSIONS.HEIGHT}`,
    );
    expect(svg.getAttribute("role")).toBe("group");
    expect(svg.getAttribute("aria-labelledby")).toBe("mapTitle mapDesc");
    expect(svg.querySelector("defs title#mapTitle")?.textContent).toBe(
      t("mapTitle"),
    );
    expect(svg.querySelector("desc#mapDesc")?.textContent).toBe(t("mapDesc"));
    expect(
      svg.querySelector("defs pattern#pattern-insufficient-data"),
    ).not.toBeNull();
  });

  it("renders paths for all 46 South Carolina counties", () => {
    const svg = renderChoroplethMap(sampleSummaries, topology);
    const paths = svg.querySelectorAll("path.county-path");
    expect(paths).toHaveLength(46);
  });

  it("assigns clearance status classes to county paths based on rates", () => {
    const svg = renderChoroplethMap(sampleSummaries, topology);

    const abbevillePath = svg.querySelector('path[data-county="Abbeville"]');
    const aikenPath = svg.querySelector('path[data-county="Aiken"]');
    const charlestonPath = svg.querySelector('path[data-county="Charleston"]');
    const pickensPath = svg.querySelector('path[data-county="Pickens"]'); // not in sample

    expect(abbevillePath?.classList.contains("tier-1")).toBe(true);
    expect(aikenPath?.classList.contains("tier-2")).toBe(true);
    expect(charlestonPath?.classList.contains("tier-3")).toBe(true);
    expect(pickensPath?.classList.contains("status-insufficient-data")).toBe(
      true,
    );
  });

  it("renders accessible aria-labels on county paths", () => {
    const svg = renderChoroplethMap(sampleSummaries, topology);
    const aikenLabel = svg
      .querySelector('path[data-county="Aiken"]')
      ?.getAttribute("aria-label");
    expect(aikenLabel).toBe("Aiken: 88%");

    const unrankedLabel = svg
      .querySelector('path[data-county="Pickens"]')
      ?.getAttribute("aria-label");
    expect(unrankedLabel).toBe(`Pickens: ${t("insufficientDataLabel")}`);
  });

  it("displays the start and end date on the map to indicate its date range", () => {
    const dateRange = {
      start: { year: 2024, month: 7 },
      end: { year: 2025, month: 6 },
    };
    const svg = (renderChoroplethMap as any)(
      sampleSummaries,
      topology,
      dateRange,
    );
    const textContent = svg.textContent || svg.getAttribute("aria-label") || "";
    expect(textContent).toMatch(/July 2024\s+to\s+June 2025/i);
  });

  describe("interactivity, selection, and accessibility", () => {
    it("renders county paths with keyboard focusability and initial aria-pressed attribute", () => {
      const svg = renderChoroplethMap(sampleSummaries, topology);
      const paths = svg.querySelectorAll<SVGPathElement>("path.county-path");

      expect(paths.length).toBeGreaterThan(0);
      for (const path of paths) {
        expect(path.getAttribute("tabindex")).toBe("0");
        expect(path.getAttribute("aria-pressed")).toBe("false");
        expect(path.classList.contains("is-selected")).toBe(false);
      }
    });

    it("applies is-selected class and aria-pressed='true' to the path matching selectedCounty", () => {
      const svg: SVGSVGElement = (renderChoroplethMap as any)(
        sampleSummaries,
        topology,
        undefined,
        "Aiken",
      );

      const aikenPath = svg.querySelector('path[data-county="Aiken"]');
      const abbevillePath = svg.querySelector('path[data-county="Abbeville"]');

      expect(aikenPath?.classList.contains("is-selected")).toBe(true);
      expect(aikenPath?.getAttribute("aria-pressed")).toBe("true");

      expect(abbevillePath?.classList.contains("is-selected")).toBe(false);
      expect(abbevillePath?.getAttribute("aria-pressed")).toBe("false");
    });

    it("invokes onSelectCounty callback with county name when an unselected path is clicked", () => {
      const onSelectCounty = vi.fn();
      const svg: SVGSVGElement = (renderChoroplethMap as any)(
        sampleSummaries,
        topology,
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
        topology,
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
        topology,
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

  describe("interactive tooltip", () => {
    let container: HTMLDivElement;

    beforeEach(() => {
      container = document.createElement("div");
      document.body.appendChild(container);
    });

    afterEach(() => {
      container.remove();
      document
        .querySelectorAll(".map-tooltip, [role='tooltip']")
        .forEach((el) => el.remove());
    });

    it("mirrors county name and clearance rate in the county path aria-label for accessibility", () => {
      const svg = renderChoroplethMap(sampleSummaries, topology);
      container.appendChild(svg);

      const aikenPath = svg.querySelector('path[data-county="Aiken"]');
      const pickensPath = svg.querySelector('path[data-county="Pickens"]');

      expect(aikenPath?.getAttribute("aria-label")).toBe("Aiken: 88%");
      expect(pickensPath?.getAttribute("aria-label")).toBe(
        `Pickens: ${t("insufficientDataLabel")}`,
      );
    });

    it("displays a dynamic tooltip with county name and clearance rate percentage on mouseover", () => {
      const svg = renderChoroplethMap(sampleSummaries, topology);
      container.appendChild(svg);

      const aikenPath = svg.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      expect(aikenPath).not.toBeNull();

      aikenPath?.dispatchEvent(
        new MouseEvent("mouseover", {
          bubbles: true,
          clientX: 120,
          clientY: 200,
        }),
      );

      const tooltip = document.querySelector<HTMLElement>(
        ".map-tooltip, [role='tooltip']",
      );
      expect(tooltip).not.toBeNull();
      expect(tooltip?.textContent).toContain("Aiken");
      expect(tooltip?.textContent).toContain("88%");
    });

    it("displays county name and Insufficient Data in the tooltip for counties with no clearance data", () => {
      const svg = renderChoroplethMap(sampleSummaries, topology);
      container.appendChild(svg);

      const pickensPath = svg.querySelector<SVGPathElement>(
        'path[data-county="Pickens"]',
      );
      expect(pickensPath).not.toBeNull();

      pickensPath?.dispatchEvent(
        new MouseEvent("mouseover", {
          bubbles: true,
          clientX: 100,
          clientY: 150,
        }),
      );

      const tooltip = document.querySelector<HTMLElement>(
        ".map-tooltip, [role='tooltip']",
      );
      expect(tooltip).not.toBeNull();
      expect(tooltip?.textContent).toContain("Pickens");
      expect(tooltip?.textContent).toContain(t("insufficientDataLabel"));
    });

    it("updates tooltip position when moving cursor (mousemove) over a county path", () => {
      const svg = renderChoroplethMap(sampleSummaries, topology);
      container.appendChild(svg);

      const aikenPath = svg.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      expect(aikenPath).not.toBeNull();

      aikenPath?.dispatchEvent(
        new MouseEvent("mouseover", {
          bubbles: true,
          clientX: 100,
          clientY: 100,
        }),
      );
      const tooltip = document.querySelector<HTMLElement>(
        ".map-tooltip, [role='tooltip']",
      );
      expect(tooltip).not.toBeNull();

      aikenPath?.dispatchEvent(
        new MouseEvent("mousemove", {
          bubbles: true,
          clientX: 180,
          clientY: 240,
        }),
      );

      const hasUpdatedPosition =
        Boolean(tooltip?.style.left && tooltip?.style.top) ||
        Boolean(tooltip?.style.transform);
      expect(hasUpdatedPosition).toBe(true);
    });

    it("hides the tooltip when the mouse leaves the county path (mouseout)", () => {
      const svg = renderChoroplethMap(sampleSummaries, topology);
      container.appendChild(svg);

      const aikenPath = svg.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      expect(aikenPath).not.toBeNull();

      aikenPath?.dispatchEvent(
        new MouseEvent("mouseover", {
          bubbles: true,
          clientX: 100,
          clientY: 100,
        }),
      );
      const tooltip = document.querySelector<HTMLElement>(
        ".map-tooltip, [role='tooltip']",
      );
      expect(tooltip).not.toBeNull();

      aikenPath?.dispatchEvent(new MouseEvent("mouseout", { bubbles: true }));

      const isHidden =
        !document.body.contains(tooltip) ||
        tooltip?.style.display === "none" ||
        tooltip?.style.opacity === "0" ||
        tooltip?.classList.contains("is-hidden") ||
        tooltip?.getAttribute("aria-hidden") === "true";
      expect(isHidden).toBe(true);
    });

    it("displays tooltip on focus and hides on blur for keyboard navigation parity", () => {
      const svg = renderChoroplethMap(sampleSummaries, topology);
      container.appendChild(svg);

      const aikenPath = svg.querySelector<SVGPathElement>(
        'path[data-county="Aiken"]',
      );
      expect(aikenPath).not.toBeNull();

      aikenPath?.dispatchEvent(new FocusEvent("focus", { bubbles: true }));

      const tooltip = document.querySelector<HTMLElement>(
        ".map-tooltip, [role='tooltip']",
      );
      expect(tooltip).not.toBeNull();
      expect(tooltip?.textContent).toContain("Aiken");
      expect(tooltip?.textContent).toContain("88%");

      aikenPath?.dispatchEvent(new FocusEvent("blur", { bubbles: true }));

      const isHidden =
        !document.body.contains(tooltip) ||
        tooltip?.style.display === "none" ||
        tooltip?.style.opacity === "0" ||
        tooltip?.classList.contains("is-hidden") ||
        tooltip?.getAttribute("aria-hidden") === "true";
      expect(isHidden).toBe(true);
    });
  });
});
