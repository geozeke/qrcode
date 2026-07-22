<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import {
    previewErrorMessage,
    roundCoordinate,
    validatePayload,
    type FieldErrors,
    type OutputFormat,
    type PayloadType,
    type Theme,
  } from './forms';

  const app_name = 'QR Code Generator';
  let payload_type: PayloadType = 'url';
  let url = 'https://example.com';
  let latitude = '';
  let longitude = '';
  let text = '';
  let security = 'wpa';
  let ssid = '';
  let password = '';
  let hidden = false;
  let error_correction = 'M';
  let module_style = 'square';
  let output_format: OutputFormat = 'png';
  let digital_scale = 'standard';
  let pdf_page_size = 'a4';
  let pdf_orientation = 'portrait';
  let pdf_margin_mm = 12;
  let pdf_symbol_size_mm = 100;
  let pdf_caption = '';
  let foreground = '#000000';
  let background = '#FFFFFF';
  let transparent = false;
  let border_type = 'quiet';
  let border_width = 2;
  let border_caption = '';
  let logo_file: File | null = null;
  let logo_input: HTMLInputElement;
  let status_element: HTMLDivElement;
  let preview_url = '';
  let render_token = '';
  let validated_request = '';
  let issue = '';
  let field_errors: FieldErrors = {};
  let pending = false;
  let download_pending = false;
  let theme: Theme = 'light';
  let request_id = 0;
  let preview_timer: ReturnType<typeof setTimeout> | undefined;
  let preview_controller: AbortController | undefined;

  function request_state(): Record<string, unknown> {
    const payload =
      payload_type === 'url'
        ? { url }
        : payload_type === 'geo'
          ? { latitude: roundCoordinate(latitude), longitude: roundCoordinate(longitude) }
          : payload_type === 'text'
            ? { text }
            : { security, ssid, password: security === 'open' ? '' : password, hidden };
    return {
      payload_type,
      payload,
      error_correction,
      module_style,
      output_format,
      digital_scale,
      pdf: {
        page_size: pdf_page_size,
        orientation: pdf_orientation,
        margin_mm: pdf_margin_mm,
        symbol_size_mm: pdf_symbol_size_mm,
        caption: pdf_caption,
      },
      visual: {
        foreground,
        background,
        transparent,
        border_type,
        border_width,
        border_caption: border_type === 'label' ? border_caption : '',
      },
    };
  }

  function payload_errors(): FieldErrors {
    return validatePayload({
      payload_type,
      url,
      latitude,
      longitude,
      text,
      security,
      ssid,
      password: security === 'open' ? '' : password,
    });
  }

  function clear_preview(): void {
    if (preview_url) URL.revokeObjectURL(preview_url);
    preview_url = '';
    render_token = '';
    validated_request = '';
  }

  function invalidate_preview(): void {
    request_id += 1;
    preview_controller?.abort();
    preview_controller = undefined;
    pending = false;
    issue = '';
    clear_preview();
  }

  async function response_problem(response: Response): Promise<string> {
    try {
      const problem = (await response.json()) as {
        error?: string;
        issues?: { path: string; message: string }[];
      };
      if (problem.issues?.length) {
        const errors: FieldErrors = {};
        for (const item of problem.issues) {
          const field = item.path.split('.').at(-1) ?? '';
          errors[field] = item.message;
        }
        field_errors = { ...field_errors, ...errors };
        return problem.issues[0].message;
      }
      return previewErrorMessage(response.status, problem.error);
    } catch {
      return previewErrorMessage(response.status);
    }
  }

  async function refresh_preview(): Promise<void> {
    field_errors = payload_errors();
    if (Object.keys(field_errors).length) {
      invalidate_preview();
      issue = 'Complete the highlighted fields to create a preview.';
      return;
    }
    const current_id = ++request_id;
    const request_json = JSON.stringify(request_state());
    preview_controller?.abort();
    const controller = new AbortController();
    preview_controller = controller;
    pending = true;
    issue = '';
    render_token = '';
    validated_request = '';
    const body = new FormData();
    body.set('request', request_json);
    if (logo_file) body.set('logo', logo_file);
    try {
      const response = await fetch('/api/preview', {
        method: 'POST',
        body,
        signal: controller.signal,
      });
      if (current_id !== request_id) return;
      if (!response.ok) {
        clear_preview();
        issue = await response_problem(response);
        return;
      }
      const image = await response.blob();
      if (current_id !== request_id) return;
      clear_preview();
      preview_url = URL.createObjectURL(image);
      render_token = response.headers.get('X-Render-Token') ?? '';
      validated_request = request_json;
      if (!render_token) {
        clear_preview();
        issue = 'The preview response was incomplete. Try again.';
      }
    } catch (error) {
      if (
        current_id === request_id &&
        !(error instanceof DOMException && error.name === 'AbortError')
      ) {
        clear_preview();
        issue = 'Could not reach the QR generator.';
      }
    } finally {
      if (current_id === request_id) {
        pending = false;
        preview_controller = undefined;
      }
    }
  }

  function schedule_preview(): void {
    if (preview_timer) clearTimeout(preview_timer);
    invalidate_preview();
    field_errors = payload_errors();
    if (Object.keys(field_errors).length) {
      issue = 'Complete the highlighted fields to create a preview.';
      return;
    }
    preview_timer = setTimeout(() => void refresh_preview(), 300);
  }

  function round_latitude(): void {
    latitude = roundCoordinate(latitude);
    schedule_preview();
  }

  function round_longitude(): void {
    longitude = roundCoordinate(longitude);
    schedule_preview();
  }

  async function announce_issue(message: string): Promise<void> {
    issue = message;
    await tick();
    status_element?.focus();
  }

  async function download(): Promise<void> {
    if (!render_token || !validated_request || download_pending) return;
    download_pending = true;
    issue = '';
    const body = new FormData();
    body.set('request', validated_request);
    body.set('render_token', render_token);
    if (logo_file) body.set('logo', logo_file);
    try {
      const response = await fetch('/api/download', { method: 'POST', body });
      if (!response.ok) {
        clear_preview();
        await announce_issue(
          response.status === 409
            ? 'The preview is no longer current. Generate it again before downloading.'
            : await response_problem(response),
        );
        return;
      }
      const file = await response.blob();
      const href = URL.createObjectURL(file);
      const link = document.createElement('a');
      link.href = href;
      link.download = `qrcode-${payload_type}.${output_format}`;
      link.click();
      URL.revokeObjectURL(href);
    } catch {
      await announce_issue('Could not download the QR code. Check your connection and try again.');
    } finally {
      download_pending = false;
    }
  }

  function set_theme(next: Theme): void {
    theme = next;
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    window.localStorage.setItem('qrcode-theme', theme);
  }

  function toggle_theme(): void {
    set_theme(theme === 'light' ? 'dark' : 'light');
  }

  function reset(): void {
    payload_type = 'url';
    url = 'https://example.com';
    latitude = '';
    longitude = '';
    text = '';
    security = 'wpa';
    ssid = '';
    password = '';
    hidden = false;
    error_correction = 'M';
    module_style = 'square';
    output_format = 'png';
    digital_scale = 'standard';
    pdf_page_size = 'a4';
    pdf_orientation = 'portrait';
    pdf_margin_mm = 12;
    pdf_symbol_size_mm = 100;
    pdf_caption = '';
    foreground = '#000000';
    background = '#FFFFFF';
    transparent = false;
    border_type = 'quiet';
    border_width = 2;
    border_caption = '';
    logo_file = null;
    if (logo_input) logo_input.value = '';
    field_errors = {};
    invalidate_preview();
    void refresh_preview();
  }

  onMount(() => {
    const saved = window.localStorage.getItem('qrcode-theme');
    const preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    set_theme(saved === 'dark' || saved === 'light' ? saved : preferred);
    void refresh_preview();
  });

  onDestroy(() => {
    if (preview_timer) clearTimeout(preview_timer);
    preview_controller?.abort();
    clear_preview();
  });
