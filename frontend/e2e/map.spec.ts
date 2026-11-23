import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.describe("Map View", () => {
  test("loads the map page with bottom legend, hidden-by-default table, and lower-page methodology", async ({
    page,
  }) => {
    await page.goto("/");

    await expect(page).toHaveTitle(/OpenCourts/);
    await expect(
      page.getByRole("heading", { name: "SC County Probate Clearance Rates" }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "County Probate Clearance Rate Map" })).toBeVisible();

    const svgMap = page.locator("svg.choropleth-svg");
    await expect(svgMap).toBeVisible();
    await expect(svgMap).toHaveAttribute("aria-describedby", /mapMethodology/);

    const aikenMapSection = page.locator("svg path[data-county='Aiken']");
    await expect(aikenMapSection).toBeVisible();
    await expect(aikenMapSection).toHaveAttribute("aria-label", /Aiken:\s*97%/);

    // Legend is at the bottom of the map box
    const svgBox = await svgMap.boundingBox();
    const legendBox = await page.locator(".map-box .clearance-legend").boundingBox();
    expect(svgBox).not.toBeNull();
    expect(legendBox).not.toBeNull();
    if (svgBox && legendBox) {
      expect(legendBox.y).toBeGreaterThanOrEqual(svgBox.y + svgBox.height - 5);
    }

    // Methodology is below the workspace
    const methodology = page.locator("#mapMethodology");
    await expect(methodology).toBeVisible();
    const methBox = await methodology.boundingBox();
    if (legendBox && methBox) {
      expect(methBox.y).toBeGreaterThan(legendBox.y);
    }

    // Table is hidden by default and toggled via button
    const toggleBtn = page.locator(".table-toggle-btn");
    const tableWrapper = page.locator("#countyTableWrapper");
    await expect(toggleBtn).toHaveAttribute("aria-expanded", "false");
    await expect(tableWrapper).toBeHidden();

    await toggleBtn.click();
    await expect(toggleBtn).toHaveAttribute("aria-expanded", "true");
    await expect(tableWrapper).toBeVisible();

    const aikenHeader = page.getByRole("rowheader", { name: "Aiken" });
    await expect(aikenHeader).toBeVisible();
    await expect(aikenHeader).toHaveCSS("font-weight", "400");

    // Check favicon link and asset serving
    const faviconLink = page.locator('link[rel="icon"]');
    await expect(faviconLink).toHaveAttribute("href", "/favicon.svg");
    const faviconResponse = await page.request.get("/favicon.svg");
    expect(faviconResponse.status()).toBe(200);
    expect(await faviconResponse.text()).toContain("<svg");
  });

  test("stacks legend items vertically on narrow screens (e.g. mobile viewport)", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");

    const legendList = page.locator(".legend-list");
    await expect(legendList).toBeVisible();
    await expect(legendList).toHaveCSS("flex-direction", "column");

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

  test.describe("Issue #73 Three-Tier Completeness & Responsive Drawer", () => {
    test("opens side drawer on desktop and below-map drawer on mobile with broken line chart", async ({
      page,
    }) => {
      await page.route("**/data/caseloads_sample.json", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            // Aiken: 2 of 3 months reported (Partial) with DNR in Aug
            { file: "t.csv", category: "Estate", year: 2025, month: 7, county: "Aiken", metric: "Added", value: 50 },
            { file: "t.csv", category: "Estate", year: 2025, month: 7, county: "Aiken", metric: "Disposed", value: 45 },
            { file: "t.csv", category: "Estate", year: 2025, month: 8, county: "Aiken", metric: "Added", value: "DNR" },
            { file: "t.csv", category: "Estate", year: 2025, month: 8, county: "Aiken", metric: "Disposed", value: "DNR" },
            { file: "t.csv", category: "Estate", year: 2025, month: 9, county: "Aiken", metric: "Added", value: 50 },
            { file: "t.csv", category: "Estate", year: 2025, month: 9, county: "Aiken", metric: "Disposed", value: 55 },
            // Barnwell: 1 of 3 months reported (<50% -> Insufficient Data)
            { file: "t.csv", category: "Estate", year: 2025, month: 7, county: "Barnwell", metric: "Added", value: 20 },
            { file: "t.csv", category: "Estate", year: 2025, month: 7, county: "Barnwell", metric: "Disposed", value: 10 },
          ]),
        });
      });

      // Desktop viewport: side drawer
      await page.setViewportSize({ width: 1280, height: 800 });
      await page.goto("/");

      const barnwellPath = page.locator("svg path[data-county='Barnwell']");
      await expect(barnwellPath).toHaveClass(/status-insufficient-data/);
      await expect(barnwellPath).toHaveAttribute(
        "aria-label",
        /Barnwell:\s*Insufficient Data/,
      );

      const aikenPath = page.locator("svg path[data-county='Aiken']");
      await aikenPath.click();

      const drawer = page.locator(".trendline-drawer");
      await expect(drawer).toBeVisible();
      await expect(drawer.locator("path.chart-line-segment")).toHaveCount(2);
      await expect(drawer.locator("g.chart-point-missing")).toHaveCount(1);
      await expect(drawer.locator(".drawer-timeline-summary")).toContainText(
        "August 2025 (DNR)",
      );

      const mapBoxDesktop = await page.locator(".map-box").boundingBox();
      const drawerBoxDesktop = await drawer.boundingBox();
      expect(mapBoxDesktop).not.toBeNull();
      expect(drawerBoxDesktop).not.toBeNull();
      if (mapBoxDesktop && drawerBoxDesktop) {
        expect(drawerBoxDesktop.x).toBeGreaterThanOrEqual(
          mapBoxDesktop.x + mapBoxDesktop.width - 10,
        );
      }

      // Mobile viewport: below-map drawer
      await page.setViewportSize({ width: 390, height: 844 });
      const mapBoxMobile = await page.locator(".map-box").boundingBox();
      const drawerBoxMobile = await drawer.boundingBox();
      expect(mapBoxMobile).not.toBeNull();
      expect(drawerBoxMobile).not.toBeNull();
      if (mapBoxMobile && drawerBoxMobile) {
        expect(drawerBoxMobile.y).toBeGreaterThanOrEqual(
          mapBoxMobile.y + mapBoxMobile.height - 10,
        );
      }

      // Close drawer via close button
      await drawer.locator(".drawer-close-btn").click();
      await expect(drawer).toHaveCount(0);
    });
  });

  test.describe("Date Range Selector and Filtering", () => {
    test.beforeEach(async ({ page }) => {
      await page.goto("/");
      await page.locator(".table-toggle-btn").click();
      await expect(page.locator("tr.county-row").first()).toBeVisible();
    });

    test("renders start and end date dropdown selectors at the top of the map page with screen reader support", async ({
      page,
    }) => {
      const startDateSelect = page.getByRole("combobox", {
        name: /start date/i,
      });
      const endDateSelect = page.getByRole("combobox", { name: /end date/i });

      await expect(startDateSelect).toBeVisible();
      await expect(endDateSelect).toBeVisible();

      const header = page.locator(".clearance-header, header");
      await expect(header).toBeVisible();
    });

    test("stacks date range selector dropdowns vertically on narrow screens (e.g. mobile viewport)", async ({
      page,
    }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto("/");

      const dateRangeSelector = page.locator(".date-range-selector");
      await expect(dateRangeSelector).toBeVisible();
      await expect(dateRangeSelector).toHaveCSS("flex-direction", "column");

      const startControl = page.locator(".start-date-control");
      const endControl = page.locator(".end-date-control");

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

      await startDateSelect.selectOption({ label: "July 2024" });
      await endDateSelect.selectOption({ label: "June 2025" });

      const abbevillePath = page.locator("svg path[data-county='Abbeville']");
      await expect(abbevillePath).toHaveAttribute(
        "aria-label",
        /Abbeville:\s*89%/i,
      );

      const abbevilleRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Abbeville" });
      await expect(abbevilleRow.locator(".county-rate-cell")).toHaveText("89%");

      await startDateSelect.selectOption({ label: "July 2023" });
      await endDateSelect.selectOption({ label: "June 2024" });

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

      await expect(page.locator(".map-box")).toContainText(
        /July 2024\s+to\s+June 2025/i,
      );
      await expect(page.locator(".table-section")).toContainText(
        /July 2024\s+to\s+June 2025/i,
      );
    });

    test('if the data table does not have data for a given date range, indicate "No records found"', async ({
      page,
    }) => {
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
      await page.locator(".table-toggle-btn").click();
      await expect(page.locator(".table-section")).toContainText(
        /no records found/i,
      );
    });

    test("if there is no data, disable the date selectors and indicate no records found", async ({
      page,
    }) => {
      await page.route("**/data/caseloads_sample.json", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        });
      });

      await page.goto("/");

      await expect(
        page.getByRole("combobox", { name: /start date/i }),
      ).toBeDisabled();
      await expect(
        page.getByRole("combobox", { name: /end date/i }),
      ).toBeDisabled();
      await expect(page.locator("body")).toContainText(/no records found/i);
    });
  });

  test.describe("Bi-directional County Selection between Map and Table", () => {
    test.beforeEach(async ({ page }) => {
      await page.goto("/");
      await page.locator(".table-toggle-btn").click();
      await expect(page.locator("tr.county-row").first()).toBeVisible();
    });

    test("clicking a county on the map visually highlights both map path and table row", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const aikenRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Aiken" });

      await aikenPath.click();

      await expect(aikenPath).toHaveClass(/is-selected/);
      await expect(aikenPath).toHaveAttribute("aria-pressed", "true");
      await expect(aikenRow).toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveAttribute("aria-selected", "true");
    });

    test("clicking a table row visually highlights both the table row and corresponding map path", async ({
      page,
    }) => {
      const aikenRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Aiken" });
      const aikenPath = page.locator("svg path[data-county='Aiken']");

      await aikenRow.click();

      await expect(aikenRow).toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveAttribute("aria-selected", "true");
      await expect(aikenPath).toHaveClass(/is-selected/);
      await expect(aikenPath).toHaveAttribute("aria-pressed", "true");
    });

    test("clicking an already-selected county clears the selection on both map and table", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const aikenRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Aiken" });

      await aikenPath.click();
      await expect(aikenPath).toHaveClass(/is-selected/);

      await aikenPath.click();
      await expect(aikenPath).not.toHaveClass(/is-selected/);
      await expect(aikenRow).not.toHaveClass(/is-selected/);
    });

    test("clicking anywhere outside the map, drawer, or table clears the selection", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const aikenRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Aiken" });

      await aikenPath.click();
      await expect(aikenPath).toHaveClass(/is-selected/);

      await page
        .getByRole("heading", { name: "SC County Probate Clearance Rates" })
        .click();

      await expect(aikenPath).not.toHaveClass(/is-selected/);
      await expect(aikenRow).not.toHaveClass(/is-selected/);
    });

    test("supports selecting and deselecting via keyboard navigation (Enter and Space keys)", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const aikenRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Aiken" });

      await aikenPath.focus();
      await page.keyboard.press("Enter");

      await expect(aikenPath).toHaveClass(/is-selected/);
      await expect(aikenRow).toHaveClass(/is-selected/);

      await aikenRow.focus();
      await page.keyboard.press("Space");

      await expect(aikenPath).not.toHaveClass(/is-selected/);
      await expect(aikenRow).not.toHaveClass(/is-selected/);
    });

    test("selecting a date range clears active county selection on map and table", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const aikenRow = page
        .locator("tr.county-row")
        .filter({ hasText: "Aiken" });

      await aikenPath.click();
      await expect(aikenPath).toHaveClass(/is-selected/);

      const startDateSelect = page.getByRole("combobox", {
        name: /start date/i,
      });
      await startDateSelect.selectOption({ label: "July 2023" });

      await expect(aikenPath).not.toHaveClass(/is-selected/);
      await expect(aikenRow).not.toHaveClass(/is-selected/);
    });
  });

  test.describe("Accessibility (A11y) Keyboard Navigation and Axe Scans", () => {
    test.beforeEach(async ({ page }) => {
      await page.goto("/");
    });

    test("[A11y] pressing Tab from the last map path moves focus to the table toggle button", async ({
      page,
    }) => {
      const mapPaths = page.locator("svg path.county-path");
      const pathCount = await mapPaths.count();
      const lastMapPath = mapPaths.nth(pathCount - 1);
      const toggleBtn = page.locator(".table-toggle-btn");

      await lastMapPath.focus();
      await expect(lastMapPath).toBeFocused();

      await page.keyboard.press("Tab");
      await expect(toggleBtn).toBeFocused();
    });

    test("[A11y] pressing Escape on a focused county path dismisses tooltip without moving focus", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const tooltip = page.locator(".map-tooltip, [role='tooltip']");

      await aikenPath.focus();
      await expect(tooltip).toBeVisible();

      await page.keyboard.press("Escape");
      await expect(tooltip).not.toBeVisible();
      await expect(aikenPath).toBeFocused();
    });

    test("[A11y] passes axe-core scan on default view, drawer open, table expanded, and empty data", async ({
      page,
    }) => {
      // 1. Default view
      const defaultResults = await new AxeBuilder({ page }).analyze();
      expect(defaultResults.violations).toEqual([]);

      // 2. County selected with drawer open
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      await aikenPath.focus();
      await page.keyboard.press("Enter");
      await expect(page.locator(".trendline-drawer")).toBeVisible();
      const drawerResults = await new AxeBuilder({ page }).analyze();
      expect(drawerResults.violations).toEqual([]);

      // 3. Table expanded
      await page.locator(".table-toggle-btn").click();
      await expect(page.locator("#countyTableWrapper")).toBeVisible();
      const tableResults = await new AxeBuilder({ page }).analyze();
      expect(tableResults.violations).toEqual([]);

      // 4. Empty data
      await page.route("**/data/caseloads_sample.json", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        });
      });
      await page.goto("/");
      await expect(page.locator("body")).toContainText(/no records found/i);
      const emptyResults = await new AxeBuilder({ page }).analyze();
      expect(emptyResults.violations).toEqual([]);
    });
  });

  test.describe("Interactive Map Tooltip (Issue #19)", () => {
    test.beforeEach(async ({ page }) => {
      await page.goto("/");
    });

    test("displays dynamic tooltip on hover and hides on mouseout", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const tooltip = page.locator(".map-tooltip, [role='tooltip']");

      await aikenPath.hover();
      await expect(tooltip).toBeVisible();
      await expect(tooltip).toContainText("Aiken");
      await expect(tooltip).toContainText("97%");

      await page.locator("h1").hover();
      await expect(tooltip).not.toBeVisible();
    });

    test("[A11y] displays tooltip on keyboard focus and hides on blur", async ({
      page,
    }) => {
      const aikenPath = page.locator("svg path[data-county='Aiken']");
      const tooltip = page.locator(".map-tooltip, [role='tooltip']");

      await aikenPath.focus();
      await expect(tooltip).toBeVisible();
      await expect(tooltip).toContainText("Aiken");

      await aikenPath.blur();
      await expect(tooltip).not.toBeVisible();
    });
  });

  test("select and option colors match the active light and dark color scheme", async ({
    page,
  }) => {
    await page.goto("/");
    const startSelect = page.getByRole("combobox", { name: /start date/i });
    const firstOption = startSelect.locator("option").first();
    await expect(startSelect).toBeVisible();

    await page.emulateMedia({ colorScheme: "light" });
    await startSelect.click();
    await expect(startSelect).toHaveCSS(
      "background-color",
      "rgb(255, 255, 255)",
    );
    await expect(startSelect).toHaveCSS("color", "rgb(17, 24, 39)");
    await expect(firstOption).toHaveCSS(
      "background-color",
      "rgb(255, 255, 255)",
    );
    await expect(firstOption).toHaveCSS("color", "rgb(17, 24, 39)");
    await startSelect.press("Escape");

    await page.emulateMedia({ colorScheme: "dark" });
    await startSelect.click();
    await expect(startSelect).toHaveCSS("background-color", "rgb(31, 41, 55)");
    await expect(startSelect).toHaveCSS("color", "rgb(243, 244, 246)");
    await expect(firstOption).toHaveCSS("background-color", "rgb(31, 41, 55)");
    await expect(firstOption).toHaveCSS("color", "rgb(243, 244, 246)");
    await startSelect.press("Escape");
  });
});
