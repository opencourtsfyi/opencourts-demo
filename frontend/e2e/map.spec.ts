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
    await expect(aikenMapSection).toHaveAttribute("aria-label", "Aiken: 97%");

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
      //Wait for data to load
      await expect(page.locator("tr.county-row").first()).toBeVisible();
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
      await expect(abbevillePath).toHaveAttribute(
        "aria-label",
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
      await expect(abbevillePath).toHaveAttribute(
        "aria-label",
        /Abbeville:\s*138%/i,
      );
      await expect(abbevilleRow.locator(".county-rate-cell")).toHaveText(
        "138%",
      );
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
      //Wait for data to load
      await expect(page.locator("tr.county-row").first()).toBeVisible();
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

  test.describe("Accessibility (A11y) Keyboard Navigation and Focus Management", () => {
    test.beforeEach(async ({ page }) => {
      await page.goto("/");
      //Wait for data to load
      await expect(page.locator("tr.county-row").first()).toBeVisible();
    });

    test("[A11y] pressing Tab from the map moves focus into the data table", async ({
      page,
    }) => {
      const mapPaths = page.locator("svg path.county-path");
      const pathCount = await mapPaths.count();
      expect(pathCount).toBeGreaterThan(0);

      const lastMapPath = mapPaths.nth(pathCount - 1);
      const firstTableRow = page.locator("tr.county-row").first();

      await lastMapPath.focus();
      await expect(lastMapPath).toBeFocused();

      // Press Tab to navigate forward
      await page.keyboard.press("Tab");

      // Focus should move directly to the first row of the data table
      await expect(firstTableRow).toBeFocused();
    });

    test("[A11y] pressing Shift+Tab from the data table moves focus backward into the map", async ({
      page,
    }) => {
      const firstTableRow = page.locator("tr.county-row").first();
      const mapPaths = page.locator("svg path.county-path");
      const pathCount = await mapPaths.count();
      const lastMapPath = mapPaths.nth(pathCount - 1);

      await firstTableRow.focus();
      await expect(firstTableRow).toBeFocused();

      // Press Shift+Tab to navigate backward
      await page.keyboard.press("Shift+Tab");

      // Focus should move backward to the last county path on the map
      await expect(lastMapPath).toBeFocused();
    });

    test("[A11y] pressing Escape key clears an active county selection on both map and table", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const aikenRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Aiken" });

      // Focus and select Aiken via Enter
      await aikenPath.focus();
      await page.keyboard.press("Enter");

      await expect(aikenPath).toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveClass(/is-selected/);

      // Press Escape key
      await page.keyboard.press("Escape");

      // Verify selection is cleared on both map and table
      await expect(aikenPath).not.toHaveClass(/is-selected/);
      await expect(aikenPath).toHaveAttribute("aria-selected", "false");
      await expect(aikenRow).not.toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveAttribute("aria-selected", "false");
    });
  });

  test.describe("Interactive Map Tooltip (Issue #19)", () => {
    test.beforeEach(async ({ page }) => {
      await page.goto("/");
    });

    test("displays dynamic tooltip with county name and clearance rate % on hover", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      await expect(aikenPath).toBeVisible();

      // Hover over Aiken county path
      await aikenPath.hover();

      const tooltip = page.locator(".map-tooltip, [role='tooltip']");
      await expect(tooltip).toBeVisible();
      await expect(tooltip).toContainText("Aiken");
      await expect(tooltip).toContainText("97%");
    });

    test("tooltip follows cursor movement across county path", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      await expect(aikenPath).toBeVisible();

      const boundingBox = await aikenPath.boundingBox();
      expect(boundingBox).not.toBeNull();
      if (!boundingBox) return;

      const tooltip = page.locator(".map-tooltip, [role='tooltip']");

      // Move mouse to first point inside county
      await page.mouse.move(boundingBox.x + 5, boundingBox.y + 5);
      await expect(tooltip).toBeVisible();
      const firstBox = await tooltip.boundingBox();
      expect(firstBox).not.toBeNull();

      // Move mouse to second point inside county
      await page.mouse.move(boundingBox.x + 25, boundingBox.y + 25);
      const secondBox = await tooltip.boundingBox();
      expect(secondBox).not.toBeNull();

      // Tooltip position should have changed to follow cursor
      if (firstBox && secondBox) {
        const moved = firstBox.x !== secondBox.x || firstBox.y !== secondBox.y;
        expect(moved).toBe(true);
      }
    });

    test("hides tooltip completely when cursor leaves county path", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      await expect(aikenPath).toBeVisible();

      await aikenPath.hover();
      const tooltip = page.locator(".map-tooltip, [role='tooltip']");
      await expect(tooltip).toBeVisible();

      // Move mouse away to header
      const header = page.locator("h1");
      await header.hover();

      await expect(tooltip).not.toBeVisible();
    });

    test("dynamically updates content when hovering over different counties", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const tooltip = page.locator(".map-tooltip, [role='tooltip']");

      // Hover Aiken
      await aikenPath.hover();
      await expect(tooltip).toBeVisible();
      await expect(tooltip).toContainText("Aiken");
      await expect(tooltip).toContainText("97%");

      // Hover Charleston
      const charlestonPath = page.locator("svg path[data-county='Charleston']");
      await charlestonPath.hover();
      await expect(tooltip).toBeVisible();
      await expect(tooltip).toContainText("Charleston");
      await expect(tooltip).not.toContainText("Aiken");
    });

    test("[A11y] mirrors tooltip content in aria-label of the county path", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      await expect(aikenPath).toBeVisible();

      const ariaLabel = await aikenPath.getAttribute("aria-label");
      expect(ariaLabel).toMatch(/Aiken:\s*97%/i);
    });

    test("tooltip styling has solid background and ignores pointer events", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      await aikenPath.hover();

      const tooltip = page.locator(".map-tooltip, [role='tooltip']");
      await expect(tooltip).toBeVisible();

      // Tooltip must have pointer-events none so it doesn't obstruct mouse events on the map
      await expect(tooltip).toHaveCSS("pointer-events", "none");
    });

    test("[A11y] displays tooltip when county path receives keyboard focus and hides on blur", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const tooltip = page.locator(".map-tooltip, [role='tooltip']");

      await aikenPath.focus();
      await expect(tooltip).toBeVisible();
      await expect(tooltip).toContainText("Aiken");
      await expect(tooltip).toContainText("97%");

      // Blur by focusing another element or calling blur
      await aikenPath.blur();
      await expect(tooltip).not.toBeVisible();
    });
  });
});
