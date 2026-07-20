<script lang="ts">
  import { onDestroy } from 'svelte';

  type PayloadType = 'url' | 'geo' | 'text' | 'wifi';
  type OutputFormat = 'png' | 'jpg' | 'svg' | 'pdf';

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
  let preview_url = '';
  let render_token = '';
  let issue = '';
  let pending = false;
  let request_id = 0;
  let preview_timer: ReturnType<typeof setTimeout> | undefined;

  function request_state(): Record<string, unknown> {
    const payload =
      payload_type === 'url'
        ? { url }
        : payload_type === 'geo'
          ? { latitude, longitude }
          : payload_type === 'text'
            ? { text }
            : { security, ssid, password, hidden };
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
        caption: pdf_caption
      },
      visual: {
        foreground,
        background,
        transparent,
        border_type,
        border_width,
        border_caption
      }
    };
  }

  function clear_preview(): void {
    if (preview_url) {
      URL.revokeObjectURL(preview_url);
    }
    preview_url = '';
    render_token = '';
  }

  async function refresh_preview(): Promise<void> {
    const current_id = ++request_id;
    pending = true;
    issue = '';
    const body = new FormData();
    body.set('request', JSON.stringify(request_state()));
    if (logo_file) body.set('logo', logo_file);
    try {
      const response = await fetch('/api/preview', { method: 'POST', body });
      if (current_id !== request_id) return;
      if (!response.ok) {
        const problem = (await response.json()) as { issues?: { message: string }[] };
        clear_preview();
        issue = problem.issues?.[0]?.message ?? 'Could not create a preview.';
        return;
      }
      const image = await response.blob();
      if (current_id !== request_id) return;
      clear_preview();
      preview_url = URL.createObjectURL(image);
      render_token = response.headers.get('X-Render-Token') ?? '';
    } catch {
      if (current_id === request_id) {
        clear_preview();
        issue = 'Could not reach the QR generator.';
      }
    } finally {
      if (current_id === request_id) pending = false;
    }
  }

  function schedule_preview(): void {
    if (preview_timer) clearTimeout(preview_timer);
    preview_timer = setTimeout(() => void refresh_preview(), 300);
  }

  async function download(): Promise<void> {
    if (!render_token) return;
    const body = new FormData();
    body.set('request', JSON.stringify(request_state()));
    body.set('render_token', render_token);
    if (logo_file) body.set('logo', logo_file);
    const response = await fetch('/api/download', { method: 'POST', body });
    if (!response.ok) {
      issue = 'The preview is no longer current. Generate it again before downloading.';
      return;
    }
    const file = await response.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(file);
    link.download = `qrcode-${payload_type}.${output_format}`;
    link.click();
    URL.revokeObjectURL(link.href);
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
    issue = '';
    clear_preview();
    void refresh_preview();
  }

  onDestroy(() => {
    if (preview_timer) clearTimeout(preview_timer);
    clear_preview();
  });

  void refresh_preview();
</script>

<svelte:head>
  <title>{app_name}</title>
</svelte:head>

