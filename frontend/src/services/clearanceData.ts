import {
  CASELOAD_METRICS,
  COMPLETENESS_CONFIG,
  CompletenessTier,
  type CompletenessTierType,
  DATE_SELECTION_CONSTRAINTS,
  DEFAULT_REPORT_PERIOD,
  GOLD_DATA_PATH,
  getCompletenessTier,
} from "../constants/clearanceThresholds";
import { generateMonthYearList, type YearMonth } from "../utils/formatters";

export interface GoldCaseloadRecord {
  file: string;
  category: string;
  month: number;
  year: number;
  county: string;
  metric: string;
  value: number | string | null;
}

export interface MonthlyPeriodPoint {
  year: number;
  month: number;
  added: number | null;
  disposed: number | null;
  clearanceRate: number | null;
  isReported: boolean;
  missingReason: string | null;
}

export interface CountyClearanceSummary {
  county: string;
  added: number;
  disposed: number;
  clearanceRate: number | null;
  reportedPeriods?: number;
  totalPeriods?: number;
  completenessRatio?: number;
  completenessTier?: CompletenessTierType;
  isSufficientData?: boolean;
  monthlySeries?: MonthlyPeriodPoint[];
}

export interface DateRangeFilter {
  start: YearMonth;
  end: YearMonth;
}

const YEAR_MULTIPLIER = 100;
const ZERO_CASES = 0;
const BLANK_REASON = "Blank";
const MISSING_REASON = "Missing";

function toYearMonthIndex(ym: YearMonth): number {
  return ym.year * YEAR_MULTIPLIER + ym.month;
}

function parseNumericValue(raw: number | string | null | undefined): {
  numeric: number | null;
  reason: string | null;
} {
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return { numeric: raw, reason: null };
  }
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (trimmed === "") {
      return { numeric: null, reason: BLANK_REASON };
    }
    const parsed = Number(trimmed);
    if (Number.isFinite(parsed)) {
      return { numeric: parsed, reason: null };
    }
    return { numeric: null, reason: trimmed };
  }
  return { numeric: null, reason: MISSING_REASON };
}

export function getDefaultDateRange(): DateRangeFilter {
  return {
    start: {
      year: DEFAULT_REPORT_PERIOD.START_YEAR,
      month: DEFAULT_REPORT_PERIOD.START_MONTH,
    },
    end: {
      year: DEFAULT_REPORT_PERIOD.END_YEAR,
      month: DEFAULT_REPORT_PERIOD.END_MONTH,
    },
  };
}

export function getDataDateBounds(
  records: readonly GoldCaseloadRecord[],
): DateRangeFilter | null {
  if (records.length === DATE_SELECTION_CONSTRAINTS.EMPTY_COUNT) {
    return null;
  }
  let earliestIdx = Number.POSITIVE_INFINITY;
  let latestIdx = Number.NEGATIVE_INFINITY;
  let earliestYM: YearMonth | null = null;
  let latestYM: YearMonth | null = null;

  for (const record of records) {
    if (record.category.trim().toLowerCase() !== "estate") {
      continue;
    }
    const idx = toYearMonthIndex({ year: record.year, month: record.month });
    if (idx < earliestIdx) {
      earliestIdx = idx;
      earliestYM = { year: record.year, month: record.month };
    }
    if (idx > latestIdx) {
      latestIdx = idx;
      latestYM = { year: record.year, month: record.month };
    }
  }

  if (!earliestYM || !latestYM) {
    return null;
  }
  return { start: earliestYM, end: latestYM };
}

interface PeriodAccumulator {
  added: number | null;
  disposed: number | null;
  addedReason: string | null;
  disposedReason: string | null;
}

