import { test, expect } from '@playwright/test';

test.describe('Date Range Selector and Filtering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });
  //TODO move these tests into the map.spect.ts

  test("renders start and end date dropdown selectors at the top of the map page with screen reader support", async ({
    page,
  }) => {
    // Dropdowns are rendered at top of page (in header or before the map section)
    const startDateSelect = page.getByRole("combobox", { name: /start date/i });
    const endDateSelect = page.getByRole("combobox", { name: /end date/i });

    await expect(startDateSelect).toBeVisible();
    await expect(endDateSelect).toBeVisible();

    // Verify selectors are placed at top of the page (in header or before map section)
    const header = page.locator(".clearance-header, header");
    await expect(header).toBeVisible();

    // Verify accessible labels indicating their purpose to screen readers
    const startAccessibleName = await startDateSelect.evaluate((el) => {
      return (
        el.getAttribute("aria-label") ||
        (el as HTMLSelectElement).labels?.[0]?.textContent ||
        ""
      );
    });
    expect(startAccessibleName).toMatch(/start date/i);

    const endAccessibleName = await endDateSelect.evaluate((el) => {
      return (
        el.getAttribute("aria-label") ||
        (el as HTMLSelectElement).labels?.[0]?.textContent ||
        ""
      );
    });
    expect(endAccessibleName).toMatch(/end date/i);
  });

  test("a start date cannot be selected that's before the earliest date in the data", async ({
    page,
  }) => {
    // In the multi-year sample data, the earliest date is July 2023
    const startDateSelect = page.getByRole("combobox", { name: /start date/i });
    await expect(startDateSelect).toBeVisible();

    const options = await startDateSelect.locator("option").allInnerTexts();
    expect(options.length).toBeGreaterThan(0);

    // Verify no option exists for dates prior to July 2023 (e.g. 2022, June 2023, etc.)
    for (const text of options) {
      expect(text).not.toMatch(
        /2020|2021|2022|January 2023|February 2023|March 2023|April 2023|May 2023|June 2023/i,
      );
    }
  });

  test("the end date cannot be selected that's later than the latest date in the data", async ({
    page,
  }) => {
    // In the multi-year sample data, the latest date is June 2026
    const endDateSelect = page.getByRole("combobox", { name: /end date/i });
    await expect(endDateSelect).toBeVisible();

    const options = await endDateSelect.locator("option").allInnerTexts();
    expect(options.length).toBeGreaterThan(0);

    // Verify no option exists for dates after June 2026 (e.g. July 2026, 2027, etc.)
    for (const text of options) {
      expect(text).not.toMatch(
        /July 2026|August 2026|September 2026|October 2026|November 2026|December 2026|2027|2028/i,
      );
    }
  });

  test("end date must be at least 1 month later than the start date", async ({
    page,
  }) => {
    const startDateSelect = page.getByRole("combobox", { name: /start date/i });
    const endDateSelect = page.getByRole("combobox", { name: /end date/i });

    // Select October 2024 as the start date
    await startDateSelect.selectOption({ label: "October 2024" });

    // End date options for October 2024 or earlier must either not exist or be disabled
    const octOption = endDateSelect
      .locator("option")
      .filter({ hasText: /October 2024/i });
    const sepOption = endDateSelect
      .locator("option")
      .filter({ hasText: /September 2024/i });

    const octCount = await octOption.count();
    if (octCount > 0) {
      await expect(octOption).toBeDisabled();
    }
    const sepCount = await sepOption.count();
    if (sepCount > 0) {
      await expect(sepOption).toBeDisabled();
    }

    // Earliest valid end date must be at least November 2024 (1 month later)
    const novOption = endDateSelect
      .locator("option")
      .filter({ hasText: /November 2024/i });
    await expect(novOption).toBeEnabled();
  });

  test("changing the start date or end date reloads the map and data table for the range", async ({
    page,
  }) => {
    const startDateSelect = page.getByRole("combobox", { name: /start date/i });
    const endDateSelect = page.getByRole("combobox", { name: /end date/i });

    // Select July 2024 to June 2025
    await startDateSelect.selectOption({ label: "July 2024" });
    await endDateSelect.selectOption({ label: "June 2025" });

    // In 2024-2025, Abbeville rate is 89%
    const abbevillePath = page.locator("svg path[data-county='Abbeville']");
    await expect(abbevillePath.locator("title")).toHaveText(
      /Abbeville:\s*89%/i,
    );

    const abbevilleRow = page
      .locator("tr.county-row")
      .filter({ hasText: "Abbeville" });
    await expect(abbevilleRow.locator(".county-rate-cell")).toHaveText("89%");

    // Change to July 2023 to June 2024
    await startDateSelect.selectOption({ label: "July 2023" });
    await endDateSelect.selectOption({ label: "June 2024" });

    // In 2023-2024, Abbeville rate is 138%
    await expect(abbevillePath.locator("title")).toHaveText(
      /Abbeville:\s*138%/i,
    );
    await expect(abbevilleRow.locator(".county-rate-cell")).toHaveText("138%");
  });

  test("the start and end date should be displayed on the map and table to indicate their date ranges", async ({
    page,
  }) => {
    const startDateSelect = page.getByRole("combobox", { name: /start date/i });
    const endDateSelect = page.getByRole("combobox", { name: /end date/i });

    await startDateSelect.selectOption({ label: "July 2024" });
    await endDateSelect.selectOption({ label: "June 2025" });

    // Check map section displays the date range
    const mapSection = page.locator(".map-box");
    await expect(mapSection).toContainText(/July 2024\s+to\s+June 2025/i);

    // Check table section displays the date range
    const tableSection = page.locator(".table-section");
    await expect(tableSection).toContainText(/July 2024\s+to\s+June 2025/i);
  });

  test('if the data table does not have data for a given date range, indicate "No records found"', async ({
    page,
  }) => {
    // Intercept data request to return data with no records matching the selected range
    await page.route("**/data/caseloads_sample.json", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            file: "test.csv",
            category: "NonEstate",
            month: 7,
            year: 2025,
            county: "Aiken",
            metric: "Added",
            value: 10,
          },
        ]),
      });
    });

    await page.goto("/");

    // Data table indicates "No records found"
    const tableSection = page.locator(".table-section");
    await expect(tableSection).toContainText(/no records found/i);
  });

  test("if there is no data, disable the date selectors and indicate no records found", async ({
    page,
  }) => {
    // Intercept data request to return empty array
    await page.route("**/data/caseloads_sample.json", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto("/");

    const startDateSelect = page.getByRole("combobox", { name: /start date/i });
    const endDateSelect = page.getByRole("combobox", { name: /end date/i });

    // Date selectors must be disabled
    await expect(startDateSelect).toBeDisabled();
    await expect(endDateSelect).toBeDisabled();

    // Verify "No records found" is indicated
    await expect(page.locator("body")).toContainText(/no records found/i);
  });
});
