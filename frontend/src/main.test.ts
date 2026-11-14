import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { t } from "./i18n";
import { initApp } from "./main";
import * as clearanceDataService from "./services/clearanceData";
import type { GoldCaseloadRecord } from "./services/clearanceData";

describe("initApp", () => {
  let root: HTMLElement;

  beforeEach(() => {
    root = document.createElement("div");
    root.id = "app";
    document.body.appendChild(root);
  });

  afterEach(() => {
    root.remove();
    vi.restoreAllMocks();
  });

  it("shows loadingData while fetch is in progress and hides it once records arrive", async () => {
    let resolveRecords!: (records: GoldCaseloadRecord[]) => void;
    const pendingRecords = new Promise<GoldCaseloadRecord[]>((resolve) => {
      resolveRecords = resolve;
    });

    vi.spyOn(
      clearanceDataService,
      "loadGoldCaseloadRecords",
    ).mockReturnValueOnce(pendingRecords);

    const initPromise = initApp(root);

    // While the network request is still in-flight (e.g., slow 3G),
    // show loadingData and do not show the empty-state notice.
    expect(root.textContent).toContain(t("loadingData"));
    expect(root.querySelector(".no-records-notice")).toBeNull();
    expect(root.textContent).not.toContain(t("noRecordsFound"));

    resolveRecords([
      {
        file: "test.csv",
        category: "Estate",
        year: 2025,
        month: 7,
        county: "Abbeville",
        metric: "Added",
        value: 10,
      },
      {
        file: "test.csv",
        category: "Estate",
        year: 2025,
        month: 7,
        county: "Abbeville",
        metric: "Disposed",
        value: 10,
      },
    ]);

    await initPromise;

    expect(root.textContent).not.toContain(t("loadingData"));
    expect(root.querySelector(".no-records-notice")).toBeNull();
    expect(root.querySelector(".county-name-cell")?.textContent).toBe(
      "Abbeville",
    );
  });

  it("shows loadingData while fetch is in progress and only shows 'No records found' after it finishes with 0 records", async () => {
    let resolveRecords!: (records: GoldCaseloadRecord[]) => void;
    const pendingRecords = new Promise<GoldCaseloadRecord[]>((resolve) => {
      resolveRecords = resolve;
    });

    vi.spyOn(
      clearanceDataService,
      "loadGoldCaseloadRecords",
    ).mockReturnValueOnce(pendingRecords);

    const initPromise = initApp(root);

    expect(root.textContent).toContain(t("loadingData"));
    expect(root.querySelector(".no-records-notice")).toBeNull();
    expect(root.textContent).not.toContain(t("noRecordsFound"));

    resolveRecords([]);
    await initPromise;

    expect(root.textContent).not.toContain(t("loadingData"));
    expect(root.querySelector(".no-records-notice")?.textContent).toBe(
      t("noRecordsFound"),
    );
    expect(root.textContent).toContain(t("noRecordsFound"));
  });
});