<main>
  <header>
    <div>
      <h1>{app_name}</h1>
      <p>Create a scanner-safe QR code, then download it.</p>
    </div>
    <button class="secondary" type="button" on:click={reset}>New code</button>
  </header>

  <div class="workspace">
    <section aria-labelledby="content-heading" class="panel">
      <h2 id="content-heading">Content</h2>
      <label>
        QR content type
        <select bind:value={payload_type} on:change={schedule_preview}>
          <option value="url">Website URL</option>
          <option value="geo">Location</option>
          <option value="text">Plain text</option>
          <option value="wifi">WiFi hotspot</option>
        </select>
      </label>

      {#if payload_type === 'url'}
        <label>
          URL
          <input bind:value={url} on:input={schedule_preview} inputmode="url" />
        </label>
      {:else if payload_type === 'geo'}
        <label>
          Latitude
          <input bind:value={latitude} on:input={schedule_preview} placeholder="40.7128" />
        </label>
        <label>
          Longitude
          <input bind:value={longitude} on:input={schedule_preview} placeholder="-74.0060" />
        </label>
      {:else if payload_type === 'text'}
        <label>
          Text
          <textarea bind:value={text} on:input={schedule_preview} rows="5"></textarea>
        </label>
      {:else}
        <label>
          Security
          <select bind:value={security} on:change={schedule_preview}>
            <option value="wpa">WPA/WPA2/WPA3 Personal</option>
            <option value="open">Open</option>
            <option value="wep">WEP</option>
          </select>
        </label>
        <label>
          Network name (SSID)
          <input bind:value={ssid} on:input={schedule_preview} />
        </label>
        <label>
          Password
          <input bind:value={password} on:input={schedule_preview} type="password" />
        </label>
        <label class="checkbox">
          <input bind:checked={hidden} on:change={schedule_preview} type="checkbox" />
          Hidden network
        </label>
      {/if}

      <h2>Options</h2>
      <label>
        Error correction
        <select bind:value={error_correction} on:change={schedule_preview}>
          <option value="L">L — low</option>
          <option value="M">M — medium</option>
          <option value="Q">Q — quartile</option>
          <option value="H">H — high</option>
        </select>
      </label>
      <label>
        Module style
        <select
          bind:value={module_style}
          on:change={() => {
            if (module_style === 'dot' && !['Q', 'H'].includes(error_correction)) {
              error_correction = 'Q';
            }
            schedule_preview();
          }}
        >
          <option value="square">Square</option>
          <option value="dot">Dot</option>
        </select>
      </label>
      <label>
        Download format
        <select
          bind:value={output_format}
          on:change={() => {
            if (['jpg', 'pdf'].includes(output_format)) transparent = false;
            schedule_preview();
          }}
        >
          <option value="png">PNG</option>
          <option value="jpg">JPG</option>
          <option value="svg">SVG</option>
          <option value="pdf">PDF</option>
        </select>
      </label>
      {#if output_format !== 'pdf'}
        <label>
          Digital scale
          <select bind:value={digital_scale} on:change={schedule_preview}>
            <option value="compact">Compact — 8 px/module</option>
            <option value="standard">Standard — 12 px/module</option>
            <option value="large">Large — 24 px/module</option>
          </select>
        </label>
      {:else}
        <label>
          Page size
          <select bind:value={pdf_page_size} on:change={schedule_preview}>
            <option value="a4">A4</option>
            <option value="letter">US Letter</option>
          </select>
        </label>
        <label>
          Orientation
          <select bind:value={pdf_orientation} on:change={schedule_preview}>
            <option value="portrait">Portrait</option>
            <option value="landscape">Landscape</option>
          </select>
        </label>
        <label>
          Margin
          <select bind:value={pdf_margin_mm} on:change={schedule_preview}>
            <option value={12}>12 mm</option>
            <option value={20}>20 mm</option>
            <option value={25}>25 mm</option>
          </select>
        </label>
        <label>
          QR symbol size
          <select bind:value={pdf_symbol_size_mm} on:change={schedule_preview}>
            <option value={50}>50 mm</option>
            <option value={75}>75 mm</option>
            <option value={100}>100 mm</option>
            <option value={125}>125 mm</option>
            <option value={150}>150 mm</option>
          </select>
        </label>
        <label>
          PDF page caption
          <input bind:value={pdf_caption} maxlength="120" on:input={schedule_preview} />
        </label>
      {/if}
      <label>
        Foreground color
        <input bind:value={foreground} on:input={schedule_preview} pattern="^#[0-9A-Fa-f]{6}$" />
      </label>
      <label>
        Background color
        <input bind:value={background} on:input={schedule_preview} pattern="^#[0-9A-Fa-f]{6}$" />
      </label>
      <label class="checkbox">
        <input bind:checked={transparent} on:change={schedule_preview} type="checkbox" />
        Transparent PNG/SVG background
      </label>
      <label>
        Border
        <select bind:value={border_type} on:change={schedule_preview}>
          <option value="quiet">Quiet zone only</option>
          <option value="solid">Solid frame</option>
          <option value="rounded">Rounded frame</option>
          <option value="label">Label frame</option>
          <option value="padding">Transparent padding</option>
        </select>
      </label>
      <label>
        Border width
        <select bind:value={border_width} disabled={border_type === 'quiet'} on:change={schedule_preview}>
          <option value={1}>1 module</option>
          <option value={2}>2 modules</option>
          <option value={4}>4 modules</option>
        </select>
      </label>
      {#if border_type === 'label'}
        <label>
          Border caption
          <input bind:value={border_caption} maxlength="80" on:input={schedule_preview} />
        </label>
      {/if}
      <label>
        Logo (PNG or JPEG)
        <input
          accept="image/png,image/jpeg"
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
      </label>
    </section>

    <section aria-labelledby="preview-heading" class="panel preview-panel">
      <h2 id="preview-heading">Preview</h2>
      {#if pending}
        <p aria-live="polite">Updating preview…</p>
      {:else if issue}
        <p class="issue" aria-live="polite">{issue}</p>
      {:else if preview_url}
        <img alt="Generated QR code preview" src={preview_url} />
      {/if}
      <button disabled={!render_token || pending} type="button" on:click={download}>
        Download {output_format.toUpperCase()}
      </button>
    </section>
  </div>
</main>
