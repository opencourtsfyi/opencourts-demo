import {
  CASELOAD_METRICS,
  DEFAULT_REPORT_PERIOD,
  GOLD_DATA_PATH,
} from "../constants/clearanceThresholds";
import type { YearMonth } from "../utils/formatters";

export interface GoldCaseloadRecord {
  file: string;
  category: string;
  month: number;
  year: number;
  county: string;
  metric: string;
  value: number | string | null;
}

export interface CountyClearanceSummary {
  county: string;
  added: number;
  disposed: number;
  clearanceRate: number | null;
}

export interface DateRangeFilter {
  start: YearMonth;
  end: YearMonth;
}

const YEAR_MULTIPLIER = 100;
const ZERO_CASES = 0;

function toYearMonthIndex(ym: YearMonth): number {
  return ym.year * YEAR_MULTIPLIER + ym.month;
}

function parseNumericValue(raw: number | string | null): number | null {
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return raw;
  }
  if (typeof raw === "string" && raw.trim() !== "") {
    const parsed = Number(raw);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
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

export function aggregateClearanceRates(
  records: readonly GoldCaseloadRecord[],
  dateRange: DateRangeFilter = getDefaultDateRange(),
): CountyClearanceSummary[] {
  const startIdx = toYearMonthIndex(dateRange.start);
  const endIdx = toYearMonthIndex(dateRange.end);

  const totalsByCounty = new Map<string, { added: number; disposed: number }>();

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

    let totals = totalsByCounty.get(countyName);
    if (!totals) {
      totals = { added: ZERO_CASES, disposed: ZERO_CASES };
      totalsByCounty.set(countyName, totals);
    }

    const numericVal = parseNumericValue(record.value);
    if (numericVal === null) {
      continue;
    }

    if (record.metric === CASELOAD_METRICS.ADDED) {
      totals.added += numericVal;
    } else if (record.metric === CASELOAD_METRICS.DISPOSED) {
      totals.disposed += numericVal;
    }
  }

  const summaries: CountyClearanceSummary[] = [];
  for (const [county, totals] of totalsByCounty.entries()) {
    const clearanceRate =
      totals.added > ZERO_CASES ? totals.disposed / totals.added : null;
    summaries.push({
      county,
      added: totals.added,
      disposed: totals.disposed,
      clearanceRate,
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
