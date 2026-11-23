import {
  CHART_DIMENSIONS,
  COMPLETENESS_CONFIG,
  CompletenessTier,
} from "../constants/clearanceThresholds";
import { t } from "../i18n";
import type {
  CountyClearanceSummary,
  MonthlyPeriodPoint,
} from "../services/clearanceData";
import { formatClearanceRate, formatMonthYear } from "../utils/formatters";

const SVG_NS = "http://www.w3.org/2000/svg";
const DEFAULT_MAX_RATE = 1.5;
const MIN_RATE = 0;
const RATE_HEADROOM_FACTOR = 1.1;
const PERCENT_FACTOR = 100;
const TICK_COUNT = 3;
const HALF_DIVISOR = 2;

function getCompletenessBadgeLabel(summary: CountyClearanceSummary): string {
  switch (summary.completenessTier) {
    case CompletenessTier.COMPLETE:
      return t("completenessComplete");
    case CompletenessTier.PARTIAL:
      return t("completenessPartial");
    default:
      return t("completenessInsufficient");
  }
}

export function buildTimelineSummaryText(
  summary: CountyClearanceSummary,
): string {
  const series = summary.monthlySeries ?? [];
  const total = summary.totalPeriods ?? series.length;
  const reported =
    summary.reportedPeriods ?? series.filter((p) => p.isReported).length;
  const missingPoints = series.filter((p) => !p.isReported);

  if (missingPoints.length === 0) {
    return t("drawerSummaryAllReported").replace("{total}", String(total));
  }

  const missingList = missingPoints
    .map(
      (p) =>
        `${formatMonthYear({ year: p.year, month: p.month })} (${p.missingReason ?? "Missing"})`,
    )
    .join(", ");

  return t("drawerSummaryWithMissing")
    .replace("{reported}", String(reported))
    .replace("{total}", String(total))
    .replace("{missingCount}", String(missingPoints.length))
    .replace("{missingList}", missingList);
}

function renderTimeSeriesSvg(
  countyName: string,
  series: readonly MonthlyPeriodPoint[],
): SVGSVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "trendline-svg");
  svg.setAttribute(
    "viewBox",
    `0 0 ${CHART_DIMENSIONS.WIDTH} ${CHART_DIMENSIONS.HEIGHT}`,
  );
  svg.setAttribute("role", "img");
  svg.setAttribute(
    "aria-label",
    t("drawerChartAriaLabel").replace("{county}", countyName),
  );

  const plotWidth =
    CHART_DIMENSIONS.WIDTH -
    CHART_DIMENSIONS.PADDING_LEFT -
    CHART_DIMENSIONS.PADDING_RIGHT;
  const plotHeight =
    CHART_DIMENSIONS.HEIGHT -
    CHART_DIMENSIONS.PADDING_TOP -
    CHART_DIMENSIONS.PADDING_BOTTOM;

  const reportedRates = series
    .map((p) => p.clearanceRate)
    .filter((r): r is number => r !== null && Number.isFinite(r));
  const rawMax =
    reportedRates.length > 0 ? Math.max(...reportedRates) : DEFAULT_MAX_RATE;
  const maxRate = Math.max(DEFAULT_MAX_RATE, rawMax * RATE_HEADROOM_FACTOR);

  const xForIndex = (index: number): number => {
    if (series.length <= 1) {
      return CHART_DIMENSIONS.PADDING_LEFT + plotWidth / HALF_DIVISOR;
    }
    return (
      CHART_DIMENSIONS.PADDING_LEFT + (index / (series.length - 1)) * plotWidth
    );
  };

  const yForRate = (rate: number): number => {
    const clamped = Math.max(MIN_RATE, rate);
    return (
      CHART_DIMENSIONS.PADDING_TOP +
      plotHeight -
      (clamped / maxRate) * plotHeight
    );
  };

  // Horizontal gridlines & Y-axis labels
  for (let i = 0; i <= TICK_COUNT; i++) {
    const tickRate = (maxRate / TICK_COUNT) * i;
    const y = yForRate(tickRate);
    const grid = document.createElementNS(SVG_NS, "line");
    grid.setAttribute("class", "chart-gridline");
    grid.setAttribute("x1", String(CHART_DIMENSIONS.PADDING_LEFT));
    grid.setAttribute("x2", String(CHART_DIMENSIONS.PADDING_LEFT + plotWidth));
    grid.setAttribute("y1", String(y));
    grid.setAttribute("y2", String(y));
    svg.appendChild(grid);

    const label = document.createElementNS(SVG_NS, "text");
    label.setAttribute("class", "chart-axis-label");
    label.setAttribute("x", String(CHART_DIMENSIONS.PADDING_LEFT - 6));
    label.setAttribute("y", String(y));
    label.setAttribute("text-anchor", "end");
    label.setAttribute("dominant-baseline", "central");
    label.textContent = `${Math.round(tickRate * PERCENT_FACTOR)}%`;
    svg.appendChild(label);
  }

  // Break line across missing/non-numeric periods
  let currentPathData = "";
  series.forEach((point, idx) => {
    if (point.isReported && point.clearanceRate !== null) {
      const x = xForIndex(idx);
      const y = yForRate(point.clearanceRate);
      currentPathData +=
        currentPathData === "" ? `M ${x} ${y}` : ` L ${x} ${y}`;
    } else if (currentPathData !== "") {
      const path = document.createElementNS(SVG_NS, "path");
      path.setAttribute("class", "chart-line-segment");
      path.setAttribute("d", currentPathData);
      svg.appendChild(path);
      currentPathData = "";
    }
  });
  if (currentPathData !== "") {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("class", "chart-line-segment");
    path.setAttribute("d", currentPathData);
    svg.appendChild(path);
  }

  // Plot reported points & missing markers
  const baselineY = CHART_DIMENSIONS.PADDING_TOP + plotHeight;
  series.forEach((point, idx) => {
    const x = xForIndex(idx);
    const monthLabel = formatMonthYear({ year: point.year, month: point.month });
    if (point.isReported && point.clearanceRate !== null) {
      const y = yForRate(point.clearanceRate);
      const circle = document.createElementNS(SVG_NS, "circle");
      circle.setAttribute("class", "chart-point-reported");
      circle.setAttribute("cx", String(x));
      circle.setAttribute("cy", String(y));
      circle.setAttribute("r", String(CHART_DIMENSIONS.POINT_RADIUS));
      const title = document.createElementNS(SVG_NS, "title");
      title.textContent = `${monthLabel}: ${formatClearanceRate(point.clearanceRate)}`;
      circle.appendChild(title);
      svg.appendChild(circle);
    } else {
      const size = CHART_DIMENSIONS.MISSING_MARKER_SIZE;
      const markerGroup = document.createElementNS(SVG_NS, "g");
      markerGroup.setAttribute("class", "chart-point-missing");
      const cross = document.createElementNS(SVG_NS, "path");
      cross.setAttribute(
        "d",
        `M ${x - size} ${baselineY - size} L ${x + size} ${baselineY + size} M ${x + size} ${baselineY - size} L ${x - size} ${baselineY + size}`,
      );
      const title = document.createElementNS(SVG_NS, "title");
      title.textContent = `${monthLabel}: ${point.missingReason ?? "Missing"}`;
      markerGroup.append(cross, title);
      svg.appendChild(markerGroup);
    }
  });

  // Start & End X-axis labels
  if (series.length > 0) {
    const first = series[0];
    const last = series[series.length - 1];
    const startLabel = document.createElementNS(SVG_NS, "text");
    startLabel.setAttribute("class", "chart-axis-label");
    startLabel.setAttribute("x", String(xForIndex(0)));
    startLabel.setAttribute("y", String(CHART_DIMENSIONS.HEIGHT - 8));
    startLabel.setAttribute("text-anchor", "start");
    startLabel.textContent = formatMonthYear({
      year: first.year,
      month: first.month,
    });
    svg.appendChild(startLabel);

    if (series.length > 1) {
      const endLabel = document.createElementNS(SVG_NS, "text");
      endLabel.setAttribute("class", "chart-axis-label");
      endLabel.setAttribute("x", String(xForIndex(series.length - 1)));
      endLabel.setAttribute("y", String(CHART_DIMENSIONS.HEIGHT - 8));
      endLabel.setAttribute("text-anchor", "end");
      endLabel.textContent = formatMonthYear({
        year: last.year,
        month: last.month,
      });
      svg.appendChild(endLabel);
    }
  }

  return svg;
}

