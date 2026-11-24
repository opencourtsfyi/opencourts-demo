import { geoMercator, geoPath } from "d3-geo";
import { select } from "d3-selection";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import {
  COMPLETENESS_CONFIG,
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
const PATTERN_SIZE = 8;
const CENTER_DIVISOR = 2;

function getSummarySufficiency(summary?: CountyClearanceSummary): boolean {
  if (!summary) {
    return false;
  }
  if (summary.isSufficientData !== undefined) {
    return summary.isSufficientData;
  }
  return summary.clearanceRate !== null;
}

function formatCompletenessText(summary?: CountyClearanceSummary): string {
  if (!summary || summary.totalPeriods === undefined) {
    return t("completenessInsufficient");
  }
  const reported = summary.reportedPeriods ?? 0;
  const total = summary.totalPeriods;
  const ratio = summary.completenessRatio ?? 0;
  const percent = Math.round(ratio * COMPLETENESS_CONFIG.PERCENT_MULTIPLIER);
  return t("completenessSummary")
    .replace("{reported}", String(reported))
    .replace("{total}", String(total))
    .replace("{percent}", String(percent));
}

function buildRegionLabel(
  countyName: string,
  summary?: CountyClearanceSummary,
): string {
  const isSufficient = getSummarySufficiency(summary);
  const rateText = isSufficient
    ? formatClearanceRate(summary?.clearanceRate ?? null)
    : t("insufficientDataLabel");
  if (summary?.totalPeriods !== undefined) {
    return `${countyName}: ${rateText} (${formatCompletenessText(summary)})`;
  }
  return `${countyName}: ${rateText}`;
}

export function renderChoroplethMap(
  summaries: readonly CountyClearanceSummary[],
  topology?: ScTopology,
  dateRange?: DateRangeFilter,
  selectedCounty?: string | null,
  onSelectCounty?: (county: string | null) => void,
  describedById?: string,
  labelledById?: string,
): SVGSVGElement {
  const summaryByCounty = new Map<string, CountyClearanceSummary>();
  for (const item of summaries) {
    summaryByCounty.set(item.county.toLowerCase(), item);
  }

  const titleText = dateRange
    ? `${t("mapTitle")} (${formatDateRange(dateRange.start, dateRange.end)})`
    : t("mapTitle");
  const descText = dateRange
    ? `${t("mapDesc")} (${formatDateRange(dateRange.start, dateRange.end)})`
    : t("mapDesc");

  const svgElement = document.createElementNS(SVG_NS, "svg");
  const ariaLabelledBy = labelledById
    ? `${labelledById} mapTitle`
    : "mapTitle mapDesc";
  const svg = select(svgElement)
    .attr("class", "choropleth-svg")
    .attr("viewBox", `0 0 ${MAP_DIMENSIONS.WIDTH} ${MAP_DIMENSIONS.HEIGHT}`)
    .attr("role", "group")
    .attr("aria-labelledby", ariaLabelledBy);

  if (describedById) {
    svg.attr("aria-describedby", `mapDesc ${describedById}`);
  }

  svg
    .append("desc")
    .attr("id", "mapDesc")
    .attr("class", "map-date-range-desc")
    .text(descText);

  const defs = svg.append("defs");
  defs.append("title").attr("id", "mapTitle").text(titleText);

  const insufficientPattern = defs
    .append("pattern")
    .attr("id", "pattern-insufficient-data")
    .attr("width", PATTERN_SIZE)
    .attr("height", PATTERN_SIZE)
    .attr("patternUnits", "userSpaceOnUse")
    .attr("patternTransform", "rotate(45)");
  insufficientPattern
    .append("rect")
    .attr("width", PATTERN_SIZE)
    .attr("height", PATTERN_SIZE)
    .attr("fill", "var(--color-insufficient-bg)");
  insufficientPattern
    .append("line")
    .attr("x1", 0)
    .attr("y1", 0)
    .attr("x2", 0)
    .attr("y2", PATTERN_SIZE)
    .attr("stroke", "var(--color-insufficient-stripe)")
    .attr("stroke-width", 2.5);

  const countyGroup = svg.append("g").attr("class", "counties-layer");
  const calloutGroup = svg
    .append("g")
    .attr("class", "callouts-layer")
    .attr("aria-hidden", "true");

  if (!topology) {
    return svgElement;
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
  const tooltip = new MapTooltip();

  const paths = countyGroup
    .selectAll<SVGPathElement, Feature<Geometry, CountyProperties>>(
      "path.county-path",
    )
    .data(geojson.features)
    .join("path")
    .attr("class", (d) => {
      const countyName = d.properties?.name ?? "";
      const summary = summaryByCounty.get(countyName.toLowerCase());
      const isSufficient = getSummarySufficiency(summary);
      const statusClass = getClearanceStatus(
        summary?.clearanceRate ?? null,
        isSufficient,
      );
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
      const summary = summaryByCounty.get(countyName.toLowerCase());
      return buildRegionLabel(countyName, summary);
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
      const summary = summaryByCounty.get(countyName.toLowerCase());
      tooltip.show(buildRegionLabel(countyName, summary), {
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
      const summary = summaryByCounty.get(countyName.toLowerCase());
      const pathEl = event.currentTarget as SVGPathElement;
      tooltip.showForElement(buildRegionLabel(countyName, summary), pathEl);
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
        event.stopPropagation();
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

  paths.each(function (d) {
    const countyName = d.properties?.name ?? "";
    const summary = summaryByCounty.get(countyName.toLowerCase());
    if (getSummarySufficiency(summary)) {
      return;
    }
    const centroid = pathGenerator.centroid(d);
    if (
      !Number.isFinite(centroid[0]) ||
      !Number.isFinite(centroid[1]) ||
      typeof this.getBBox !== "function"
    ) {
      return;
    }
    const bbox = this.getBBox();
    if (
      bbox.width >= MAP_DIMENSIONS.CALLOUT_MIN_WIDTH &&
      bbox.height >= MAP_DIMENSIONS.CALLOUT_MIN_HEIGHT
    ) {
      calloutGroup
        .append("text")
        .attr("class", "insufficient-callout")
        .attr("x", bbox.x + bbox.width / CENTER_DIVISOR)
        .attr("y", bbox.y + bbox.height / CENTER_DIVISOR)
        .attr("text-anchor", "middle")
        .attr("dominant-baseline", "central")
        .text(t("insufficientDataShort"));
    }
  });

  return svgElement;
}
