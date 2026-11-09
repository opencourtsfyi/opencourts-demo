import { describe, it, expect } from "vitest";
import {
  formatClearanceRate,
  formatDateRange,
  formatMonthYear,
} from "./formatters";

describe("formatters", () => {
  it("formats month and year correctly in English", () => {
    expect(formatMonthYear({ year: 2025, month: 7 }, "en")).toBe("July 2025");
    expect(formatMonthYear({ year: 2026, month: 12 }, "en")).toBe(
      "December 2026",
    );
  });

  it("formats date range with localized separator", () => {
    const range = formatDateRange(
      { year: 2025, month: 7 },
      { year: 2026, month: 6 },
      "en",
    );
    expect(range).toBe("July 2025 to June 2026");
  });

  it("formats clearance rates as rounded percentages", () => {
    expect(formatClearanceRate(1.04, "en")).toBe("104%");
    expect(formatClearanceRate(0.88, "en")).toBe("88%");
    expect(formatClearanceRate(0.224, "en")).toBe("22%");
    expect(formatClearanceRate(0, "en")).toBe("0%");
  });

  it("returns fallback label for null or non-finite rates", () => {
    expect(formatClearanceRate(null, "en")).toBe("N/A");
    expect(formatClearanceRate(NaN, "en")).toBe("N/A");
  });
});
