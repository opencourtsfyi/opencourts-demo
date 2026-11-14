import { describe, it, expect, vi } from "vitest";
import {
  renderDateRangeSelector,
  updateDateRangeSelector,
} from "./DateRangeSelector";
import { t } from "../i18n";
import type { DateRangeFilter } from "../services/clearanceData";

describe("DateRangeSelector component", () => {
  const defaultAvailableRange: DateRangeFilter = {
    start: { year: 2023, month: 7 },
    end: { year: 2026, month: 6 },
  };

  const defaultSelectedRange: DateRangeFilter = {
    start: { year: 2024, month: 7 },
    end: { year: 2025, month: 6 },
  };

  it("renders accessible start and end date dropdown selectors", () => {
    const el = renderDateRangeSelector({
      availableRange: defaultAvailableRange,
      selectedRange: defaultSelectedRange,
    });

    const startSelect = el.querySelector<HTMLSelectElement>("#start-date");
    const endSelect = el.querySelector<HTMLSelectElement>("#end-date");
    const startLabel = el.querySelector<HTMLLabelElement>(
      "label[for='start-date']",
    );
    const endLabel = el.querySelector<HTMLLabelElement>(
      "label[for='end-date']",
    );

    expect(startSelect).not.toBeNull();
    expect(endSelect).not.toBeNull();
    expect(startLabel?.textContent).toBe(t("startDateLabel"));
    expect(endLabel?.textContent).toBe(t("endDateLabel"));
    expect(startSelect?.getAttribute("aria-label")).toBe(t("startDateLabel"));
    expect(endSelect?.getAttribute("aria-label")).toBe(t("endDateLabel"));
  });

  it("populates start and end options within available range bounds without disabled options", () => {
    const el = renderDateRangeSelector({
      availableRange: defaultAvailableRange,
      selectedRange: defaultSelectedRange,
    });

    const startSelect = el.querySelector<HTMLSelectElement>("#start-date");
    const endSelect = el.querySelector<HTMLSelectElement>("#end-date");

    const startOptions = Array.from(startSelect?.options ?? []);
    const endOptions = Array.from(endSelect?.options ?? []);

    expect(startOptions.length).toBeGreaterThan(0);
    expect(endOptions.length).toBeGreaterThan(0);

    // Earliest start date is July 2023
    expect(startOptions[0].value).toBe("2023-07");
    // Latest start date is June 2026 (same as latest data month)
    expect(startOptions[startOptions.length - 1].value).toBe("2026-06");

    // Earliest end date is July 2023 (same as earliest data month)
    expect(endOptions[0].value).toBe("2023-07");
    // Latest end date is June 2026
    expect(endOptions[endOptions.length - 1].value).toBe("2026-06");

    // Verify no individual options are disabled/greyed out
    expect(startOptions.filter((o) => o.disabled)).toHaveLength(0);
    expect(endOptions.filter((o) => o.disabled)).toHaveLength(0);
  });

  it("disables both date dropdowns when disabled option is true", () => {
    const el = renderDateRangeSelector({
      availableRange: defaultAvailableRange,
      selectedRange: defaultSelectedRange,
      disabled: true,
    });

    const startSelect = el.querySelector<HTMLSelectElement>("#start-date");
    const endSelect = el.querySelector<HTMLSelectElement>("#end-date");

    expect(startSelect?.disabled).toBe(true);
    expect(endSelect?.disabled).toBe(true);
  });

  it("auto-advances end date to match start date when start date is moved past end date", () => {
    const onDateRangeChange = vi.fn();
    const el = renderDateRangeSelector({
      availableRange: defaultAvailableRange,
      selectedRange: {
        start: { year: 2024, month: 7 },
        end: { year: 2024, month: 9 },
      },
      onDateRangeChange,
    });

    const startSelect = el.querySelector<HTMLSelectElement>("#start-date")!;
    const endSelect = el.querySelector<HTMLSelectElement>("#end-date")!;

    // Move start date to October 2024 (after current September 2024 end date)
    startSelect.value = "2024-10";
    startSelect.dispatchEvent(new Event("change", { bubbles: true }));

    // End date should auto-advance to October 2024
    expect(endSelect.value).toBe("2024-10");
    expect(onDateRangeChange).toHaveBeenCalledWith({
      start: { year: 2024, month: 10 },
      end: { year: 2024, month: 10 },
    });
  });

  it("auto-adjusts start date backward to match end date when end date is moved before start date", () => {
    const onDateRangeChange = vi.fn();
    const el = renderDateRangeSelector({
      availableRange: defaultAvailableRange,
      selectedRange: {
        start: { year: 2024, month: 7 },
        end: { year: 2024, month: 9 },
      },
      onDateRangeChange,
    });

    const startSelect = el.querySelector<HTMLSelectElement>("#start-date")!;
    const endSelect = el.querySelector<HTMLSelectElement>("#end-date")!;

    // Move end date to June 2024 (before current July 2024 start date)
    endSelect.value = "2024-06";
    endSelect.dispatchEvent(new Event("change", { bubbles: true }));

    // Start date should auto-adjust backward to June 2024
    expect(startSelect.value).toBe("2024-06");
    expect(onDateRangeChange).toHaveBeenCalledWith({
      start: { year: 2024, month: 6 },
      end: { year: 2024, month: 6 },
    });
  });

  it("allows start date to be selected equal to current end date (1 month of data)", () => {
    const onDateRangeChange = vi.fn();
    const el = renderDateRangeSelector({
      availableRange: defaultAvailableRange,
      selectedRange: {
        start: { year: 2024, month: 7 },
        end: { year: 2024, month: 9 },
      },
      onDateRangeChange,
    });

    const startSelect = el.querySelector<HTMLSelectElement>("#start-date")!;
    const endSelect = el.querySelector<HTMLSelectElement>("#end-date")!;

    // Select start date identical to current end date (September 2024)
    startSelect.value = "2024-09";
    startSelect.dispatchEvent(new Event("change", { bubbles: true }));

    // End date should remain September 2024
    expect(endSelect.value).toBe("2024-09");
    expect(onDateRangeChange).toHaveBeenCalledWith({
      start: { year: 2024, month: 9 },
      end: { year: 2024, month: 9 },
    });
  });

  it("prevents start date from moving before earliest data when selecting the earliest possible end date", () => {
    const onDateRangeChange = vi.fn();
    const el = renderDateRangeSelector({
      availableRange: defaultAvailableRange,
      selectedRange: {
        start: { year: 2024, month: 7 },
        end: { year: 2024, month: 9 },
      },
      onDateRangeChange,
    });

    const startSelect = el.querySelector<HTMLSelectElement>("#start-date")!;
    const endSelect = el.querySelector<HTMLSelectElement>("#end-date")!;

    // The earliest selectable end date is July 2023 (same as earliest data July 2023)
    const endOptions = Array.from(endSelect.options).map((o) => o.value);
    expect(endOptions[0]).toBe("2023-07");
    expect(endOptions).not.toContain("2023-06");

    // Selecting earliest end date pulls start date back to earliest possible data month (July 2023)
    endSelect.value = "2023-07";
    endSelect.dispatchEvent(new Event("change", { bubbles: true }));

    expect(startSelect.value).toBe("2023-07");
    expect(onDateRangeChange).toHaveBeenCalledWith({
      start: { year: 2023, month: 7 },
      end: { year: 2023, month: 7 },
    });

    // Start options do not allow anything before July 2023
    const startOptions = Array.from(startSelect.options).map((o) => o.value);
    expect(startOptions[0]).toBe("2023-07");
    expect(startOptions).not.toContain("2023-06");
  });

  it("prevents end date from moving after latest data when selecting the latest possible start date", () => {
    const onDateRangeChange = vi.fn();
    const el = renderDateRangeSelector({
      availableRange: defaultAvailableRange,
      selectedRange: {
        start: { year: 2024, month: 7 },
        end: { year: 2024, month: 9 },
      },
      onDateRangeChange,
    });

    const startSelect = el.querySelector<HTMLSelectElement>("#start-date")!;
    const endSelect = el.querySelector<HTMLSelectElement>("#end-date")!;

    // The latest selectable start date is June 2026 (same as latest data June 2026)
    const startOptions = Array.from(startSelect.options).map((o) => o.value);
    expect(startOptions[startOptions.length - 1]).toBe("2026-06");
    expect(startOptions).not.toContain("2026-07");

    // Selecting latest start date pushes end date forward to latest possible data month (June 2026)
    startSelect.value = "2026-06";
    startSelect.dispatchEvent(new Event("change", { bubbles: true }));

    expect(endSelect.value).toBe("2026-06");
    expect(onDateRangeChange).toHaveBeenCalledWith({
      start: { year: 2026, month: 6 },
      end: { year: 2026, month: 6 },
    });

    // End options do not allow anything after June 2026
    const endOptions = Array.from(endSelect.options).map((o) => o.value);
    expect(endOptions[endOptions.length - 1]).toBe("2026-06");
    expect(endOptions).not.toContain("2026-07");
  });

  it("disables controls with loading text while loading and rebuilds options when updated with a new availableRange", () => {
    const el = renderDateRangeSelector({
      availableRange: defaultAvailableRange,
      selectedRange: defaultSelectedRange,
      loading: true,
    });

    const startSelect = el.querySelector<HTMLSelectElement>("#start-date")!;
    const endSelect = el.querySelector<HTMLSelectElement>("#end-date")!;

    expect(startSelect.disabled).toBe(true);
    expect(endSelect.disabled).toBe(true);
    expect(startSelect.selectedOptions[0]?.textContent).toMatch(/loading/i);
    expect(endSelect.selectedOptions[0]?.textContent).toMatch(/loading/i);

    const loadedRange: DateRangeFilter = {
      start: { year: 2015, month: 1 },
      end: { year: 2016, month: 12 },
    };

    updateDateRangeSelector(el, {
      availableRange: loadedRange,
      selectedRange: loadedRange,
      disabled: false,
      loading: false,
    });

    expect(startSelect.disabled).toBe(false);
    expect(endSelect.disabled).toBe(false);

    const startValues = Array.from(startSelect.options).map((o) => o.value);
    const endValues = Array.from(endSelect.options).map((o) => o.value);

    expect(startValues).toContain("2015-01");
    expect(startValues).not.toContain("2023-07");
    expect(endValues).toContain("2016-12");
    expect(endValues).not.toContain("2026-06");

    expect(startSelect.value).toBe("2015-01");
    expect(endSelect.value).toBe("2016-12");
  });
});
