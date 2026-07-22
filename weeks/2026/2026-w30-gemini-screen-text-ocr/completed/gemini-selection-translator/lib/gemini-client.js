"use strict";

(() => {
  const GENERATE_CONTENT_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models";
  const DEFAULT_TIMEOUT_MS = 25000;
  const MAX_RETRIES = 1;

  async function requestStructured(options) {
    const apiKey = String(options?.apiKey || "").trim();
    const model = normalizeModel(options?.model);
    const input = options?.input;
    const systemInstruction = String(options?.systemInstruction || "").trim();
    const responseSchema = options?.responseSchema;
    const fetchImpl = options?.fetchImpl || globalThis.fetch;
    const sleepImpl = options?.sleepImpl || sleep;
    const timeoutMs = clampNumber(options?.timeoutMs, 1000, 60000, DEFAULT_TIMEOUT_MS);
    const externalSignal = options?.signal;

    if (!apiKey) {
      throw publicError("missing_api_key", "請先設定 Gemini API Key。", false);
    }
    if (!model || !Array.isArray(input) || input.length === 0 || !responseSchema) {
      throw publicError("invalid_request", "Gemini 請求資料不完整。", false);
    }
    if (typeof fetchImpl !== "function") {
      throw publicError("network_unavailable", "目前無法連線到 Gemini。", true);
    }

    const endpoint = `${GENERATE_CONTENT_API_ROOT}/${encodeURIComponent(model)}:generateContent`;
    let compatibilityMode = false;
    let body = buildGenerateContentBody({
      input,
      systemInstruction,
      responseSchema,
      compatibilityMode
    });
    let transientAttempt = 0;
    let lastError;

    while (transientAttempt <= MAX_RETRIES) {
      if (externalSignal?.aborted) {
        throw publicError("request_aborted", "這次 Gemini 請求已由較新的操作取代。", false);
      }
      try {
        const response = await fetchWithTimeout(fetchImpl, endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-goog-api-key": apiKey
          },
          body: JSON.stringify(body)
        }, timeoutMs, externalSignal);

        if (externalSignal?.aborted) {
          throw publicError("request_aborted", "這次 Gemini 請求已由較新的操作取代。", false);
        }

        if (!response.ok) {
          const errorPayload = await readErrorJson(response);
          const error = httpError(response.status, errorPayload, model);
          if (shouldUseCompatibilityBody(response.status, error, compatibilityMode)) {
            compatibilityMode = true;
            body = buildGenerateContentBody({
              input,
              systemInstruction,
              responseSchema,
              compatibilityMode
            });
            continue;
          }
          if (error.retryable && transientAttempt < MAX_RETRIES) {
            await sleepImpl(retryDelayMs(response, transientAttempt));
            transientAttempt += 1;
            continue;
          }
          throw error;
        }

        const payload = await readResponseJson(response);
        return {
          data: parseModelJson(extractGenerateContentText(payload)),
          model: normalizeModel(payload?.modelVersion) || model,
          usage: sanitizeUsage(payload?.usageMetadata),
          transport: "generateContent",
          compatibilityMode
        };
      } catch (error) {
        if (externalSignal?.aborted) {
          throw publicError("request_aborted", "這次 Gemini 請求已由較新的操作取代。", false);
        }
        const mapped = normalizeThrownError(error);
        lastError = mapped;
        if (mapped.retryable && transientAttempt < MAX_RETRIES) {
          await sleepImpl(retryDelayMs(null, transientAttempt));
          transientAttempt += 1;
          continue;
        }
        throw mapped;
      }
    }

    throw lastError || publicError("network_unavailable", "目前無法連線到 Gemini。", true);
  }

  function buildGenerateContentBody({ input, systemInstruction, responseSchema, compatibilityMode = false }) {
    const imageParts = [];
    const textParts = [];

    for (const item of input) {
      if (item?.type === "text" && typeof item.text === "string") {
        textParts.push(item.text);
        continue;
      }
      if (item?.type === "image" && typeof item.data === "string" && typeof item.mime_type === "string") {
        imageParts.push({
          inlineData: {
            mimeType: item.mime_type,
            data: item.data
          }
        });
        continue;
      }
      throw publicError("invalid_request", "Gemini 請求包含不支援的內容格式。", false);
    }

    const parts = [...imageParts];
    if (compatibilityMode) {
      parts.push({
        text: buildCompatibilityPrompt(systemInstruction, responseSchema, textParts)
      });
    } else {
      parts.push(...textParts.map((text) => ({ text })));
    }

    const body = {
      contents: [{ role: "user", parts }],
      generationConfig: {
        responseMimeType: "application/json"
      }
    };

    if (!compatibilityMode) {
      body.store = false;
      body.generationConfig.responseJsonSchema = responseSchema;
      if (systemInstruction) {
        body.systemInstruction = {
          parts: [{ text: systemInstruction }]
        };
      }
    }

    return body;
  }

  function buildCompatibilityPrompt(systemInstruction, responseSchema, textParts) {
    const sections = [];
    if (systemInstruction) {
      sections.push(systemInstruction);
    }
    sections.push(
      "Return only one valid JSON object. Do not use Markdown or code fences.",
      `The JSON object must match this schema exactly and must not contain extra keys: ${JSON.stringify(responseSchema)}`
    );
    if (textParts.length) {
      sections.push("Task:", ...textParts);
    }
    return sections.join("\n");
  }

  function shouldUseCompatibilityBody(status, error, compatibilityMode) {
    return !compatibilityMode &&
      status === 400 &&
      error?.code === "invalid_request" &&
      ["", "INVALID_ARGUMENT"].includes(String(error?.upstreamStatus || ""));
  }

  async function fetchWithTimeout(fetchImpl, url, options, timeoutMs, externalSignal) {
    const controller = new AbortController();
    const abortFromExternal = () => controller.abort();
    if (externalSignal?.aborted) {
      controller.abort();
    } else {
      externalSignal?.addEventListener?.("abort", abortFromExternal, { once: true });
    }
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetchImpl(url, {
        ...options,
        signal: controller.signal
      });
    } finally {
      clearTimeout(timer);
      externalSignal?.removeEventListener?.("abort", abortFromExternal);
    }
  }

  async function readResponseJson(response) {
    let raw;
    try {
      raw = await response.text();
    } catch (error) {
      throw publicError("invalid_api_response", "Gemini 回傳了無法讀取的資料。", false);
    }

    if (!raw) {
      return {};
    }

    try {
      return JSON.parse(raw);
    } catch (error) {
      throw publicError("invalid_api_response", "Gemini 回傳了無法解析的資料。", false);
    }
  }

  async function readErrorJson(response) {
    let raw;
    try {
      raw = await response.text();
    } catch (error) {
      return null;
    }

    if (!raw || raw.length > 65536) {
      return null;
    }

    try {
      const payload = JSON.parse(raw);
      return payload && typeof payload === "object" ? payload : null;
    } catch (error) {
      return null;
    }
  }

  function extractGenerateContentText(payload) {
    const blockReason = String(payload?.promptFeedback?.blockReason || "").trim().toUpperCase();
    if (blockReason) {
      throw publicError("content_blocked", "Gemini 因安全政策未處理這次內容。請縮小框選範圍或改用較單純的內容。", false);
    }

    const candidates = Array.isArray(payload?.candidates) ? payload.candidates : [];
    const candidate = candidates[0];
    const finishReason = String(candidate?.finishReason || "").trim().toUpperCase();
    if (finishReason && !["STOP", "FINISH_REASON_UNSPECIFIED"].includes(finishReason)) {
      const incomplete = finishReason === "MAX_TOKENS";
      throw publicError(
        incomplete ? "interaction_incomplete" : "content_blocked",
        incomplete
          ? "Gemini 的輸出超過長度限制，請縮小框選範圍後再試。"
          : "Gemini 因安全政策未完成這次內容。請縮小框選範圍或改用較單純的內容。",
        false
      );
    }

    const parts = Array.isArray(candidate?.content?.parts) ? candidate.content.parts : [];
    const texts = parts
      .filter((part) => typeof part?.text === "string" && part.text.trim())
      .map((part) => part.text.trim());
    if (!texts.length) {
      throw publicError("empty_api_response", "Gemini 沒有回傳可用的文字。", false);
    }
    return texts.join("\n");
  }

  function parseModelJson(text) {
    const trimmed = String(text || "").trim();
    try {
      return JSON.parse(trimmed);
    } catch (error) {
      throw publicError("invalid_model_json", "Gemini 回傳的格式不正確，請重新處理。", false);
    }
  }

  function httpError(status, payload, model) {
    const upstreamStatus = normalizeUpstreamStatus(payload?.error?.status);
    const upstreamReason = extractUpstreamReason(payload);
    const upstreamMessage = String(payload?.error?.message || "").slice(0, 4096);

    if (isInvalidApiKey(upstreamStatus, upstreamReason, upstreamMessage)) {
      return publicError(
        "auth_error",
        "Gemini API Key 無效、已失效，或舊的未限制 Standard Key 已被 Google 拒絕。請在 Google AI Studio 建立新的 Auth Key 後重新儲存。",
        false,
        status,
        upstreamStatus,
        upstreamReason
      );
    }
    if (isUnsupportedRegion(upstreamMessage)) {
      return publicError(
        "region_not_supported",
        "這把 Gemini API Key 所屬地區目前不支援此服務。請改用受支援地區的 Google AI Studio 專案。",
        false,
        status,
        upstreamStatus,
        upstreamReason
      );
    }
    if (isApiNotEnabled(upstreamReason, upstreamMessage)) {
      return publicError(
        "api_not_enabled",
        "這把 Key 的 Google Cloud 專案尚未啟用 Gemini API。請在 Google AI Studio 建立新的 Gemini API Key 後重新儲存。",
        false,
        status,
        upstreamStatus,
        upstreamReason
      );
    }
    if (upstreamStatus === "FAILED_PRECONDITION") {
      return publicError(
        "project_not_ready",
        "Gemini API 專案目前不符合使用條件。請在 Google AI Studio 檢查所在地區、服務條款與計費狀態。",
        false,
        status,
        upstreamStatus,
        upstreamReason
      );
    }
    if (status === 401 || status === 403) {
      return publicError(
        "auth_error",
        "Gemini API Key 無效、沒有模型權限，或舊的未限制 Standard Key 已被拒絕。請確認權限，或在 Google AI Studio 建立新的 Auth Key。",
        false,
        status,
        upstreamStatus,
        upstreamReason
      );
    }
    if (status === 404 || upstreamStatus === "NOT_FOUND" || isModelUnavailable(upstreamMessage)) {
      return publicError(
        "model_not_available",
        `目前無法使用模型 ${normalizeModel(model) || "Gemini"}。請改用 gemini-3.1-flash-lite，或確認這把 Key 已取得該模型權限。`,
        false,
        status,
        upstreamStatus || "NOT_FOUND",
        upstreamReason
      );
    }
    if (status === 400) {
      return publicError(
        "invalid_request",
        "Gemini 不接受這次請求。擴充功能已嘗試相容格式；請確認模型設定，或在 Google AI Studio 建立新的 Auth Key 後再試。",
        false,
        status,
        upstreamStatus || "INVALID_ARGUMENT",
        upstreamReason
      );
    }
    if (status === 413) {
      return publicError("image_too_large", "框選圖片過大，請縮小範圍後再試。", false, status, upstreamStatus, upstreamReason);
    }
    if (status === 429) {
      return publicError("rate_limited", "Gemini 目前已達速率或配額限制，請稍後再試。", true, status, upstreamStatus, upstreamReason);
    }
    if (status === 503 || status >= 500) {
      return publicError("service_unavailable", "Gemini 服務暫時無法回應，請稍後再試。", true, status, upstreamStatus, upstreamReason);
    }
    return publicError(
      "gemini_api_error",
      `Gemini API 回傳 HTTP ${Number(status) || 0}。`,
      false,
      status,
      upstreamStatus,
      upstreamReason
    );
  }

  function normalizeUpstreamStatus(status) {
    const normalized = String(status || "").trim().toUpperCase();
    return /^[A-Z][A-Z0-9_]{1,63}$/.test(normalized) ? normalized : "";
  }

  function extractUpstreamReason(payload) {
    const details = Array.isArray(payload?.error?.details) ? payload.error.details : [];
    for (const detail of details) {
      const reason = normalizeUpstreamStatus(detail?.reason ?? detail?.metadata?.reason);
      if (reason) {
        return reason;
      }
    }
    return "";
  }

  function isInvalidApiKey(upstreamStatus, upstreamReason, message) {
    return upstreamStatus === "UNAUTHENTICATED" ||
      /API_KEY|UNAUTHENTICATED/.test(upstreamReason) ||
      /api key (?:is )?(?:not supported|not valid|invalid|expired|was deleted|blocked|not allowed)|api_key_invalid|invalid api key|unrestricted[^\n]{0,80}api key|standard[^\n]{0,80}(?:api )?key/i.test(message);
  }

  function isUnsupportedRegion(message) {
    return /user location is not supported|not available in (?:your|this) (?:country|region)/i.test(message);
  }

  function isApiNotEnabled(upstreamReason, message) {
    return upstreamReason === "SERVICE_DISABLED" ||
      /generative language api[^\n]{0,160}(?:has not been used|is disabled)|service_disabled|api[^\n]{0,80}not enabled/i.test(message);
  }

  function isModelUnavailable(message) {
    return /model[^\n]{0,160}(?:not found|not available|not supported|does not exist)|not found for api version/i.test(message);
  }

  function normalizeThrownError(error) {
    if (error?.code) {
      return error;
    }
    if (error?.name === "AbortError") {
      return publicError("timeout", "Gemini 回應逾時，請保留畫面後再試一次。", true);
    }
    return publicError("network_unavailable", "目前無法連線到 Gemini，請檢查網路後再試。", true);
  }

  function retryDelayMs(response, attempt) {
    const retryAfter = response?.headers?.get?.("Retry-After");
    if (retryAfter) {
      const seconds = Number(retryAfter);
      if (Number.isFinite(seconds)) {
        return Math.min(Math.max(seconds * 1000, 250), 2000);
      }
      const dateDelay = Date.parse(retryAfter) - Date.now();
      if (Number.isFinite(dateDelay) && dateDelay > 0) {
        return Math.min(dateDelay, 2000);
      }
    }
    return Math.min(500 * 2 ** attempt + Math.floor(Math.random() * 200), 2000);
  }

  function sanitizeUsage(usage) {
    if (!usage || typeof usage !== "object") {
      return null;
    }
    return {
      inputTokens: finiteInteger(usage.total_input_tokens ?? usage.promptTokenCount),
      outputTokens: finiteInteger(usage.total_output_tokens ?? usage.candidatesTokenCount),
      totalTokens: finiteInteger(usage.total_tokens ?? usage.totalTokenCount)
    };
  }

  function finiteInteger(value) {
    const number = Number(value);
    return Number.isFinite(number) && number >= 0 ? Math.floor(number) : null;
  }

  function normalizeModel(model) {
    return String(model || "").trim().replace(/^models\//, "");
  }

  function clampNumber(value, min, max, fallback) {
    const number = Number(value);
    return Number.isFinite(number) ? Math.min(Math.max(number, min), max) : fallback;
  }

  function publicError(code, message, retryable, httpStatus, upstreamStatus, upstreamReason) {
    const error = new Error(message);
    error.code = code;
    error.retryable = Boolean(retryable);
    if (httpStatus) {
      error.httpStatus = httpStatus;
    }
    if (upstreamStatus) {
      error.upstreamStatus = upstreamStatus;
    }
    if (upstreamReason) {
      error.upstreamReason = upstreamReason;
    }
    return error;
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  globalThis.GeminiClient = Object.freeze({
    GENERATE_CONTENT_API_ROOT,
    requestStructured,
    buildGenerateContentBody,
    buildCompatibilityPrompt,
    extractGenerateContentText,
    parseModelJson
  });
})();
