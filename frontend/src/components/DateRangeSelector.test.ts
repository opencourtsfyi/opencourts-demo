import { describe, it, expect, vi } from "vitest";
import { renderDateRangeSelector } from "./DateRangeSelector";
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
    // Latest start date is May 2026 (1 month before June 2026)
    expect(startOptions[startOptions.length - 1].value).toBe("2026-05");

    // Earliest end date is August 2023 (1 month after July 2023)
    expect(endOptions[0].value).toBe("2023-08");
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

  it("auto-advances end date to start + 1 month when start date is moved past end date", () => {
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

    // End date should auto-advance to November 2024
    expect(endSelect.value).toBe("2024-11");
    expect(onDateRangeChange).toHaveBeenCalledWith({
      start: { year: 2024, month: 10 },
      end: { year: 2024, month: 11 },
    });
  });

  it("auto-adjusts start date backward to end - 1 month when end date is moved before start date", () => {
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

    // Move end date to July 2024 (same as or before current July 2024 start date)
    endSelect.value = "2024-07";
    endSelect.dispatchEvent(new Event("change", { bubbles: true }));

    // Start date should auto-adjust backward to June 2024
    expect(startSelect.value).toBe("2024-06");
    expect(onDateRangeChange).toHaveBeenCalledWith({
      start: { year: 2024, month: 6 },
      end: { year: 2024, month: 7 },
    });
  });
});
