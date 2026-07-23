import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

async function loadClient() {
  const source = await readFile(new URL("../lib/gemini-client.js", import.meta.url), "utf8");
  const context = { AbortController, clearTimeout, setTimeout };
  context.globalThis = context;
  vm.runInNewContext(source, context);
  return context.GeminiClient;
}

function response(status, payload, headers = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => headers[name] || headers[name.toLowerCase()] || null },
    async text() {
      return JSON.stringify(payload);
    }
  };
}

function plainTextResponse(status, body, headers = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => headers[name] || headers[name.toLowerCase()] || null },
    async text() {
      return String(body || "");
    }
  };
}

function successPayload(text = '{"translation":"你好"}') {
  return {
    modelVersion: "gemini-3.1-flash-lite",
    candidates: [{
      finishReason: "STOP",
      content: { parts: [{ text }] }
    }],
    usageMetadata: {
      promptTokenCount: 20,
      candidatesTokenCount: 4,
      totalTokenCount: 24
    }
  };
}

const schema = {
  type: "object",
  additionalProperties: false,
  properties: { translation: { type: "string" } },
  required: ["translation"]
};

test("uses generateContent v1beta, header auth, store false, and JSON Schema", async () => {
  const client = await loadClient();
  let request;
  const result = await client.requestStructured({
    apiKey: "secret-key",
    model: "models/gemini-3.1-flash-lite",
    systemInstruction: "Translate strictly.",
    input: [{ type: "text", text: "hello" }],
    responseSchema: schema,
    fetchImpl: async (url, options) => {
      request = { url, options };
      return response(200, successPayload());
    }
  });

  assert.equal(
    request.url,
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"
  );
  assert.doesNotMatch(request.url, /secret-key|\?key=/);
  assert.equal(request.options.headers["x-goog-api-key"], "secret-key");
  const body = JSON.parse(request.options.body);
  assert.equal(body.store, false);
  assert.equal(body.contents[0].parts[0].text, "hello");
  assert.equal(body.systemInstruction.parts[0].text, "Translate strictly.");
  assert.equal(body.generationConfig.responseMimeType, "application/json");
  assert.deepEqual(body.generationConfig.responseJsonSchema, schema);
  assert.equal("responseFormat" in body.generationConfig, false);
  assert.equal("thinkingConfig" in body.generationConfig, false);
  assert.equal("temperature" in body.generationConfig, false);
  assert.doesNotMatch(request.options.body, /secret-key/);
  assert.equal(result.data.translation, "你好");
  assert.equal(result.model, "gemini-3.1-flash-lite");
  assert.equal(result.usage.totalTokens, 24);
  assert.equal(result.transport, "generateContent");
  assert.equal(result.compatibilityMode, false);
});

test("places an OCR image before the task prompt in the official request body", async () => {
  const client = await loadClient();
  let requestBody;
  await client.requestStructured({
    apiKey: "key",
    model: "gemini-3.1-flash-lite",
    systemInstruction: "Transcribe faithfully.",
    input: [
      { type: "text", text: "Read the image." },
      { type: "image", data: "AQID", mime_type: "image/png", resolution: "high" }
    ],
    responseSchema: schema,
    fetchImpl: async (_url, options) => {
      requestBody = JSON.parse(options.body);
      return response(200, successPayload('{"translation":"畫面文字"}'));
    }
  });

  assert.deepEqual(requestBody.contents[0].parts[0].inlineData, {
    mimeType: "image/png",
    data: "AQID"
  });
  assert.equal(requestBody.contents[0].parts[1].text, "Read the image.");
  assert.equal(requestBody.systemInstruction.parts[0].text, "Transcribe faithfully.");
});

