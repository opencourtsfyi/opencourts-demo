import { describe, it, expect } from "vitest";
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
});