export function renderTimeSeriesDrawer(
  summary: CountyClearanceSummary,
  onClose: () => void,
): HTMLElement {
  const drawer = document.createElement("aside");
  drawer.className = "trendline-drawer";
  drawer.setAttribute("aria-labelledby", "drawerHeading");

  const header = document.createElement("div");
  header.className = "drawer-header";

  const heading = document.createElement("h3");
  heading.id = "drawerHeading";
  heading.textContent = t("drawerTitle").replace("{county}", summary.county);

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "drawer-close-btn";
  closeBtn.setAttribute("aria-label", t("drawerClose"));
  closeBtn.textContent = "×";
  closeBtn.addEventListener("click", () => onClose());

  header.append(heading, closeBtn);
  drawer.appendChild(header);

  const meta = document.createElement("div");
  meta.className = "drawer-meta";

  const badge = document.createElement("span");
  badge.className = `completeness-badge tier-${summary.completenessTier ?? CompletenessTier.INSUFFICIENT}`;
  badge.textContent = getCompletenessBadgeLabel(summary);

  const rateSpan = document.createElement("span");
  rateSpan.className = "drawer-overall-rate";
  rateSpan.textContent = summary.isSufficientData
    ? formatClearanceRate(summary.clearanceRate)
    : t("insufficientDataLabel");

  const reported = summary.reportedPeriods ?? 0;
  const total = summary.totalPeriods ?? 0;
  const pct = Math.round(
    (summary.completenessRatio ?? 0) * COMPLETENESS_CONFIG.PERCENT_MULTIPLIER,
  );
  const periodsSpan = document.createElement("span");
  periodsSpan.className = "drawer-periods-count";
  periodsSpan.textContent = t("completenessSummary")
    .replace("{reported}", String(reported))
    .replace("{total}", String(total))
    .replace("{percent}", String(pct));

  meta.append(badge, rateSpan, periodsSpan);
  drawer.appendChild(meta);

  const series = summary.monthlySeries ?? [];
  if (series.length > 0) {
    drawer.appendChild(renderTimeSeriesSvg(summary.county, series));

    const chartLegend = document.createElement("div");
    chartLegend.className = "drawer-chart-legend";
    chartLegend.innerHTML = `<span class="legend-dot-reported" aria-hidden="true"></span><span>${t("drawerLegendReported")}</span><span class="legend-cross-missing" aria-hidden="true">×</span><span>${t("drawerLegendMissing")}</span>`;
    drawer.appendChild(chartLegend);

    const srSummary = document.createElement("p");
    srSummary.className = "drawer-timeline-summary";
    srSummary.setAttribute("aria-live", "polite");
    srSummary.textContent = buildTimelineSummaryText(summary);
    drawer.appendChild(srSummary);
  } else {
    const emptyMsg = document.createElement("p");
    emptyMsg.className = "drawer-empty-msg";
    emptyMsg.textContent = t("drawerNoSeries");
    drawer.appendChild(emptyMsg);
  }

  return drawer;
}
