import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import axe from 'axe-core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App.svelte';

function previewResponse(): Response {
  return new Response(new Blob(['png'], { type: 'image/png' }), {
    status: 200,
    headers: { 'Content-Type': 'image/png', 'X-Render-Token': 'safe-token' },
  });
}

describe('QR generator interface', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(previewResponse()));
  });

  it('exposes labeled controls and has no automated structural accessibility violations', async () => {
    const { container } = render(App);
    expect(screen.getByRole('textbox', { name: 'URL' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'QR content type' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Switch to dark mode' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Download PNG' })).toBeEnabled());
    const results = await axe.run(container, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results.violations).toEqual([]);
  });

  it('persists dark mode without changing QR colors', async () => {
    render(App);
    const foreground = screen.getByRole('textbox', { name: 'Foreground color hex value' });
    expect(foreground).toHaveValue('#000000');
    await fireEvent.click(screen.getByRole('button', { name: 'Switch to dark mode' }));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(window.localStorage.getItem('qrcode-theme')).toBe('dark');
    expect(foreground).toHaveValue('#000000');
  });

  it('shows field validation and does not render incomplete content', async () => {
    render(App);
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    await fireEvent.change(screen.getByRole('combobox', { name: 'QR content type' }), {
      target: { value: 'text' },
    });
    expect(screen.getByRole('textbox', { name: 'Text' })).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('alert')).toHaveTextContent('Complete the highlighted fields');
    expect(screen.getByRole('button', { name: 'Download PNG' })).toBeDisabled();
    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('aborts stale previews and disables stale downloads immediately', async () => {
    let firstSignal: AbortSignal | undefined;
    const fetchMock = vi
      .fn()
      .mockImplementationOnce((_url: string, init: RequestInit) => {
        firstSignal = init.signal as AbortSignal;
        return new Promise<Response>((_resolve, reject) => {
          firstSignal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError')),
          );
        });
      })
      .mockResolvedValue(previewResponse());
    vi.stubGlobal('fetch', fetchMock);
    render(App);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await fireEvent.input(screen.getByRole('textbox', { name: 'URL' }), {
      target: { value: 'https://example.org' },
    });
    expect(firstSignal?.aborted).toBe(true);
    expect(screen.getByRole('button', { name: 'Download PNG' })).toBeDisabled();
    await waitFor(
      () => expect(screen.getByRole('button', { name: 'Download PNG' })).toBeEnabled(),
      { timeout: 1000 },
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
