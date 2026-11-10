import { test, expect } from '@playwright/test';

test.describe('Map View', () => {
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
});
