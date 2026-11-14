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

  const ariaLabel = dateRange
    ? `${t("mapAriaLabel")} (${formatDateRange(dateRange.start, dateRange.end)})`
    : t("mapAriaLabel");

  const svgElement = document.createElementNS(SVG_NS, "svg");
  const svg = select(svgElement)
    .attr("class", "choropleth-svg")
    .attr("viewBox", `0 0 ${MAP_DIMENSIONS.WIDTH} ${MAP_DIMENSIONS.HEIGHT}`)
    .attr("role", "img")
    .attr("aria-label", ariaLabel);

  if (dateRange) {
    svg
      .append("desc")
      .attr("class", "map-date-range-desc")
      .text(formatDateRange(dateRange.start, dateRange.end));
  }

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
    .attr("aria-selected", (d) => {
      const countyName = d.properties?.name ?? "";
      const isSelected = Boolean(
        selectedCounty &&
        countyName.toLowerCase() === selectedCounty.toLowerCase(),
      );
      return isSelected ? "true" : "false";
    })
    .attr("d", (d) => pathGenerator(d) ?? "")
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
    })
    .append("title")
    .text((d) => {
      const countyName = d.properties?.name ?? "";
      const rate = rateByCounty.get(countyName.toLowerCase()) ?? null;
      return `${countyName}: ${formatClearanceRate(rate)}`;
    });

  return svgElement;
}
