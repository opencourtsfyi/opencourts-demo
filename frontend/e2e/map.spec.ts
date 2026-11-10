import { test, expect } from '@playwright/test';

test.describe('Map View', () => {
  test('loads the map page', async ({ page }) => {
    await page.goto('/');

    await expect(page).toHaveTitle(/OpenCourts/);
    await expect(
      page.getByRole('heading', { name: 'SC County Probate Clearance Rates' }),
    ).toBeVisible();
    await expect(page.locator('svg.choropleth-svg')).toBeVisible();
  });
});
