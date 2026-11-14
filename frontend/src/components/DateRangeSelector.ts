import { DATE_SELECTION_CONSTRAINTS } from "../constants/clearanceThresholds";
import { t } from "../i18n";
import type { DateRangeFilter } from "../services/clearanceData";
import {
  addMonths,
  compareYearMonth,
  formatMonthYear,
  generateMonthYearList,
  parseYearMonthValue,
  toYearMonthValue,
} from "../utils/formatters";

export interface DateRangeSelectorOptions {
  availableRange: DateRangeFilter;
  selectedRange: DateRangeFilter;
  disabled?: boolean;
  loading?: boolean;
  onDateRangeChange?: (newRange: DateRangeFilter) => void;
}

export interface DateRangeSelectorElement extends HTMLElement {
  _onDateRangeChange?: (newRange: DateRangeFilter) => void;
  _selectedRange?: DateRangeFilter;
}

function populateMonthOptions(
  select: HTMLSelectElement,
  months: ReturnType<typeof generateMonthYearList>,
  selectedMonth: DateRangeFilter["start"],
): void {
  const options: HTMLOptionElement[] = [];
  for (const ym of months) {
    const opt = document.createElement("option");
    opt.value = toYearMonthValue(ym);
    opt.textContent = formatMonthYear(ym);
    if (compareYearMonth(ym, selectedMonth) === 0) {
      opt.selected = true;
    }
    options.push(opt);
  }
  select.replaceChildren(...options);
  select.value = toYearMonthValue(selectedMonth);
}

function populateLoadingOption(select: HTMLSelectElement): void {
  const opt = document.createElement("option");
  opt.value = "";
  opt.textContent = t("loadingData");
  opt.selected = true;
  select.replaceChildren(opt);
}

function applyDateRangeSelectorOptions(
  container: DateRangeSelectorElement,
  startSelect: HTMLSelectElement,
  endSelect: HTMLSelectElement,
  options: DateRangeSelectorOptions,
): void {
  const {
    availableRange,
    selectedRange,
    disabled = false,
    loading = false,
    onDateRangeChange,
  } = options;

  container._onDateRangeChange = onDateRangeChange;
  container._selectedRange = selectedRange;

  const isDisabled = disabled || loading;
  startSelect.disabled = isDisabled;
  endSelect.disabled = isDisabled;

  if (loading) {
    populateLoadingOption(startSelect);
    populateLoadingOption(endSelect);
    return;
  }

  const maxStartMonth = addMonths(
    availableRange.end,
    -DATE_SELECTION_CONSTRAINTS.MIN_MONTH_DIFF,
  );
  const startMonths = generateMonthYearList(
    availableRange.start,
    maxStartMonth,
  );
  populateMonthOptions(startSelect, startMonths, selectedRange.start);

  const minEndMonth = addMonths(
    availableRange.start,
    DATE_SELECTION_CONSTRAINTS.MIN_MONTH_DIFF,
  );
  const endMonths = generateMonthYearList(minEndMonth, availableRange.end);
  populateMonthOptions(endSelect, endMonths, selectedRange.end);
}

export function updateDateRangeSelector(
  container: DateRangeSelectorElement,
  options: DateRangeSelectorOptions,
): void {
  const startSelect = container.querySelector<HTMLSelectElement>("#start-date");
  const endSelect = container.querySelector<HTMLSelectElement>("#end-date");
  if (!startSelect || !endSelect) return;

  applyDateRangeSelectorOptions(container, startSelect, endSelect, options);
}

export function renderDateRangeSelector(
  options: DateRangeSelectorOptions,
): DateRangeSelectorElement {
  const container = document.createElement("div") as DateRangeSelectorElement;
  container.className = "date-range-selector";
  container.setAttribute("role", "group");
  container.setAttribute(
    "aria-label",
    `${t("startDateLabel")} ${t("dateRangeSeparator")} ${t("endDateLabel")}`,
  );

  // Start Date Control
  const startControl = document.createElement("div");
  startControl.className = "date-control start-date-control";

  const startLabel = document.createElement("label");
  startLabel.htmlFor = "start-date";
  startLabel.textContent = t("startDateLabel");

  const startSelect = document.createElement("select");
  startSelect.id = "start-date";
  startSelect.name = "startDate";
  startSelect.setAttribute("aria-label", t("startDateLabel"));

  startControl.append(startLabel, startSelect);

  // End Date Control
  const endControl = document.createElement("div");
  endControl.className = "date-control end-date-control";

  const endLabel = document.createElement("label");
  endLabel.htmlFor = "end-date";
  endLabel.textContent = t("endDateLabel");

  const endSelect = document.createElement("select");
  endSelect.id = "end-date";
  endSelect.name = "endDate";
  endSelect.setAttribute("aria-label", t("endDateLabel"));

  endControl.append(endLabel, endSelect);

  applyDateRangeSelectorOptions(container, startSelect, endSelect, options);

  // Events
  startSelect.addEventListener("change", () => {
    const newStart = parseYearMonthValue(startSelect.value);
    if (!newStart) return;

    let currentEnd =
      parseYearMonthValue(endSelect.value) ??
      container._selectedRange?.end ??
      options.selectedRange.end;
    const minValidEnd = addMonths(
      newStart,
      DATE_SELECTION_CONSTRAINTS.MIN_MONTH_DIFF,
    );
    if (compareYearMonth(currentEnd, minValidEnd) < 0) {
      currentEnd = minValidEnd;
      endSelect.value = toYearMonthValue(currentEnd);
    }

    if (container._onDateRangeChange) {
      container._onDateRangeChange({ start: newStart, end: currentEnd });
    }
  });

  endSelect.addEventListener("change", () => {
    let currentStart =
      parseYearMonthValue(startSelect.value) ??
      container._selectedRange?.start ??
      options.selectedRange.start;
    const newEnd = parseYearMonthValue(endSelect.value);
    if (!newEnd) return;

    const maxValidStart = addMonths(
      newEnd,
      -DATE_SELECTION_CONSTRAINTS.MIN_MONTH_DIFF,
    );
    if (compareYearMonth(currentStart, maxValidStart) > 0) {
      currentStart = maxValidStart;
      startSelect.value = toYearMonthValue(currentStart);
    }

    if (container._onDateRangeChange) {
      container._onDateRangeChange({ start: currentStart, end: newEnd });
    }
  });

  container.append(startControl, endControl);
  return container;
}
