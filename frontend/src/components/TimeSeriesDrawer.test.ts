import { describe, it, expect, vi } from "vitest";
import {
  buildTimelineSummaryText,
  renderTimeSeriesDrawer,
} from "./TimeSeriesDrawer";
import { CompletenessTier } from "../constants/clearanceThresholds";
import type { CountyClearanceSummary } from "../services/clearanceData";

describe("TimeSeriesDrawer component", () => {
  const partialSummary: CountyClearanceSummary = {
    county: "Allendale",
    added: 20,
    disposed: 18,
    clearanceRate: 0.9,
    reportedPeriods: 3,
    totalPeriods: 4,
    completenessRatio: 0.75,
    completenessTier: CompletenessTier.PARTIAL,
    isSufficientData: true,
    monthlySeries: [
      {
        year: 2025,
        month: 7,
        added: 10,
        disposed: 9,
        clearanceRate: 0.9,
        isReported: true,
        missingReason: null,
      },
      {
        year: 2025,
        month: 8,
        added: null,
        disposed: null,
        clearanceRate: null,
        isReported: false,
        missingReason: "DNR",
      },
      {
        year: 2025,
        month: 9,
        added: 5,
        disposed: 5,
        clearanceRate: 1.0,
        isReported: true,
        missingReason: null,
      },
      {
        year: 2025,
        month: 10,
        added: 5,
        disposed: 4,
        clearanceRate: 0.8,
        isReported: true,
        missingReason: null,
      },
    ],
  };

  it("breaks line segments across missing periods and marks missing points", () => {
    const onClose = vi.fn();
    const drawer = renderTimeSeriesDrawer(partialSummary, onClose);

    const segments = drawer.querySelectorAll("path.chart-line-segment");
    expect(segments).toHaveLength(2);

    const reportedPoints = drawer.querySelectorAll(
      "circle.chart-point-reported",
    );
    expect(reportedPoints).toHaveLength(3);

    const missingMarkers = drawer.querySelectorAll("g.chart-point-missing");
    expect(missingMarkers).toHaveLength(1);
    expect(missingMarkers[0].textContent).toContain("DNR");
  });

  it("renders dynamic screen reader summary identifying missing periods", () => {
    const summaryText = buildTimelineSummaryText(partialSummary);
    expect(summaryText).toContain("3 of 4 periods reported");
    expect(summaryText).toContain("August 2025 (DNR)");

    const drawer = renderTimeSeriesDrawer(partialSummary, vi.fn());
    const srEl = drawer.querySelector(".drawer-timeline-summary");
    expect(srEl?.getAttribute("aria-live")).toBe("polite");
    expect(srEl?.textContent).toBe(summaryText);
  });

  it("invokes onClose when close button is clicked", () => {
    const onClose = vi.fn();
    const drawer = renderTimeSeriesDrawer(partialSummary, onClose);
    const closeBtn =
      drawer.querySelector<HTMLButtonElement>(".drawer-close-btn");
    closeBtn?.click();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("announces complete reporting when no periods are missing and handles empty series", () => {
    const completeSummary: CountyClearanceSummary = {
      ...partialSummary,
      reportedPeriods: 1,
      totalPeriods: 1,
      completenessRatio: 1,
      completenessTier: CompletenessTier.COMPLETE,
      monthlySeries: [partialSummary.monthlySeries![0]],
    };
    expect(buildTimelineSummaryText(completeSummary)).toContain(
      "All 1 periods reported",
    );

    const emptySummary: CountyClearanceSummary = {
      county: "Pickens",
      added: 0,
      disposed: 0,
      clearanceRate: null,
      isSufficientData: false,
      monthlySeries: [],
    };
    const drawer = renderTimeSeriesDrawer(emptySummary, vi.fn());
    expect(drawer.querySelector(".drawer-empty-msg")).not.toBeNull();
  });
});