export function aggregateClearanceRates(
  records: readonly GoldCaseloadRecord[],
  dateRange: DateRangeFilter = getDefaultDateRange(),
): CountyClearanceSummary[] {
  const startIdx = toYearMonthIndex(dateRange.start);
  const endIdx = toYearMonthIndex(dateRange.end);
  const expectedMonths = generateMonthYearList(dateRange.start, dateRange.end);
  const totalPeriods = expectedMonths.length;

  const countyMap = new Map<string, Map<number, PeriodAccumulator>>();

  for (const record of records) {
    if (record.category.trim().toLowerCase() !== "estate") {
      continue;
    }

    const recordIdx = toYearMonthIndex({
      year: record.year,
      month: record.month,
    });
    if (recordIdx < startIdx || recordIdx > endIdx) {
      continue;
    }

    if (
      record.metric !== CASELOAD_METRICS.ADDED &&
      record.metric !== CASELOAD_METRICS.DISPOSED
    ) {
      continue;
    }

    const countyName = record.county.trim();
    if (!countyName) {
      continue;
    }

    let periodMap = countyMap.get(countyName);
    if (!periodMap) {
      periodMap = new Map<number, PeriodAccumulator>();
      countyMap.set(countyName, periodMap);
    }

    let acc = periodMap.get(recordIdx);
    if (!acc) {
      acc = {
        added: null,
        disposed: null,
        addedReason: null,
        disposedReason: null,
      };
      periodMap.set(recordIdx, acc);
    }

    const { numeric, reason } = parseNumericValue(record.value);
    if (record.metric === CASELOAD_METRICS.ADDED) {
      acc.added = numeric;
      acc.addedReason = reason;
    } else if (record.metric === CASELOAD_METRICS.DISPOSED) {
      acc.disposed = numeric;
      acc.disposedReason = reason;
    }
  }

  const summaries: CountyClearanceSummary[] = [];
  for (const [county, periodMap] of countyMap.entries()) {
    let totalAdded = ZERO_CASES;
    let totalDisposed = ZERO_CASES;
    let reportedPeriods = ZERO_CASES;
    const monthlySeries: MonthlyPeriodPoint[] = [];

    for (const ym of expectedMonths) {
      const idx = toYearMonthIndex(ym);
      const acc = periodMap.get(idx);
      const isReported =
        acc !== undefined && acc.added !== null && acc.disposed !== null;

      if (isReported && acc) {
        reportedPeriods += 1;
        totalAdded += acc.added ?? ZERO_CASES;
        totalDisposed += acc.disposed ?? ZERO_CASES;
        const periodRate =
          (acc.added ?? ZERO_CASES) > ZERO_CASES
            ? (acc.disposed ?? ZERO_CASES) / (acc.added ?? ZERO_CASES)
            : null;
        monthlySeries.push({
          year: ym.year,
          month: ym.month,
          added: acc.added,
          disposed: acc.disposed,
          clearanceRate: periodRate,
          isReported: true,
          missingReason: null,
        });
      } else {
        const reason =
          acc?.addedReason ?? acc?.disposedReason ?? MISSING_REASON;
        monthlySeries.push({
          year: ym.year,
          month: ym.month,
          added: acc?.added ?? null,
          disposed: acc?.disposed ?? null,
          clearanceRate: null,
          isReported: false,
          missingReason: reason,
        });
      }
    }

    const completenessRatio =
      totalPeriods > ZERO_CASES ? reportedPeriods / totalPeriods : ZERO_CASES;
    const completenessTier = getCompletenessTier(reportedPeriods, totalPeriods);
    const isSufficientData =
      completenessTier !== CompletenessTier.INSUFFICIENT &&
      completenessRatio >= COMPLETENESS_CONFIG.MIN_REPORTING_RATIO;

    const clearanceRate =
      isSufficientData && totalAdded > ZERO_CASES
        ? totalDisposed / totalAdded
        : null;

    summaries.push({
      county,
      added: totalAdded,
      disposed: totalDisposed,
      clearanceRate,
      reportedPeriods,
      totalPeriods,
      completenessRatio,
      completenessTier,
      isSufficientData,
      monthlySeries,
    });
  }

  summaries.sort((a, b) => a.county.localeCompare(b.county));
  return summaries;
}

export async function loadGoldCaseloadRecords(
  url: string = GOLD_DATA_PATH,
): Promise<GoldCaseloadRecord[]> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load Gold JSON (${response.status})`);
  }
  return (await response.json()) as GoldCaseloadRecord[];
}