</script>

<svelte:head>
  <title>{app_name}</title>
  <meta
    name="description"
    content="Create scanner-safe QR codes for URLs, locations, text, and WiFi networks."
  />
</svelte:head>

<a class="skip-link" href="#generator-form">Skip to QR code settings</a>

<main>
  <header class="site-header">
    <div>
      <p class="eyebrow">Private · stateless · self-hosted</p>
      <h1>{app_name}</h1>
      <p class="lede">Create a scanner-safe code, preview it, and export exactly what you see.</p>
    </div>
    <div class="header-actions">
      <button
        aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        aria-pressed={theme === 'dark'}
        class="secondary compact"
        type="button"
        on:click={toggle_theme}
      >
        <span aria-hidden="true">{theme === 'light' ? '☾' : '☀'}</span>
        {theme === 'light' ? 'Dark' : 'Light'} mode
      </button>
      <button class="secondary compact" type="button" on:click={reset}>New code</button>
    </div>
  </header>

  <div class="workspace">
    <form id="generator-form" class="panel controls-panel" on:submit|preventDefault>
      <fieldset>
        <legend>1. Content</legend>
        <label for="payload-type">QR content type</label>
        <select id="payload-type" bind:value={payload_type} on:change={schedule_preview}>
          <option value="url">Website URL</option>
          <option value="geo">Location</option>
          <option value="text">Plain text</option>
          <option value="wifi">WiFi hotspot</option>
        </select>

        {#if payload_type === 'url'}
          <label for="url">URL</label>
          <input
            id="url"
            aria-describedby={field_errors.url ? 'url-error' : 'url-help'}
            aria-invalid={field_errors.url ? 'true' : undefined}
            autocomplete="url"
            bind:value={url}
            inputmode="url"
            on:input={schedule_preview}
          />
          {#if field_errors.url}<span id="url-error" class="field-error">{field_errors.url}</span
            >{:else}<span id="url-help" class="help">HTTP and HTTPS links only.</span>{/if}
        {:else if payload_type === 'geo'}
          <div class="field-grid">
            <div>
              <label for="latitude">Latitude</label>
              <input
                id="latitude"
                aria-describedby={field_errors.latitude ? 'latitude-error' : undefined}
                aria-invalid={field_errors.latitude ? 'true' : undefined}
                bind:value={latitude}
                inputmode="decimal"
                on:input={schedule_preview}
                on:blur={round_latitude}
                placeholder="40.7128"
              />
              {#if field_errors.latitude}<span id="latitude-error" class="field-error"
                  >{field_errors.latitude}</span
                >{/if}
            </div>
            <div>
              <label for="longitude">Longitude</label>
              <input
                id="longitude"
                aria-describedby={field_errors.longitude ? 'longitude-error' : undefined}
                aria-invalid={field_errors.longitude ? 'true' : undefined}
                bind:value={longitude}
                inputmode="decimal"
                on:input={schedule_preview}
                on:blur={round_longitude}
                placeholder="-74.0060"
              />
              {#if field_errors.longitude}<span id="longitude-error" class="field-error"
                  >{field_errors.longitude}</span
                >{/if}
            </div>
          </div>
        {:else if payload_type === 'text'}
          <label for="plain-text">Text</label>
          <textarea
            id="plain-text"
            aria-describedby="text-count"
            aria-invalid={field_errors.text ? 'true' : undefined}
            bind:value={text}
            maxlength="1000"
            on:input={schedule_preview}
            rows="5"
          ></textarea>
          <span id="text-count" class:field-error={field_errors.text} class="help"
            >{new TextEncoder().encode(text).length} of 1,000 UTF-8 bytes</span
          >
        {:else}
          <label for="security">Security</label>
          <select
            id="security"
            bind:value={security}
            on:change={() => {
              if (security === 'open') password = '';
              schedule_preview();
            }}
          >
            <option value="wpa">WPA/WPA2/WPA3 Personal</option>
            <option value="open">Open</option>
            <option value="wep">WEP</option>
          </select>
          <label for="ssid">Network name (SSID)</label>
          <input
            id="ssid"
            aria-describedby={field_errors.ssid ? 'ssid-error' : undefined}
            aria-invalid={field_errors.ssid ? 'true' : undefined}
            autocomplete="off"
            bind:value={ssid}
            on:input={schedule_preview}
          />
          {#if field_errors.ssid}<span id="ssid-error" class="field-error">{field_errors.ssid}</span
            >{/if}
          {#if security !== 'open'}
            <label for="wifi-password">Password</label>
            <input
              id="wifi-password"
              aria-describedby={field_errors.password ? 'password-error' : undefined}
              aria-invalid={field_errors.password ? 'true' : undefined}
              autocomplete="new-password"
              bind:value={password}
              on:input={schedule_preview}
              type="password"
            />
            {#if field_errors.password}<span id="password-error" class="field-error"
                >{field_errors.password}</span
              >{/if}
          {/if}
          <label class="checkbox" for="hidden-network">
            <input
              id="hidden-network"
              bind:checked={hidden}
              on:change={schedule_preview}
              type="checkbox"
            />
            Hidden network
          </label>
        {/if}
      </fieldset>

      <fieldset>
        <legend>2. Appearance</legend>
        <div class="field-grid">
          <div>
            <label for="error-correction">Error correction</label>
            <select
              id="error-correction"
              bind:value={error_correction}
              on:change={schedule_preview}
            >
              <option value="L">L — low</option><option value="M">M — medium</option><option
                value="Q">Q — quartile</option
              ><option value="H">H — high</option>
            </select>
          </div>
          <div>
            <label for="module-style">Module style</label>
            <select
              id="module-style"
              bind:value={module_style}
              on:change={() => {
                if (module_style === 'dot' && !['Q', 'H'].includes(error_correction))
                  error_correction = 'Q';
                schedule_preview();
              }}
            >
              <option value="square">Square</option><option value="dot">Dot</option>
            </select>
          </div>
        </div>
        <div class="field-grid">
          <div>
            <label for="foreground">Foreground color</label>
            <div class="color-field">
              <input
                id="foreground-picker"
                aria-label="Choose foreground color"
                bind:value={foreground}
                on:input={schedule_preview}
                type="color"
              /><input
                id="foreground"
                aria-label="Foreground color hex value"
                bind:value={foreground}
                on:input={schedule_preview}
                pattern="^#[0-9A-Fa-f]{6}$"
              />
            </div>
          </div>
          <div>
            <label for="background">Background color</label>
            <div class="color-field">
              <input
                id="background-picker"
                aria-label="Choose background color"
                bind:value={background}
                on:input={schedule_preview}
                type="color"
              /><input
                id="background"
                aria-label="Background color hex value"
                bind:value={background}
                on:input={schedule_preview}
                pattern="^#[0-9A-Fa-f]{6}$"
              />
            </div>
          </div>
        </div>
        <label
          class="checkbox"
          class:disabled={['jpg', 'pdf'].includes(output_format)}
          for="transparent"
        >
          <input
            id="transparent"
            bind:checked={transparent}
            disabled={['jpg', 'pdf'].includes(output_format)}
            on:change={schedule_preview}
            type="checkbox"
          />
          Transparent PNG/SVG background
        </label>
        <div class="field-grid">
          <div>
            <label for="border-type">Border</label><select
              id="border-type"
              bind:value={border_type}
              on:change={schedule_preview}
              ><option value="quiet">Quiet zone only</option><option value="solid"
                >Solid frame</option
              ><option value="rounded">Rounded frame</option><option value="label"
                >Label frame</option
              ><option value="padding">Transparent padding</option></select
            >
          </div>
          <div>
            <label for="border-width">Border width</label><select
              id="border-width"
              bind:value={border_width}
              disabled={border_type === 'quiet'}
              on:change={schedule_preview}
              ><option value={1}>1 module</option><option value={2}>2 modules</option><option
                value={4}>4 modules</option
              ></select
            >
          </div>
        </div>
        {#if border_type === 'label'}<label for="border-caption">Border caption</label><input
            id="border-caption"
            bind:value={border_caption}
            maxlength="80"
            on:input={schedule_preview}
          />{/if}
        <label for="logo">Logo <span class="optional">Optional · PNG or JPEG</span></label>
        <input
          id="logo"
          accept="image/png,image/jpeg"
          aria-describedby="logo-help"
          bind:this={logo_input}
          on:change={(event) => {
            logo_file = event.currentTarget.files?.[0] ?? null;
            if (logo_file) {
              module_style = 'square';
              error_correction = 'H';
            }
            schedule_preview();
          }}
          type="file"
        />
        <span id="logo-help" class="help"
          >Up to 5 MiB. Adding a logo selects square modules and H correction.</span
        >
      </fieldset>

      <fieldset>
        <legend>3. Export</legend>
        <label for="output-format">Download format</label>
        <select
          id="output-format"
          bind:value={output_format}
          on:change={() => {
            if (['jpg', 'pdf'].includes(output_format)) transparent = false;
            schedule_preview();
          }}
          ><option value="png">PNG</option><option value="jpg">JPG</option><option value="svg"
            >SVG</option
          ><option value="pdf">PDF</option></select
        >
        {#if output_format !== 'pdf'}
          <label for="digital-scale">Digital scale</label><select
            id="digital-scale"
            bind:value={digital_scale}
            on:change={schedule_preview}
            ><option value="compact">Compact — 8 px/module</option><option value="standard"
              >Standard — 12 px/module</option
            ><option value="large">Large — 24 px/module</option></select
          >
        {:else}
          <div class="field-grid">
            <div>
              <label for="page-size">Page size</label><select
                id="page-size"
                bind:value={pdf_page_size}
                on:change={schedule_preview}
                ><option value="a4">A4</option><option value="letter">US Letter</option></select
              >
            </div>
            <div>
              <label for="orientation">Orientation</label><select
                id="orientation"
                bind:value={pdf_orientation}
                on:change={schedule_preview}
                ><option value="portrait">Portrait</option><option value="landscape"
                  >Landscape</option
                ></select
              >
            </div>
            <div>
              <label for="margin">Margin</label><select
                id="margin"
                bind:value={pdf_margin_mm}
                on:change={schedule_preview}
                ><option value={12}>12 mm</option><option value={20}>20 mm</option><option
                  value={25}>25 mm</option
                ></select
              >
            </div>
            <div>
              <label for="symbol-size">QR symbol size</label><select
                id="symbol-size"
                bind:value={pdf_symbol_size_mm}
                on:change={schedule_preview}
                ><option value={50}>50 mm</option><option value={75}>75 mm</option><option
                  value={100}>100 mm</option
                ><option value={125}>125 mm</option><option value={150}>150 mm</option></select
              >
            </div>
          </div>
          <label for="pdf-caption">PDF page caption <span class="optional">Optional</span></label
          ><input
            id="pdf-caption"
            bind:value={pdf_caption}
            maxlength="120"
            on:input={schedule_preview}
          />
        {/if}
      </fieldset>
    </form>

    <aside aria-labelledby="preview-heading" class="panel preview-panel">
      <div class="preview-header">
        <div>
          <p class="step">Live result</p>
          <h2 id="preview-heading">Preview</h2>
        </div>
        <span class="privacy-badge">Not stored</span>
      </div>
      <div class="preview-stage" aria-busy={pending}>
        {#if pending}<div class="loading" role="status">
            <span class="spinner" aria-hidden="true"></span><span>Updating preview…</span>
          </div>
        {:else if issue}<div bind:this={status_element} class="issue" role="alert" tabindex="-1">
            <strong>Preview unavailable</strong><span>{issue}</span>
          </div>
        {:else if preview_url}<img alt="Generated QR code preview" src={preview_url} />
        {:else}<p class="empty-state">Enter valid content to see your QR code.</p>{/if}
      </div>
      <p class="preview-note">The downloaded file uses this exact validated preview state.</p>
      <button
        aria-describedby="download-help"
        disabled={!render_token || pending || download_pending}
        type="button"
        on:click={download}
        >{download_pending
          ? 'Preparing download…'
          : `Download ${output_format.toUpperCase()}`}</button
      >
      <span id="download-help" class="visually-hidden"
        >Available when the current settings have a valid preview.</span
      >
    </aside>
  </div>
</main>
