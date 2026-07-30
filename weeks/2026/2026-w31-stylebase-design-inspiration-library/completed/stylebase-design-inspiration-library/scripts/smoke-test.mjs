import { spawn } from "node:child_process";
import { cp, mkdir, mkdtemp, rm } from "node:fs/promises";
import { createServer } from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const temporaryRoot = await mkdtemp(path.join(os.tmpdir(), "stylebase-smoke-"));

async function reservePort() {
  return new Promise((resolve, reject) => {
    const probe = createServer();
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const address = probe.address();
      const port = typeof address === "object" && address ? address.port : 0;
      probe.close((error) => (error ? reject(error) : resolve(port)));
    });
  });
}

async function waitForRoot(url, attempts = 40) {
  let lastError = null;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1_000) });
      if (response.ok) return response;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw lastError || new Error("Stylebase did not become ready.");
}

let child = null;
let output = "";

try {
  await cp(path.join(root, "public"), path.join(temporaryRoot, "public"), {
    recursive: true,
  });
  await cp(path.join(root, "src"), path.join(temporaryRoot, "src"), {
    recursive: true,
  });
  await cp(
    path.join(root, "server.mjs"),
    path.join(temporaryRoot, "server.mjs"),
  );
  await mkdir(path.join(temporaryRoot, "library", "inbox"), {
    recursive: true,
  });

  const port = await reservePort();
  child = spawn(process.execPath, ["server.mjs"], {
    cwd: temporaryRoot,
    env: { ...process.env, STYLEBASE_PORT: String(port) },
    shell: false,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.stdout.on("data", (chunk) => {
    output += chunk.toString("utf8");
  });
  child.stderr.on("data", (chunk) => {
    output += chunk.toString("utf8");
  });

  const baseUrl = `http://127.0.0.1:${port}`;
  const rootResponse = await waitForRoot(`${baseUrl}/`);
  const bootstrapResponse = await fetch(`${baseUrl}/api/bootstrap`, {
    signal: AbortSignal.timeout(20_000),
  });
  const bootstrap = await bootstrapResponse.json();

  const csp = rootResponse.headers.get("content-security-policy") || "";
  const assetCount = bootstrap.assets?.items?.length;
  const jobCount = bootstrap.jobs?.items?.length;

  if (rootResponse.status !== 200) {
    throw new Error(`Root returned ${rootResponse.status}.`);
  }
  if (!bootstrapResponse.ok) {
    throw new Error(`Bootstrap returned ${bootstrapResponse.status}.`);
  }
  if (bootstrap.version !== "1.0.0") {
    throw new Error(`Unexpected version: ${bootstrap.version}`);
  }
  if (assetCount !== 0 || jobCount !== 0) {
    throw new Error(
      `Cold start was not empty: ${assetCount} assets, ${jobCount} jobs.`,
    );
  }
  if (!csp.includes("default-src 'self'")) {
    throw new Error("Content-Security-Policy is missing.");
  }

  console.log(
    `Smoke test passed: HTTP 200, v${bootstrap.version}, empty database, CSP present.`,
  );
} catch (error) {
  if (output.trim()) console.error(output.trim());
  throw error;
} finally {
  if (child && child.exitCode === null) {
    child.kill("SIGINT");
    await Promise.race([
      new Promise((resolve) => child.once("exit", resolve)),
      new Promise((resolve) => setTimeout(resolve, 2_000)),
    ]);
  }
  await rm(temporaryRoot, { recursive: true, force: true });
}