test("retries one generic 400 with the four-week-old minimal generateContent shape", async () => {
  const client = await loadClient();
  const requests = [];
  const result = await client.requestStructured({
    apiKey: "key",
    model: "gemini-3.1-flash-lite",
    systemInstruction: "Transcribe faithfully.",
    input: [
      { type: "text", text: "Read the image." },
      { type: "image", data: "AQID", mime_type: "image/png" }
    ],
    responseSchema: schema,
    fetchImpl: async (url, options) => {
      requests.push({ url, body: JSON.parse(options.body) });
      if (requests.length === 1) {
        return response(400, {
          error: { status: "INVALID_ARGUMENT", message: "optional field is not accepted" }
        });
      }
      return response(200, successPayload('{"translation":"相容成功"}'));
    }
  });

  assert.equal(requests.length, 2);
  assert.equal(requests[0].url, requests[1].url);
  assert.equal(requests[0].body.store, false);
  assert.deepEqual(requests[0].body.generationConfig.responseJsonSchema, schema);
  assert.equal("store" in requests[1].body, false);
  assert.equal("systemInstruction" in requests[1].body, false);
  assert.equal("responseJsonSchema" in requests[1].body.generationConfig, false);
  assert.equal(requests[1].body.generationConfig.responseMimeType, "application/json");
  assert.equal(requests[1].body.contents[0].parts[0].inlineData.mimeType, "image/png");
  const prompt = requests[1].body.contents[0].parts[1].text;
  assert.match(prompt, /Return only one valid JSON object/);
  assert.match(prompt, /"required":\["translation"\]/);
  assert.match(prompt, /Read the image\./);
  assert.equal(result.data.translation, "相容成功");
  assert.equal(result.compatibilityMode, true);
});

test("classifies invalid and unrestricted API keys returned as HTTP 400 without resending", async () => {
  const client = await loadClient();
  let calls = 0;
  await assert.rejects(
    client.requestStructured({
      apiKey: "bad-key",
      model: "gemini-3.1-flash-lite",
      input: [{ type: "text", text: "hello" }],
      responseSchema: schema,
      fetchImpl: async () => {
        calls += 1;
        return response(400, {
          error: {
            status: "INVALID_ARGUMENT",
            message: "Unrestricted Standard API key is not supported. raw-secret-detail",
            details: [{ reason: "API_KEY_UNRESTRICTED" }]
          }
        });
      }
    }),
    (error) =>
      error.code === "auth_error" &&
      error.httpStatus === 400 &&
      error.upstreamReason === "API_KEY_UNRESTRICTED" &&
      !error.message.includes("raw-secret-detail")
  );
  assert.equal(calls, 1);
});

test("classifies a project precondition without a compatibility resubmission", async () => {
  const client = await loadClient();
  let calls = 0;
  await assert.rejects(
    client.requestStructured({
      apiKey: "key",
      model: "gemini-3.1-flash-lite",
      input: [{ type: "text", text: "hello" }],
      responseSchema: schema,
      fetchImpl: async () => {
        calls += 1;
        return response(400, {
          error: { status: "FAILED_PRECONDITION", message: "raw project detail" }
        });
      }
    }),
    (error) =>
      error.code === "project_not_ready" &&
      error.upstreamStatus === "FAILED_PRECONDITION" &&
      !error.message.includes("raw project detail")
  );
  assert.equal(calls, 1);
});

test("returns a safe model error after one generateContent request", async () => {
  const client = await loadClient();
  let calls = 0;
  await assert.rejects(
    client.requestStructured({
      apiKey: "key",
      model: "gemini-3.1-flash-lite",
      input: [{ type: "text", text: "hello" }],
      responseSchema: schema,
      fetchImpl: async () => {
        calls += 1;
        return response(404, {
          error: { status: "NOT_FOUND", message: "raw model rollout detail" }
        });
      }
    }),
    (error) =>
      error.code === "model_not_available" &&
      error.httpStatus === 404 &&
      error.upstreamStatus === "NOT_FOUND" &&
      !error.message.includes("raw model rollout detail")
  );
  assert.equal(calls, 1);
});

test("a generic invalid request gets only the single compatibility retry", async () => {
  const client = await loadClient();
  let calls = 0;
  await assert.rejects(
    client.requestStructured({
      apiKey: "key",
      model: "gemini-3.1-flash-lite",
      input: [{ type: "text", text: "hello" }],
      responseSchema: schema,
      fetchImpl: async () => {
        calls += 1;
        return response(400, { error: { status: "INVALID_ARGUMENT" } });
      }
    }),
    (error) => error.code === "invalid_request"
  );
  assert.equal(calls, 2);
});

