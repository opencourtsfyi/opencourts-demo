export const CLEARANCE_THRESHOLDS = {
  OPTIMAL_MIN: 1.0,
  WARNING_MIN: 0.8,
} as const;

export const ClearanceStatus = {
  GREEN: "status-green",
  YELLOW: "status-yellow",
  RED: "status-red",
  NO_DATA: "status-no-data",
} as const;

export type ClearanceStatusType =
  (typeof ClearanceStatus)[keyof typeof ClearanceStatus];

export const MAP_DIMENSIONS = {
  WIDTH: 800,
  HEIGHT: 560,
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
  MIN_MONTH_DIFF: 1,
  MONTHS_PER_YEAR: 12,
  FIRST_MONTH_OF_YEAR: 1,
  EMPTY_COUNT: 0,
} as const;

export const GOLD_DATA_PATH = "/data/caseloads_sample.json";

export function getClearanceStatus(rate: number | null): ClearanceStatusType {
  if (rate === null || !Number.isFinite(rate)) {
    return ClearanceStatus.NO_DATA;
  }
  if (rate >= CLEARANCE_THRESHOLDS.OPTIMAL_MIN) {
    return ClearanceStatus.GREEN;
  }
  if (rate >= CLEARANCE_THRESHOLDS.WARNING_MIN) {
    return ClearanceStatus.YELLOW;
  }
  return ClearanceStatus.RED;
}
