"use strict";

(() => {
  const MIN_SELECTION_CSS_PX = 16;
  const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
  const MAX_REQUEST_BYTES = 20 * 1024 * 1024;
  const ALLOWED_IMAGE_TYPES = new Set(["image/png", "image/jpeg"]);

  function normalizeSelection(startX, startY, endX, endY) {
    const x1 = Number(startX);
    const y1 = Number(startY);
    const x2 = Number(endX);
    const y2 = Number(endY);
    if (![x1, y1, x2, y2].every(Number.isFinite)) {
      return null;
    }
    return {
      left: Math.min(x1, x2),
      top: Math.min(y1, y2),
      right: Math.max(x1, x2),
      bottom: Math.max(y1, y2),
      width: Math.abs(x2 - x1),
      height: Math.abs(y2 - y1)
    };
  }

  function validateSelection(rect, viewport) {
    const width = Number(viewport?.width);
    const height = Number(viewport?.height);
    const values = [rect?.left, rect?.top, rect?.right, rect?.bottom, rect?.width, rect?.height, width, height].map(Number);
    if (!values.every(Number.isFinite) || width <= 0 || height <= 0) {
      return { ok: false, code: "invalid_selection", message: "框選座標不正確，請重新框選。" };
    }

    const normalized = normalizeSelection(rect.left, rect.top, rect.right, rect.bottom);
    if (!normalized) {
      return { ok: false, code: "invalid_selection", message: "框選座標不正確，請重新框選。" };
    }

    normalized.left = clamp(normalized.left, 0, width);
    normalized.top = clamp(normalized.top, 0, height);
    normalized.right = clamp(normalized.right, 0, width);
    normalized.bottom = clamp(normalized.bottom, 0, height);
    normalized.width = normalized.right - normalized.left;
    normalized.height = normalized.bottom - normalized.top;

    if (normalized.width < MIN_SELECTION_CSS_PX || normalized.height < MIN_SELECTION_CSS_PX) {
      return { ok: false, code: "selection_too_small", message: "框選範圍至少需要 16 × 16 像素。" };
    }

    return {
      ok: true,
      rect: normalized,
      viewport: { width, height }
    };
  }

  function computeCropRect(rect, viewport, image) {
    const checked = validateSelection(rect, viewport);
    const imageWidth = Number(image?.width);
    const imageHeight = Number(image?.height);
    if (!checked.ok || !Number.isFinite(imageWidth) || !Number.isFinite(imageHeight) || imageWidth <= 0 || imageHeight <= 0) {
      throw new Error("invalid_crop_geometry");
    }

    const scaleX = imageWidth / checked.viewport.width;
    const scaleY = imageHeight / checked.viewport.height;
    const x1 = clamp(Math.floor(checked.rect.left * scaleX), 0, imageWidth);
    const y1 = clamp(Math.floor(checked.rect.top * scaleY), 0, imageHeight);
    const x2 = clamp(Math.ceil(checked.rect.right * scaleX), 0, imageWidth);
    const y2 = clamp(Math.ceil(checked.rect.bottom * scaleY), 0, imageHeight);

    if (x2 <= x1 || y2 <= y1) {
      throw new Error("empty_crop");
    }

    return {
      x: x1,
      y: y1,
      width: x2 - x1,
      height: y2 - y1,
      scaleX,
      scaleY
    };
  }

  function parseDataUrl(value) {
    const text = String(value || "");
    const match = /^data:([^;,]+);base64,([A-Za-z0-9+/=]+)$/.exec(text);
    if (!match || !ALLOWED_IMAGE_TYPES.has(match[1])) {
      return null;
    }
    return {
      mimeType: match[1],
      base64: match[2],
      byteLength: base64ByteLength(match[2])
    };
  }

  function base64ByteLength(base64) {
    const text = String(base64 || "").replace(/\s/g, "");
    if (!text) {
      return 0;
    }
    const padding = text.endsWith("==") ? 2 : text.endsWith("=") ? 1 : 0;
    return Math.floor((text.length * 3) / 4) - padding;
  }

  function utf8ByteLength(value) {
    return new TextEncoder().encode(String(value || "")).byteLength;
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  globalThis.CaptureUtils = Object.freeze({
    MIN_SELECTION_CSS_PX,
    MAX_IMAGE_BYTES,
    MAX_REQUEST_BYTES,
    ALLOWED_IMAGE_TYPES,
    normalizeSelection,
    validateSelection,
    computeCropRect,
    parseDataUrl,
    base64ByteLength,
    utf8ByteLength
  });
})();
