import { test, expect } from "@playwright/test";

test.describe("Map View", () => {
  test("loads the map page", async ({ page }) => {
    //Arrange

    //Act
    await page.goto("/");

    //Assert
    await expect(page).toHaveTitle(/OpenCourts/);
    await expect(
      page.getByRole("heading", { name: "SC County Probate Clearance Rates" }),
    ).toBeVisible();
    await expect(page.locator("svg.choropleth-svg")).toBeVisible();
    const aikenMapSection = page.locator("svg path[data-county='Aiken']");
    await expect(aikenMapSection).toBeVisible();
    await expect(aikenMapSection.locator("title")).toHaveText("Aiken: 97%");

    //Check Data Table
    await expect(page.getByRole("cell", { name: "Aiken" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "%" }).nth(1)).toHaveText(
      "97%",
    );
  });

  test("stacks legend items vertically on narrow screens (e.g. mobile viewport)", async ({
    page,
  }) => {
    // Set viewport to mobile width (e.g. 390px like an iPhone 12/13/14)
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");

    const legendList = page.locator(".legend-list");
    await expect(legendList).toBeVisible();
    await expect(legendList).toHaveCSS("flex-direction", "column");

    // Verify all legend items are vertically stacked (each item is below the previous one)
    const items = page.locator(".legend-item");
    const count = await items.count();
    expect(count).toBeGreaterThan(1);

    for (let i = 1; i < count; i++) {
      const prevBox = await items.nth(i - 1).boundingBox();
      const currBox = await items.nth(i).boundingBox();
      expect(prevBox).not.toBeNull();
      expect(currBox).not.toBeNull();
      if (prevBox && currBox) {
        expect(currBox.y).toBeGreaterThanOrEqual(prevBox.y + prevBox.height);
      }
    }
  });

  test.describe("Date Range Selector and Filtering", () => {
    test.beforeEach(async ({ page }) => {
      await page.goto("/");
    });

    test("renders start and end date dropdown selectors at the top of the map page with screen reader support", async ({
      page,
    }) => {
      // Dropdowns are rendered at top of page (in header or before the map section)
      const startDateSelect = page.getByRole("combobox", {
        name: /start date/i,
      });
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

    test("stacks date range selector dropdowns vertically on narrow screens (e.g. mobile viewport)", async ({
      page,
    }) => {
      // Set viewport to mobile width (390px - iPhone 12/13/14)
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto("/");

      const dateRangeSelector = page.locator(".date-range-selector");
      await expect(dateRangeSelector).toBeVisible();
      await expect(dateRangeSelector).toHaveCSS("flex-direction", "column");

      const startControl = page.locator(".start-date-control");
      const endControl = page.locator(".end-date-control");

      await expect(startControl).toBeVisible();
      await expect(endControl).toBeVisible();

      const startBox = await startControl.boundingBox();
      const endBox = await endControl.boundingBox();

      expect(startBox).not.toBeNull();
      expect(endBox).not.toBeNull();
      if (startBox && endBox) {
        expect(endBox.y).toBeGreaterThanOrEqual(startBox.y + startBox.height);
      }
    });

    test("changing the start date or end date reloads the map and data table for the range", async ({
      page,
    }) => {
      const startDateSelect = page.getByRole("combobox", {
        name: /start date/i,
      });
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
      const startDateSelect = page.getByRole("combobox", {
        name: /start date/i,
      });
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

      const startDateSelect = page.getByRole("combobox", {
        name: /start date/i,
      });
      const endDateSelect = page.getByRole("combobox", { name: /end date/i });

      // Date selectors must be disabled
      await expect(startDateSelect).toBeDisabled();
      await expect(endDateSelect).toBeDisabled();

      // Verify "No records found" is indicated
      await expect(page.locator("body")).toContainText(/no records found/i);
    });
  });

  test.describe("Bi-directional County Selection between Map and Table", () => {
    test.beforeEach(async ({ page }) => {
      await page.goto("/");
    });

    test("clicking a county on the map visually highlights both map path and table row", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const aikenRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Aiken" });

      await expect(aikenPath).toBeVisible();
      await expect(aikenRow).toBeVisible();

      // Click county path on the map
      await aikenPath.click();

      // Assert .is-selected class and aria-selected="true" on both
      await expect(aikenPath).toHaveClass(/is-selected/);
      await expect(aikenPath).toHaveAttribute("aria-selected", "true");
      await expect(aikenRow).toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveAttribute("aria-selected", "true");

      // Verify other counties remain unselected
      const abbevillePath = page.locator("svg path[data-county='Abbeville']");
      const abbevilleRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Abbeville" });
      await expect(abbevillePath).not.toHaveClass(/is-selected/);
      await expect(abbevillePath).toHaveAttribute("aria-selected", "false");
      await expect(abbevilleRow).not.toHaveClass(/is-selected/);
      await expect(abbevilleRow).toHaveAttribute("aria-selected", "false");
    });

    test("clicking a table row visually highlights both the table row and corresponding map path", async ({
      page,
    }) => {
      const aikenRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Aiken" });
      const aikenPath = page.locator("svg path[data-county='Aiken']");

      // Click row in table
      await aikenRow.click();

      await expect(aikenRow).toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveAttribute("aria-selected", "true");
      await expect(aikenPath).toHaveClass(/is-selected/);
      await expect(aikenPath).toHaveAttribute("aria-selected", "true");
    });

    test("clicking an already-selected county clears the selection on both map and table", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const aikenRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Aiken" });

      // Click to select
      await aikenPath.click();
      await expect(aikenPath).toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveClass(/is-selected/);

      // Re-click on map path to deselect
      await aikenPath.click();
      await expect(aikenPath).not.toHaveClass(/is-selected/);
      await expect(aikenPath).toHaveAttribute("aria-selected", "false");
      await expect(aikenRow).not.toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveAttribute("aria-selected", "false");

      // Select again via table row
      await aikenRow.click();
      await expect(aikenRow).toHaveClass(/is-selected/);

      // Re-click table row to deselect
      await aikenRow.click();
      await expect(aikenPath).not.toHaveClass(/is-selected/);
      await expect(aikenRow).not.toHaveClass(/is-selected/);
    });

    test("clicking anywhere outside the map or table clears the selection", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const aikenRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Aiken" });

      // Select county
      await aikenPath.click();
      await expect(aikenPath).toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveClass(/is-selected/);

      // Click outside (e.g. main page title heading)
      await page
        .getByRole("heading", { name: "SC County Probate Clearance Rates" })
        .click();

      await expect(aikenPath).not.toHaveClass(/is-selected/);
      await expect(aikenPath).toHaveAttribute("aria-selected", "false");
      await expect(aikenRow).not.toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveAttribute("aria-selected", "false");
    });

    test("supports selecting and deselecting via keyboard navigation (Enter and Space keys)", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const aikenRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Aiken" });

      // Focus map path and press Enter
      await aikenPath.focus();
      await page.keyboard.press("Enter");

      await expect(aikenPath).toHaveClass(/is-selected/);
      await expect(aikenPath).toHaveAttribute("aria-selected", "true");
      await expect(aikenRow).toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveAttribute("aria-selected", "true");

      // Focus table row and press Space to toggle off
      await aikenRow.focus();
      await page.keyboard.press("Space");

      await expect(aikenPath).not.toHaveClass(/is-selected/);
      await expect(aikenPath).toHaveAttribute("aria-selected", "false");
      await expect(aikenRow).not.toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveAttribute("aria-selected", "false");
    });

    test("clicking on a map county does not display a rectangular focus outline", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      await expect(aikenPath).toBeVisible();

      // Click / focus the county path
      await aikenPath.click();

      // Verify outline is none / 0px so no rectangular bounding box is shown
      await expect(aikenPath).toHaveCSS("outline-style", "none");
      await expect(aikenPath).toHaveCSS("outline-width", "0px");
    });

    test("selecting a date range clears active county selection on map and table", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const aikenRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Aiken" });

      // Select Aiken on map
      await aikenPath.click();
      await expect(aikenPath).toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveClass(/is-selected/);

      // Change start date
      const startDateSelect = page.getByRole("combobox", {
        name: /start date/i,
      });
      await startDateSelect.selectOption({ label: "July 2023" });

      // Verify active county selection is cleared on both map and table
      await expect(aikenPath).not.toHaveClass(/is-selected/);
      await expect(aikenPath).toHaveAttribute("aria-selected", "false");
      await expect(aikenRow).not.toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveAttribute("aria-selected", "false");
    });
  });
});
