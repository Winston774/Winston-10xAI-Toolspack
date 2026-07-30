import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import {
  ANALYSIS_PROMPT,
  ANALYSIS_SCHEMA,
  validateAnalysis,
} from "./analysis-schema.mjs";

const AGENT_TIMEOUT_MS = 12 * 60 * 1000;
const OUTPUT_LIMIT = 2 * 1024 * 1024;

function requiredEnvironment(source = process.env) {
  const allowed = [
    "APPDATA",
    "CODEX_HOME",
    "COMSPEC",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "SystemRoot",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "USERNAME",
    "WINDIR",
  ];
  return Object.fromEntries(
    allowed
      .filter((key) => typeof source[key] === "string")
      .map((key) => [key, source[key]]),
  );
}

async function fileExists(filePath) {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function resolveLauncher(configuration = {}) {
  const configured = String(configuration.executable || "").trim();
  const candidates = [];

  if (configured && configured !== "codex") {
    candidates.push(configured);
  }
  if (process.env.APPDATA) {
    candidates.push(
      path.join(
        process.env.APPDATA,
        "npm",
        "node_modules",
        "@openai",
        "codex",
        "bin",
        "codex.js",
      ),
    );
  }

  for (const candidate of candidates) {
    if (await fileExists(candidate)) {
      if (candidate.toLowerCase().endsWith(".js")) {
        return {
          command: process.execPath,
          prefix: [candidate],
          display: candidate,
        };
      }
      return { command: candidate, prefix: [], display: candidate };
    }
  }

  return {
    command: configured || "codex",
    prefix: [],
    display: configured || "codex",
  };
}

function runProcess({
  command,
  args,
  cwd,
  input = "",
  timeoutMs = 10_000,
  environment = process.env,
}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      env: requiredEnvironment(environment),
      shell: false,
      windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    let settled = false;

    const timer = setTimeout(() => {
      if (settled) return;
      child.kill();
      const error = new Error("Codex Agent 超過允許的執行時間。");
      error.code = "CODEX_TIMEOUT";
      reject(error);
    }, timeoutMs);

    function append(current, chunk) {
      if (current.length >= OUTPUT_LIMIT) return current;
      return (current + chunk.toString("utf8")).slice(0, OUTPUT_LIMIT);
    }

    child.stdout.on("data", (chunk) => {
      stdout = append(stdout, chunk);
    });
    child.stderr.on("data", (chunk) => {
      stderr = append(stderr, chunk);
    });
    child.on("error", (cause) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      const error = new Error(
        cause.code === "ENOENT"
          ? "找不到 Codex CLI。請確認 Codex 桌面版已安裝並登入。"
          : `無法啟動 Codex Agent：${cause.message}`,
      );
      error.code = "CODEX_UNAVAILABLE";
      error.cause = cause;
      reject(error);
    });
    child.on("close", (code, signal) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ code, signal, stdout, stderr });
    });

    child.stdin.on("error", () => {});
    child.stdin.end(input);
  });
}

function classifyCodexFailure(result) {
  const combined = `${result.stderr}\n${result.stdout}`.toLowerCase();
  const error = new Error(
    result.stderr.trim() ||
      `Codex Agent 以狀態碼 ${result.code ?? "unknown"} 結束。`,
  );
  if (
    combined.includes("login") ||
    combined.includes("not authenticated") ||
    combined.includes("unauthorized")
  ) {
    error.code = "CODEX_AUTH_REQUIRED";
    error.message = "Codex 登入已失效；請先在 Codex 桌面版重新登入。";
  } else if (
    combined.includes("unexpected argument") ||
    combined.includes("unrecognized") ||
    combined.includes("configuration")
  ) {
    error.code = "CODEX_CONFIGURATION";
    error.message = "目前 Codex CLI 不支援 Stylebase 所需的圖片任務參數。";
  } else if (
    combined.includes("rate limit") ||
    combined.includes("quota") ||
    combined.includes("too many requests")
  ) {
    error.code = "CODEX_RATE_LIMIT";
    error.message = "Codex 暫時達到使用限制；請稍後重試這筆工作。";
  } else {
    error.code = "CODEX_FAILED";
  }
  return error;
}

function hasCompletedTurn(stdout) {
  return stdout
    .split(/\r?\n/)
    .filter(Boolean)
    .some((line) => {
      try {
        const event = JSON.parse(line);
        return (
          event.type === "turn.completed" ||
          event.type === "turn_complete" ||
          event.type === "task_complete"
        );
      } catch {
        return false;
      }
    });
}

