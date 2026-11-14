import { DATE_SELECTION_CONSTRAINTS } from "../constants/clearanceThresholds";
import { DEFAULT_LOCALE, t } from "../i18n";

const MONTH_INDEX_OFFSET = 1;
const DEFAULT_DAY_OF_MONTH = 1;
const PERCENT_MAX_FRACTION_DIGITS = 0;
const PAD_LENGTH = 2;
const PAD_CHAR = "0";
const PARSE_SPLIT_DELIMITER = "-";
const EXPECTED_PARSE_PARTS = 2;
const YEAR_INDEX = 0;
const MONTH_INDEX = 1;

export interface YearMonth {
  year: number;
  month: number;
}

export function compareYearMonth(a: YearMonth, b: YearMonth): number {
  if (a.year !== b.year) {
    return a.year - b.year;
  }
  return a.month - b.month;
}

export function toYearMonthValue(ym: YearMonth): string {
  const monthStr = String(ym.month).padStart(PAD_LENGTH, PAD_CHAR);
  return `${ym.year}${PARSE_SPLIT_DELIMITER}${monthStr}`;
}

export function parseYearMonthValue(val: string): YearMonth | null {
  const parts = val.split(PARSE_SPLIT_DELIMITER);
  if (parts.length !== EXPECTED_PARSE_PARTS) {
    return null;
  }
  const year = Number(parts[YEAR_INDEX]);
  const month = Number(parts[MONTH_INDEX]);
  if (!Number.isInteger(year) || !Number.isInteger(month)) {
    return null;
  }
  if (
    month < DATE_SELECTION_CONSTRAINTS.FIRST_MONTH_OF_YEAR ||
    month > DATE_SELECTION_CONSTRAINTS.MONTHS_PER_YEAR
  ) {
    return null;
  }
  return { year, month };
}

export function addMonths(ym: YearMonth, count: number): YearMonth {
  const zeroBasedMonth =
    ym.month - DATE_SELECTION_CONSTRAINTS.FIRST_MONTH_OF_YEAR + count;
  const newYear =
    ym.year +
    Math.floor(zeroBasedMonth / DATE_SELECTION_CONSTRAINTS.MONTHS_PER_YEAR);
  const newMonth =
    (((zeroBasedMonth % DATE_SELECTION_CONSTRAINTS.MONTHS_PER_YEAR) +
      DATE_SELECTION_CONSTRAINTS.MONTHS_PER_YEAR) %
      DATE_SELECTION_CONSTRAINTS.MONTHS_PER_YEAR) +
    DATE_SELECTION_CONSTRAINTS.FIRST_MONTH_OF_YEAR;
  return { year: newYear, month: newMonth };
}

export function generateMonthYearList(
  start: YearMonth,
  end: YearMonth,
): YearMonth[] {
  const list: YearMonth[] = [];
  let current = { ...start };
  while (compareYearMonth(current, end) <= 0) {
    list.push(current);
    current = addMonths(current, DATE_SELECTION_CONSTRAINTS.MIN_MONTH_DIFF);
  }
  return list;
}

export function formatMonthYear(
  yearMonth: YearMonth,
  locale: string = DEFAULT_LOCALE,
): string {
  const date = new Date(
    Date.UTC(
      yearMonth.year,
      yearMonth.month - MONTH_INDEX_OFFSET,
      DEFAULT_DAY_OF_MONTH,
    ),
  );
  return new Intl.DateTimeFormat(locale, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function formatDateRange(
  start: YearMonth,
  end: YearMonth,
  locale: string = DEFAULT_LOCALE,
): string {
  const startLabel = formatMonthYear(start, locale);
  const endLabel = formatMonthYear(end, locale);
  return `${startLabel} ${t("dateRangeSeparator", locale)} ${endLabel}`;
}

export function formatClearanceRate(
  rate: number | null,
  locale: string = DEFAULT_LOCALE,
): string {
  if (rate === null || !Number.isFinite(rate)) {
    return t("noDataLabel", locale);
  }
  return new Intl.NumberFormat(locale, {
    style: "percent",
    maximumFractionDigits: PERCENT_MAX_FRACTION_DIGITS,
  }).format(rate);
}
