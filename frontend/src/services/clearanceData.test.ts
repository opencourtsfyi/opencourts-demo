import { describe, it, expect, vi, afterEach } from "vitest";
import {
  aggregateClearanceRates,
  getDefaultDateRange,
  loadGoldCaseloadRecords,
  type GoldCaseloadRecord,
} from "./clearanceData";
import { CompletenessTier } from "../constants/clearanceThresholds";

describe("clearanceData service", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("getDefaultDateRange", () => {
    it("returns the default July 2025 - June 2026 date range", () => {
      const range = getDefaultDateRange();
      expect(range).toEqual({
        start: { year: 2025, month: 7 },
        end: { year: 2026, month: 6 },
      });
    });
  });

  describe("aggregateClearanceRates", () => {
    it("aggregates Added and Disposed counts and calculates clearance rate", () => {
      const records: GoldCaseloadRecord[] = [
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 7,
          county: "Aiken",
          metric: "Added",
          value: 100,
        },
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 7,
          county: "Aiken",
          metric: "Disposed",
          value: 85,
        },
      ];

      const summaries = aggregateClearanceRates(records, {
        start: { year: 2025, month: 7 },
        end: { year: 2025, month: 7 },
      });

      expect(summaries).toHaveLength(1);
      expect(summaries[0]).toMatchObject({
        county: "Aiken",
        added: 100,
        disposed: 85,
        clearanceRate: 0.85,
        reportedPeriods: 1,
        totalPeriods: 1,
        completenessRatio: 1,
        completenessTier: CompletenessTier.COMPLETE,
        isSufficientData: true,
      });
    });

    it("includes only Estate records regardless of category casing or whitespace", () => {
      const records: GoldCaseloadRecord[] = [
        {
          file: "test.csv",
          category: " Estate ",
          year: 2025,
          month: 7,
          county: "Aiken",
          metric: "Added",
          value: 100,
        },
        {
          file: "test.csv",
          category: "eStAtE",
          year: 2025,
          month: 7,
          county: "Aiken",
          metric: "Disposed",
          value: 80,
        },
        {
          file: "test.csv",
          category: "Trust",
          year: 2025,
          month: 7,
          county: "Aiken",
          metric: "Added",
          value: 900,
        },
        {
          file: "test.csv",
          category: "Trust",
          year: 2025,
          month: 7,
          county: "York",
          metric: "Added",
          value: 500,
        },
      ];

      const summaries = aggregateClearanceRates(records, {
        start: { year: 2025, month: 7 },
        end: { year: 2025, month: 7 },
      });

      expect(summaries).toHaveLength(1);
      expect(summaries[0]).toMatchObject({
        county: "Aiken",
        added: 100,
        disposed: 80,
        clearanceRate: 0.8,
      });
    });

    it("ignores records outside the specified date range", () => {
      const records: GoldCaseloadRecord[] = [
        {
          file: "test.csv",
          category: "Estate",
          year: 2024,
          month: 12,
          county: "Abbeville",
          metric: "Added",
          value: 50,
        },
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 7,
          county: "Abbeville",
          metric: "Added",
          value: 30,
        },
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 7,
          county: "Abbeville",
          metric: "Disposed",
          value: 0,
        },
      ];

      const summaries = aggregateClearanceRates(records, {
        start: { year: 2025, month: 7 },
        end: { year: 2025, month: 7 },
      });

      expect(summaries).toHaveLength(1);
      expect(summaries[0]).toMatchObject({
        county: "Abbeville",
        added: 30,
        disposed: 0,
        clearanceRate: 0,
      });
    });

    it("tracks non-numeric missingness reasons (DNR, TI, Blank, null) without treating them as 0", () => {
      const records: GoldCaseloadRecord[] = [
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 7,
          county: "Charleston",
          metric: "Added",
          value: "40",
        },
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 7,
          county: "Charleston",
          metric: "Disposed",
          value: 36,
        },
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 8,
          county: "Charleston",
          metric: "Added",
          value: "DNR",
        },
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 8,
          county: "Charleston",
          metric: "Disposed",
          value: "DNR",
        },
      ];

      const summaries = aggregateClearanceRates(records, {
        start: { year: 2025, month: 7 },
        end: { year: 2025, month: 8 },
      });

      expect(summaries[0].added).toBe(40);
      expect(summaries[0].disposed).toBe(36);
      expect(summaries[0].reportedPeriods).toBe(1);
      expect(summaries[0].totalPeriods).toBe(2);
      expect(summaries[0].completenessTier).toBe(CompletenessTier.PARTIAL);
      expect(summaries[0].isSufficientData).toBe(true);
      expect(summaries[0].monthlySeries?.[1]).toMatchObject({
        year: 2025,
        month: 8,
        isReported: false,
        missingReason: "DNR",
        clearanceRate: null,
      });
    });

    it("excludes counties below 50% reporting threshold as Insufficient Data", () => {
      const records: GoldCaseloadRecord[] = [
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 7,
          county: "Barnwell",
          metric: "Added",
          value: 20,
        },
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 7,
          county: "Barnwell",
          metric: "Disposed",
          value: 15,
        },
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 8,
          county: "Barnwell",
          metric: "Added",
          value: "TI",
        },
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 9,
          county: "Barnwell",
          metric: "Added",
          value: "",
        },
      ];

      const summaries = aggregateClearanceRates(records, {
        start: { year: 2025, month: 7 },
        end: { year: 2025, month: 9 },
      });

      expect(summaries[0].reportedPeriods).toBe(1);
      expect(summaries[0].totalPeriods).toBe(3);
      expect(summaries[0].completenessTier).toBe(CompletenessTier.INSUFFICIENT);
      expect(summaries[0].isSufficientData).toBe(false);
      expect(summaries[0].clearanceRate).toBeNull();
    });

    it("returns null clearanceRate when added cases is 0", () => {
      const records: GoldCaseloadRecord[] = [
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 7,
          county: "Barnwell",
          metric: "Disposed",
          value: 10,
        },
      ];

      const summaries = aggregateClearanceRates(records, {
        start: { year: 2025, month: 7 },
        end: { year: 2025, month: 7 },
      });

      expect(summaries[0].clearanceRate).toBeNull();
    });

    it("sorts summaries alphabetically by county", () => {
      const records: GoldCaseloadRecord[] = [
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 7,
          county: "York",
          metric: "Added",
          value: 10,
        },
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 7,
          county: "Aiken",
          metric: "Added",
          value: 20,
        },
      ];

      const summaries = aggregateClearanceRates(records, {
        start: { year: 2025, month: 7 },
        end: { year: 2025, month: 7 },
      });

      expect(summaries.map((s) => s.county)).toEqual(["Aiken", "York"]);
    });

    it("aggregates data correctly across multiple years", () => {
      const records: GoldCaseloadRecord[] = [
        {
          file: "2023_to_2024.csv",
          category: "Estate",
          year: 2023,
          month: 8,
          county: "Abbeville",
          metric: "Added",
          value: 50,
        },
        {
          file: "2023_to_2024.csv",
          category: "Estate",
          year: 2023,
          month: 8,
          county: "Abbeville",
          metric: "Disposed",
          value: 69,
        },
        {
          file: "2024_to_2025.csv",
          category: "Estate",
          year: 2024,
          month: 8,
          county: "Abbeville",
          metric: "Added",
          value: 100,
        },
        {
          file: "2024_to_2025.csv",
          category: "Estate",
          year: 2024,
          month: 8,
          county: "Abbeville",
          metric: "Disposed",
          value: 89,
        },
      ];

      const summaries2024 = aggregateClearanceRates(records, {
        start: { year: 2024, month: 8 },
        end: { year: 2024, month: 8 },
      });
      expect(summaries2024).toHaveLength(1);
      expect(summaries2024[0].added).toBe(100);
      expect(summaries2024[0].disposed).toBe(89);
      expect(summaries2024[0].clearanceRate).toBe(0.89);

      const summaries2023 = aggregateClearanceRates(records, {
        start: { year: 2023, month: 8 },
        end: { year: 2023, month: 8 },
      });
      expect(summaries2023).toHaveLength(1);
      expect(summaries2023[0].added).toBe(50);
      expect(summaries2023[0].disposed).toBe(69);
      expect(summaries2023[0].clearanceRate).toBe(1.38);
    });

    it("returns empty summaries when no records match the date range", () => {
      const records: GoldCaseloadRecord[] = [
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 7,
          county: "Aiken",
          metric: "Added",
          value: 10,
        },
      ];

      const summaries = aggregateClearanceRates(records, {
        start: { year: 2023, month: 1 },
        end: { year: 2023, month: 6 },
      });

      expect(summaries).toHaveLength(0);
    });
  });

  describe("loadGoldCaseloadRecords", () => {
    it("fetches and returns gold caseload records from URL", async () => {
      const mockRecords: GoldCaseloadRecord[] = [
        {
          file: "test.csv",
          category: "Estate",
          year: 2025,
          month: 7,
          county: "Aiken",
          metric: "Added",
          value: 10,
        },
      ];

      vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
        ok: true,
        json: async () => mockRecords,
      } as Response);

      const records = await loadGoldCaseloadRecords("/data/test.json");
      expect(records).toEqual(mockRecords);
    });

    it("throws error when fetch response is not ok", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
        ok: false,
        status: 404,
      } as Response);

      await expect(
        loadGoldCaseloadRecords("/data/missing.json"),
      ).rejects.toThrow("Failed to load Gold JSON (404)");
    });
  });
});
