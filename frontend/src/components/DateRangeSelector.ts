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
  onDateRangeChange?: (newRange: DateRangeFilter) => void;
}

export interface DateRangeSelectorElement extends HTMLElement {
  _onDateRangeChange?: (newRange: DateRangeFilter) => void;
}

export function renderDateRangeSelector(
  options: DateRangeSelectorOptions,
): DateRangeSelectorElement {
  const {
    availableRange,
    selectedRange,
    disabled = false,
    onDateRangeChange,
  } = options;

  const container = document.createElement("div") as DateRangeSelectorElement;
  container.className = "date-range-selector";
  container.setAttribute("role", "group");
  container.setAttribute(
    "aria-label",
    `${t("startDateLabel")} ${t("dateRangeSeparator")} ${t("endDateLabel")}`,
  );
  container._onDateRangeChange = onDateRangeChange;

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
  startSelect.disabled = disabled;

  // Generate start options: from earliest up to latest - 1 month
  const maxStartMonth = addMonths(
    availableRange.end,
    -DATE_SELECTION_CONSTRAINTS.MIN_MONTH_DIFF,
  );
  const startMonths = generateMonthYearList(
    availableRange.start,
    maxStartMonth,
  );

  for (const ym of startMonths) {
    const opt = document.createElement("option");
    opt.value = toYearMonthValue(ym);
    opt.textContent = formatMonthYear(ym);
    if (compareYearMonth(ym, selectedRange.start) === 0) {
      opt.selected = true;
    }
    startSelect.appendChild(opt);
  }

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
  endSelect.disabled = disabled;

  // Generate end options: from earliest + 1 month up to latest
  const endMonths = generateMonthYearList(
    availableRange.start,
    availableRange.end,
  );

  function updateEndOptionsDisabled(
    currentStartYM: typeof selectedRange.start,
  ): void {
    const minValidEnd = addMonths(
      currentStartYM,
      DATE_SELECTION_CONSTRAINTS.MIN_MONTH_DIFF,
    );
    for (const opt of Array.from(endSelect.options)) {
      const optYM = parseYearMonthValue(opt.value);
      if (optYM) {
        opt.disabled = compareYearMonth(optYM, minValidEnd) < 0;
      }
    }
  }

  for (const ym of endMonths) {
    const opt = document.createElement("option");
    opt.value = toYearMonthValue(ym);
    opt.textContent = formatMonthYear(ym);
    if (compareYearMonth(ym, selectedRange.end) === 0) {
      opt.selected = true;
    }
    endSelect.appendChild(opt);
  }

  updateEndOptionsDisabled(selectedRange.start);

  endControl.append(endLabel, endSelect);

  // Events
  startSelect.addEventListener("change", () => {
    const newStart = parseYearMonthValue(startSelect.value);
    if (!newStart) return;

    updateEndOptionsDisabled(newStart);

    let currentEnd = parseYearMonthValue(endSelect.value) ?? selectedRange.end;
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
    const currentStart =
      parseYearMonthValue(startSelect.value) ?? selectedRange.start;
    const newEnd = parseYearMonthValue(endSelect.value);
    if (!newEnd) return;

    const minValidEnd = addMonths(
      currentStart,
      DATE_SELECTION_CONSTRAINTS.MIN_MONTH_DIFF,
    );
    if (compareYearMonth(newEnd, minValidEnd) < 0) {
      // Revert if invalid
      endSelect.value = toYearMonthValue(selectedRange.end);
      return;
    }

    if (container._onDateRangeChange) {
      container._onDateRangeChange({ start: currentStart, end: newEnd });
    }
  });

  container.append(startControl, endControl);
  return container;
}
