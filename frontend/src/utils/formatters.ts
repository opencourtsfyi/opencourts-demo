import { DEFAULT_LOCALE, t } from '../i18n';

const MONTH_INDEX_OFFSET = 1;
const DEFAULT_DAY_OF_MONTH = 1;
const PERCENT_MAX_FRACTION_DIGITS = 0;

export interface YearMonth {
  year: number;
  month: number;
}

export function formatMonthYear(yearMonth: YearMonth, locale: string = DEFAULT_LOCALE): string {
  const date = new Date(
    Date.UTC(yearMonth.year, yearMonth.month - MONTH_INDEX_OFFSET, DEFAULT_DAY_OF_MONTH),
  );
  return new Intl.DateTimeFormat(locale, {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date);
}

export function formatDateRange(
  start: YearMonth,
  end: YearMonth,
  locale: string = DEFAULT_LOCALE,
): string {
  const startLabel = formatMonthYear(start, locale);
  const endLabel = formatMonthYear(end, locale);
  return `${startLabel} ${t('dateRangeSeparator', locale)} ${endLabel}`;
}

export function formatClearanceRate(
  rate: number | null,
  locale: string = DEFAULT_LOCALE,
): string {
  if (rate === null || !Number.isFinite(rate)) {
    return t('noDataLabel', locale);
  }
  return new Intl.NumberFormat(locale, {
    style: 'percent',
    maximumFractionDigits: PERCENT_MAX_FRACTION_DIGITS,
  }).format(rate);
}
