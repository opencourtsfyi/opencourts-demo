export const CLEARANCE_THRESHOLDS = {
  TIER_LOW_MAX: 0.8,
  TIER_MODERATE_MAX: 1.0,
  TIER_HIGH_MAX: 1.2,
  OPTIMAL_MIN: 1.0,
  WARNING_MIN: 0.8,
} as const;

export const COMPLETENESS_CONFIG = {
  MIN_REPORTING_RATIO: 0.5,
  COMPLETE_RATIO: 1.0,
  PERCENT_MULTIPLIER: 100,
} as const;

export const ClearanceStatus = {
  TIER_1: "tier-1",
  TIER_2: "tier-2",
  TIER_3: "tier-3",
  TIER_4: "tier-4",
  INSUFFICIENT_DATA: "status-insufficient-data",
} as const;

export type ClearanceStatusType =
  (typeof ClearanceStatus)[keyof typeof ClearanceStatus];

export const CompletenessTier = {
  COMPLETE: "complete",
  PARTIAL: "partial",
  INSUFFICIENT: "insufficient",
} as const;

export type CompletenessTierType =
  (typeof CompletenessTier)[keyof typeof CompletenessTier];

export const MAP_DIMENSIONS = {
  WIDTH: 800,
  HEIGHT: 560,
  CALLOUT_MIN_WIDTH: 44,
  CALLOUT_MIN_HEIGHT: 30,
} as const;

export const DEFAULT_REPORT_PERIOD = {
  START_YEAR: 2025,
  START_MONTH: 7,
  END_YEAR: 2026,
  END_MONTH: 6,
} as const;

export const CASELOAD_METRICS = {
  ADDED: "Added",
  DISPOSED: "Disposed",
} as const;

export const DATE_SELECTION_CONSTRAINTS = {
  MIN_MONTH_DIFF: 0,
  MONTHS_PER_YEAR: 12,
  FIRST_MONTH_OF_YEAR: 1,
  EMPTY_COUNT: 0,
} as const;

export const TOOLTIP_CONFIG = {
  OFFSET_X: 12,
  OFFSET_Y: 12,
  VIEWPORT_PADDING: 16,
} as const;

export const CHART_DIMENSIONS = {
  WIDTH: 340,
  HEIGHT: 190,
  PADDING_TOP: 20,
  PADDING_RIGHT: 16,
  PADDING_BOTTOM: 34,
  PADDING_LEFT: 42,
  POINT_RADIUS: 4,
  MISSING_MARKER_SIZE: 4,
} as const;

export const GOLD_DATA_PATH = "/data/caseloads_sample.json";

export function getClearanceStatus(
  rate: number | null,
  isSufficientData = true,
): ClearanceStatusType {
  if (!isSufficientData || rate === null || !Number.isFinite(rate)) {
    return ClearanceStatus.INSUFFICIENT_DATA;
  }
  if (rate >= CLEARANCE_THRESHOLDS.TIER_HIGH_MAX) {
    return ClearanceStatus.TIER_4;
  }
  if (rate >= CLEARANCE_THRESHOLDS.TIER_MODERATE_MAX) {
    return ClearanceStatus.TIER_3;
  }
  if (rate >= CLEARANCE_THRESHOLDS.TIER_LOW_MAX) {
    return ClearanceStatus.TIER_2;
  }
  return ClearanceStatus.TIER_1;
}

export function getCompletenessTier(
  reportedPeriods: number,
  totalPeriods: number,
): CompletenessTierType {
  if (
    totalPeriods <= DATE_SELECTION_CONSTRAINTS.EMPTY_COUNT ||
    reportedPeriods <= DATE_SELECTION_CONSTRAINTS.EMPTY_COUNT
  ) {
    return CompletenessTier.INSUFFICIENT;
  }
  const ratio = reportedPeriods / totalPeriods;
  if (ratio >= COMPLETENESS_CONFIG.COMPLETE_RATIO) {
    return CompletenessTier.COMPLETE;
  }
  if (ratio >= COMPLETENESS_CONFIG.MIN_REPORTING_RATIO) {
    return CompletenessTier.PARTIAL;
  }
  return CompletenessTier.INSUFFICIENT;
}
