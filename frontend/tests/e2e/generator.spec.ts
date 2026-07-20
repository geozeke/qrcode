import { expect, test, type Page } from '@playwright/test';

const pixel = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII=',
  'base64',
);

async function mockApi(page: Page): Promise<void> {
  await page.route('**/api/preview', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      headers: { 'X-Render-Token': 'browser-token' },
      body: pixel,
    });
  });
  await page.route('**/api/download', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      headers: { 'Content-Disposition': 'attachment; filename="qrcode-url.png"' },
      body: pixel,
    });
  });
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto('/');
  await expect(page.getByAltText('Generated QR code preview')).toBeVisible();
});

test('generates a URL code and downloads the validated state', async ({ page }) => {
  await page.getByRole('textbox', { name: 'URL' }).fill('https://example.org/docs');
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download PNG' }).click();
  expect((await download).suggestedFilename()).toBe('qrcode-url.png');
});

test('validates each first-release payload workflow', async ({ page }) => {
  const type = page.getByRole('combobox', { name: 'QR content type' });

  await type.selectOption('geo');
  await page.getByRole('textbox', { name: 'Latitude' }).fill('40.7128');
  await page.getByRole('textbox', { name: 'Longitude' }).fill('-74.0060');
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();

  await type.selectOption('text');
  await page.getByRole('textbox', { name: 'Text' }).fill('Accessible plain text');
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();

  await type.selectOption('wifi');
  await page.getByRole('textbox', { name: 'Network name (SSID)' }).fill('Office');
  await page.getByLabel('Password').fill('password123');
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
});

test('keeps theme changes separate from generated colors', async ({ page }) => {
  const foreground = page.getByRole('textbox', { name: 'Foreground color hex value' });
  await expect(foreground).toHaveValue('#000000');
  await page.getByRole('button', { name: 'Switch to dark mode' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(foreground).toHaveValue('#000000');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});

test('offers keyboard access and a single-column mobile layout', async ({ page }, testInfo) => {
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to QR code settings' })).toBeFocused();
  if (testInfo.project.name === 'mobile-chromium') {
    const workspace = page.locator('.workspace');
    await expect(workspace).toHaveCSS('grid-template-columns', /\d+(\.\d+)?px/);
  }
});