test("retries a transient 503 once on the same generateContent endpoint", async () => {
  const client = await loadClient();
  let calls = 0;
  const sleeps = [];
  const result = await client.requestStructured({
    apiKey: "key",
    model: "gemini-3.1-flash-lite",
    input: [{ type: "text", text: "hello" }],
    responseSchema: schema,
    sleepImpl: async (ms) => sleeps.push(ms),
    fetchImpl: async () => {
      calls += 1;
      return calls === 1 ? response(503, {}) : response(200, successPayload());
    }
  });
  assert.equal(calls, 2);
  assert.equal(sleeps.length, 1);
  assert.equal(result.data.translation, "你好");
});

test("an external abort stops the active request without retrying", async () => {
  const client = await loadClient();
  const controller = new AbortController();
  let calls = 0;
  const request = client.requestStructured({
    apiKey: "key",
    model: "gemini-3.1-flash-lite",
    input: [{ type: "text", text: "hello" }],
    responseSchema: schema,
    signal: controller.signal,
    fetchImpl: async (_url, options) => {
      calls += 1;
      return new Promise((_resolve, reject) => {
        options.signal.addEventListener("abort", () => {
          const error = new Error("aborted");
          error.name = "AbortError";
          reject(error);
        }, { once: true });
      });
    }
  });

  controller.abort();

  await assert.rejects(
    request,
    (error) => error.code === "request_aborted" && error.retryable === false
  );
  assert.equal(calls, 1);
});

test("maps HTTP status before parsing a non-JSON error body", async () => {
  const client = await loadClient();
  let calls = 0;
  const result = await client.requestStructured({
    apiKey: "key",
    model: "gemini-3.1-flash-lite",
    input: [{ type: "text", text: "hello" }],
    responseSchema: schema,
    sleepImpl: async () => undefined,
    fetchImpl: async () => {
      calls += 1;
      return calls === 1
        ? plainTextResponse(503, "upstream unavailable")
        : response(200, successPayload());
    }
  });
  assert.equal(calls, 2);
  assert.equal(result.data.translation, "你好");

  await assert.rejects(
    client.requestStructured({
      apiKey: "bad-key",
      model: "gemini-3.1-flash-lite",
      input: [{ type: "text", text: "hello" }],
      responseSchema: schema,
      fetchImpl: async () => plainTextResponse(403, "not JSON and must not leak")
    }),
    (error) => error.code === "auth_error" && !error.message.includes("must not leak")
  );
});

test("reports prompt blocks and token truncation without retrying", async () => {
  const client = await loadClient();
  await assert.rejects(
    client.requestStructured({
      apiKey: "key",
      model: "gemini-3.1-flash-lite",
      input: [{ type: "text", text: "hello" }],
      responseSchema: schema,
      fetchImpl: async () => response(200, { promptFeedback: { blockReason: "SAFETY" } })
    }),
    (error) => error.code === "content_blocked"
  );

  await assert.rejects(
    client.requestStructured({
      apiKey: "key",
      model: "gemini-3.1-flash-lite",
      input: [{ type: "text", text: "hello" }],
      responseSchema: schema,
      fetchImpl: async () => response(200, {
        candidates: [{ finishReason: "MAX_TOKENS", content: { parts: [] } }]
      })
    }),
    (error) => error.code === "interaction_incomplete"
  );
});

test("rejects malformed model JSON and unsupported request parts", async () => {
  const client = await loadClient();
  await assert.rejects(
    client.requestStructured({
      apiKey: "key",
      model: "gemini-3.1-flash-lite",
      input: [{ type: "text", text: "hello" }],
      responseSchema: schema,
      fetchImpl: async () => response(200, successPayload("not json"))
    }),
    (error) => error.code === "invalid_model_json"
  );

  await assert.rejects(
    client.requestStructured({
      apiKey: "key",
      model: "gemini-3.1-flash-lite",
      input: [{ type: "audio", data: "AQID" }],
      responseSchema: schema,
      fetchImpl: async () => response(200, successPayload())
    }),
    (error) => error.code === "invalid_request"
  );
});
