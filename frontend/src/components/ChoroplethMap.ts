import { geoMercator, geoPath } from "d3-geo";
import { select } from "d3-selection";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import scTopologyJson from "../data/sc-counties-topo.json";
import {
  getClearanceStatus,
  MAP_DIMENSIONS,
} from "../constants/clearanceThresholds";
import type {
  CountyClearanceSummary,
  DateRangeFilter,
} from "../services/clearanceData";
import { formatClearanceRate, formatDateRange } from "../utils/formatters";
import { t } from "../i18n";
import { MapTooltip } from "./MapTooltip";

export interface CountyProperties {
  name: string;
}

export type ScTopology = Topology<{
  counties: GeometryCollection<CountyProperties>;
}>;

const SVG_NS = "http://www.w3.org/2000/svg";

export function renderChoroplethMap(
  summaries: readonly CountyClearanceSummary[],
  topology: ScTopology = scTopologyJson as unknown as ScTopology,
  dateRange?: DateRangeFilter,
  selectedCounty?: string | null,
  onSelectCounty?: (county: string | null) => void,
): SVGSVGElement {
  const rateByCounty = new Map<string, number | null>();
  for (const item of summaries) {
    rateByCounty.set(item.county.toLowerCase(), item.clearanceRate);
  }

  const geojson = feature(
    topology,
    topology.objects.counties,
  ) as FeatureCollection<Geometry, CountyProperties>;

  const projection = geoMercator().fitSize(
    [MAP_DIMENSIONS.WIDTH, MAP_DIMENSIONS.HEIGHT],
    geojson,
  );
  const pathGenerator = geoPath(projection);

  const titleText = dateRange
    ? `${t("mapTitle")} (${formatDateRange(dateRange.start, dateRange.end)})`
    : t("mapTitle");
  const descText = dateRange
    ? `${t("mapDesc")} (${formatDateRange(dateRange.start, dateRange.end)})`
    : t("mapDesc");

  const svgElement = document.createElementNS(SVG_NS, "svg");
  const svg = select(svgElement)
    .attr("class", "choropleth-svg")
    .attr("viewBox", `0 0 ${MAP_DIMENSIONS.WIDTH} ${MAP_DIMENSIONS.HEIGHT}`)
    .attr("role", "group")
    .attr("aria-labelledby", "mapTitle mapDesc");

  svg
    .append("desc")
    .attr("id", "mapDesc")
    .attr("class", "map-date-range-desc")
    .text(descText);

  const defs = svg.append("defs");
  // Place <title> inside <defs> so Chrome does not show a native hover tooltip
  // over our custom MapTooltip while aria-labelledby still resolves #mapTitle.
  defs.append("title").attr("id", "mapTitle").text(titleText);

  const yellowPattern = defs
    .append("pattern")
    .attr("id", "pattern-status-yellow")
    .attr("width", 8)
    .attr("height", 8)
    .attr("patternUnits", "userSpaceOnUse")
    .attr("patternTransform", "rotate(45)");
  yellowPattern
    .append("rect")
    .attr("width", 8)
    .attr("height", 8)
    .attr("fill", "var(--color-yellow)");
  yellowPattern
    .append("line")
    .attr("x1", 0)
    .attr("y1", 0)
    .attr("x2", 0)
    .attr("y2", 8)
    .attr("stroke", "rgba(0, 0, 0, 0.22)")
    .attr("stroke-width", 2);

  const redPattern = defs
    .append("pattern")
    .attr("id", "pattern-status-red")
    .attr("width", 8)
    .attr("height", 8)
    .attr("patternUnits", "userSpaceOnUse");
  redPattern
    .append("rect")
    .attr("width", 8)
    .attr("height", 8)
    .attr("fill", "var(--color-red)");
  redPattern
    .append("path")
    .attr("d", "M0 0 L8 8 M8 0 L0 8")
    .attr("stroke", "rgba(255, 255, 255, 0.28)")
    .attr("stroke-width", 1.5);

  const noDataPattern = defs
    .append("pattern")
    .attr("id", "pattern-status-no-data")
    .attr("width", 8)
    .attr("height", 8)
    .attr("patternUnits", "userSpaceOnUse");
  noDataPattern
    .append("rect")
    .attr("width", 8)
    .attr("height", 8)
    .attr("fill", "var(--color-no-data)");
  noDataPattern
    .append("circle")
    .attr("cx", 4)
    .attr("cy", 4)
    .attr("r", 1.5)
    .attr("fill", "rgba(255, 255, 255, 0.45)");

  const tooltip = new MapTooltip();
  const countyGroup = svg.append("g").attr("class", "counties-layer");

  countyGroup
    .selectAll<SVGPathElement, Feature<Geometry, CountyProperties>>(
      "path.county-path",
    )
    .data(geojson.features)
    .join("path")
    .attr("class", (d) => {
      const countyName = d.properties?.name ?? "";
      const rate = rateByCounty.get(countyName.toLowerCase()) ?? null;
      const statusClass = getClearanceStatus(rate);
      const isSelected = Boolean(
        selectedCounty &&
        countyName.toLowerCase() === selectedCounty.toLowerCase(),
      );
      return `county-path ${statusClass}${isSelected ? " is-selected" : ""}`;
    })
    .attr("data-county", (d) => d.properties?.name ?? "")
    .attr("tabindex", "0")
    .attr("role", "button")
    .attr("aria-label", (d) => {
      const countyName = d.properties?.name ?? "";
      const rate = rateByCounty.get(countyName.toLowerCase()) ?? null;
      return `${countyName}: ${formatClearanceRate(rate)}`;
    })
    .attr("aria-pressed", (d) => {
      const countyName = d.properties?.name ?? "";
      const isSelected = Boolean(
        selectedCounty &&
        countyName.toLowerCase() === selectedCounty.toLowerCase(),
      );
      return isSelected ? "true" : "false";
    })
    .attr("d", (d) => pathGenerator(d) ?? "")
    .on("mouseover", (event: MouseEvent, d) => {
      const countyName = d.properties?.name ?? "";
      const rate = rateByCounty.get(countyName.toLowerCase()) ?? null;
      tooltip.show(`${countyName}: ${formatClearanceRate(rate)}`, {
        clientX: event.clientX,
        clientY: event.clientY,
      });
    })
    .on("mousemove", (event: MouseEvent) => {
      tooltip.move({
        clientX: event.clientX,
        clientY: event.clientY,
      });
    })
    .on("mouseout", () => {
      tooltip.hide();
    })
    .on("focus", (event: FocusEvent, d) => {
      const countyName = d.properties?.name ?? "";
      const rate = rateByCounty.get(countyName.toLowerCase()) ?? null;
      const pathEl = event.currentTarget as SVGPathElement;
      tooltip.showForElement(
        `${countyName}: ${formatClearanceRate(rate)}`,
        pathEl,
      );
    })
    .on("blur", () => {
      tooltip.hide();
    })
    .on("click", (event, d) => {
      const countyName = d.properties?.name ?? "";
      const pathEl = event.currentTarget as SVGPathElement;
      const isSelected = pathEl.classList.contains("is-selected");
      const nextSelected = isSelected ? null : countyName;
      onSelectCounty?.(nextSelected);
      pathEl.dispatchEvent(
        new CustomEvent("countySelected", {
          bubbles: true,
          detail: { county: nextSelected },
        }),
      );
    })
    .on("keydown", (event: KeyboardEvent, d) => {
      if (event.key === "Escape") {
        tooltip.hide();
        onSelectCounty?.(null);
        const pathEl = event.currentTarget as SVGPathElement;
        pathEl.dispatchEvent(
          new CustomEvent("countySelected", {
            bubbles: true,
            detail: { county: null },
          }),
        );
        return;
      }
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        const countyName = d.properties?.name ?? "";
        const pathEl = event.currentTarget as SVGPathElement;
        const isSelected = pathEl.classList.contains("is-selected");
        const nextSelected = isSelected ? null : countyName;
        onSelectCounty?.(nextSelected);
        pathEl.dispatchEvent(
          new CustomEvent("countySelected", {
            bubbles: true,
            detail: { county: nextSelected },
          }),
        );
      }
    });

  return svgElement;
}
