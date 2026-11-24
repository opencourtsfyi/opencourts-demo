import { describe, it, expect } from "vitest";
import {
  ClearanceStatus,
  CLEARANCE_THRESHOLDS,
  COMPLETENESS_CONFIG,
  CompletenessTier,
  getClearanceStatus,
  getCompletenessTier,
  MAP_DIMENSIONS,
} from "./clearanceThresholds";

describe("clearanceThresholds", () => {
  it("defines correct domain constants", () => {
    expect(CLEARANCE_THRESHOLDS.TIER_LOW_MAX).toBe(0.8);
    expect(CLEARANCE_THRESHOLDS.TIER_MODERATE_MAX).toBe(1.0);
    expect(CLEARANCE_THRESHOLDS.TIER_HIGH_MAX).toBe(1.2);
    expect(COMPLETENESS_CONFIG.MIN_REPORTING_RATIO).toBe(0.5);
    expect(MAP_DIMENSIONS.WIDTH).toBe(800);
    expect(MAP_DIMENSIONS.HEIGHT).toBe(560);
  });

  it("classifies rates into four sequential clearance tiers", () => {
    expect(getClearanceStatus(0.79)).toBe(ClearanceStatus.TIER_1);
    expect(getClearanceStatus(0.0)).toBe(ClearanceStatus.TIER_1);
    expect(getClearanceStatus(0.8)).toBe(ClearanceStatus.TIER_2);
    expect(getClearanceStatus(0.99)).toBe(ClearanceStatus.TIER_2);
    expect(getClearanceStatus(1.0)).toBe(ClearanceStatus.TIER_3);
    expect(getClearanceStatus(1.19)).toBe(ClearanceStatus.TIER_3);
    expect(getClearanceStatus(1.2)).toBe(ClearanceStatus.TIER_4);
  });

  it("classifies null, non-finite, or insufficient data as INSUFFICIENT_DATA", () => {
    expect(getClearanceStatus(null)).toBe(ClearanceStatus.INSUFFICIENT_DATA);
    expect(getClearanceStatus(NaN)).toBe(ClearanceStatus.INSUFFICIENT_DATA);
    expect(getClearanceStatus(Infinity)).toBe(
      ClearanceStatus.INSUFFICIENT_DATA,
    );
    expect(getClearanceStatus(1.05, false)).toBe(
      ClearanceStatus.INSUFFICIENT_DATA,
    );
  });

  it("classifies three-tier completeness ratios accurately", () => {
    expect(getCompletenessTier(12, 12)).toBe(CompletenessTier.COMPLETE);
    expect(getCompletenessTier(6, 12)).toBe(CompletenessTier.PARTIAL);
    expect(getCompletenessTier(5, 12)).toBe(CompletenessTier.INSUFFICIENT);
    expect(getCompletenessTier(0, 12)).toBe(CompletenessTier.INSUFFICIENT);
  });
});
