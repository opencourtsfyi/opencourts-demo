import { describe, it, expect } from 'vitest';
import {
  ClearanceStatus,
  CLEARANCE_THRESHOLDS,
  getClearanceStatus,
  MAP_DIMENSIONS,
} from './clearanceThresholds';

describe('clearanceThresholds', () => {
  it('defines correct domain constants', () => {
    expect(CLEARANCE_THRESHOLDS.OPTIMAL_MIN).toBe(1.0);
    expect(CLEARANCE_THRESHOLDS.WARNING_MIN).toBe(0.8);
    expect(MAP_DIMENSIONS.WIDTH).toBe(800);
    expect(MAP_DIMENSIONS.HEIGHT).toBe(560);
  });

  it('classifies rates >= 1.0 as GREEN', () => {
    expect(getClearanceStatus(1.0)).toBe(ClearanceStatus.GREEN);
    expect(getClearanceStatus(1.25)).toBe(ClearanceStatus.GREEN);
  });

  it('classifies rates between 0.8 and 1.0 as YELLOW', () => {
    expect(getClearanceStatus(0.8)).toBe(ClearanceStatus.YELLOW);
    expect(getClearanceStatus(0.99)).toBe(ClearanceStatus.YELLOW);
  });

  it('classifies rates below 0.8 as RED', () => {
    expect(getClearanceStatus(0.79)).toBe(ClearanceStatus.RED);
    expect(getClearanceStatus(0.0)).toBe(ClearanceStatus.RED);
  });

  it('classifies null or non-finite values as NO_DATA', () => {
    expect(getClearanceStatus(null)).toBe(ClearanceStatus.NO_DATA);
    expect(getClearanceStatus(NaN)).toBe(ClearanceStatus.NO_DATA);
    expect(getClearanceStatus(Infinity)).toBe(ClearanceStatus.NO_DATA);
  });
});

