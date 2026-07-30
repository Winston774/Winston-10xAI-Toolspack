const HEX_COLOR_PATTERN =
  /^#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$/i;

export function safeHexColor(value) {
  const color = String(value ?? "").trim();
  return HEX_COLOR_PATTERN.test(color) ? color : "#d7d7d2";
}

export function renderSwatchColor(value) {
  const color = safeHexColor(value);
  return `<svg class="swatch-color" viewBox="0 0 100 44" preserveAspectRatio="none" aria-hidden="true" focusable="false"><rect width="100" height="44" fill="${color}"></rect></svg>`;
}