async function removeJobDirectory(dataDirectory, jobDirectory) {
  const root = path.resolve(dataDirectory);
  const target = path.resolve(jobDirectory);
  if (!target.startsWith(`${root}${path.sep}`)) return;
  await rm(target, { recursive: true, force: true });
}

export async function checkCodexAgent(configuration = {}) {
  const launcher = await resolveLauncher(configuration);
  try {
    const version = await runProcess({
      command: launcher.command,
      args: [...launcher.prefix, "--version"],
      cwd: configuration.workingDirectory || os.tmpdir(),
      timeoutMs: 7_000,
    });
    if (version.code !== 0) throw classifyCodexFailure(version);

    const login = await runProcess({
      command: launcher.command,
      args: [...launcher.prefix, "login", "status"],
      cwd: configuration.workingDirectory || os.tmpdir(),
      timeoutMs: 7_000,
    });
    const loginText = `${login.stdout}\n${login.stderr}`.trim();
    const authenticated =
      login.code === 0 && /logged in|authenticated|chatgpt/i.test(loginText);

    return {
      id: "codex",
      label: "Codex AI Agent",
      ready: authenticated,
      version: version.stdout.trim() || version.stderr.trim(),
      authenticated,
      execution: "ephemeral / read-only / approval never",
      model: configuration.model || "signed-in default",
      message: authenticated
        ? "Codex 已登入，可接收圖片辨識工作。"
        : "Codex CLI 可用，但尚未確認登入狀態。",
    };
  } catch (error) {
    return {
      id: "codex",
      label: "Codex AI Agent",
      ready: false,
      version: "",
      authenticated: false,
      execution: "ephemeral / read-only / approval never",
      model: configuration.model || "signed-in default",
      message:
        error instanceof Error
          ? error.message
          : "無法確認 Codex Agent 狀態。",
    };
  }
}

export async function runCodexAnalysis({
  imagePath,
  mimeType,
  configuration = {},
}) {
  if (!/^image\/(jpeg|png|webp|gif)$/.test(String(mimeType || ""))) {
    const error = new Error("Codex Agent 收到不支援的圖片格式。");
    error.code = "CODEX_CONFIGURATION";
    throw error;
  }
  if (!(await fileExists(imagePath))) {
    const error = new Error("找不到要分析的原始圖片。");
    error.code = "CODEX_CONFIGURATION";
    throw error;
  }

  const dataDirectory =
    configuration.dataDirectory || path.join(os.tmpdir(), "stylebase");
  await mkdir(dataDirectory, { recursive: true });
  const jobDirectory = await mkdtemp(
    path.join(dataDirectory, "codex-agent-job-"),
  );
  const schemaPath = path.join(jobDirectory, "analysis.schema.json");
  const outputPath = path.join(jobDirectory, "analysis.output.json");
  const launcher = await resolveLauncher(configuration);

  await writeFile(
    schemaPath,
    `${JSON.stringify(ANALYSIS_SCHEMA, null, 2)}\n`,
    "utf8",
  );

  const args = [
    ...launcher.prefix,
    "-a",
    "never",
    "exec",
    "--sandbox",
    "read-only",
    "--ephemeral",
    "--ignore-user-config",
    "--skip-git-repo-check",
    "--json",
    "--color",
    "never",
    "--image",
    imagePath,
    "--output-schema",
    schemaPath,
    "--output-last-message",
    outputPath,
    "--cd",
    jobDirectory,
  ];
  if (configuration.model) {
    args.push("--model", configuration.model);
  }
  args.push("-");

  try {
    const result = await runProcess({
      command: launcher.command,
      args,
      cwd: jobDirectory,
      input: ANALYSIS_PROMPT,
      timeoutMs: configuration.timeoutMs || AGENT_TIMEOUT_MS,
    });
    if (result.code !== 0) throw classifyCodexFailure(result);
    if (!hasCompletedTurn(result.stdout)) {
      const error = new Error("Codex Agent 未回報工作完成事件。");
      error.code = "CODEX_FAILED";
      throw error;
    }

    let parsed;
    try {
      parsed = JSON.parse(await readFile(outputPath, "utf8"));
    } catch (cause) {
      const error = new Error("Codex Agent 的分析結果不是有效 JSON。");
      error.code = "CODEX_FAILED";
      error.cause = cause;
      throw error;
    }

    const analysis = validateAnalysis(parsed);
    return {
      analysis,
      model: configuration.model || "signed-in-default",
      raw: {
        jobId: randomUUID(),
        schemaVersion: analysis.schemaVersion,
        completedAt: new Date().toISOString(),
      },
    };
  } finally {
    await removeJobDirectory(dataDirectory, jobDirectory).catch(() => {});
  }
}
