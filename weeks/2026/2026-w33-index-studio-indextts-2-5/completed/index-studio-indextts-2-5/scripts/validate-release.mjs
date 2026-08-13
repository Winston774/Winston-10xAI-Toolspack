import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const failures = [];
const required = [
  "README.md",
  "NOTICE.md",
  "LICENSE",
  "LICENSE_ZH.txt",
  "DISCLAIMER",
  "pyproject.toml",
  "uv.lock",
  "htmlui_server.py",
  "webui.html",
  "start_htmlui.ps1",
  "start_htmlui.bat",
  "docs/HTML_UI_ZH.md",
  "docs/CAPABILITY_EXPERIMENTS_ZH.md",
  "docs/STUDENT_GUIDE_ZH.md",
  "docs/PRIVACY_AND_VOICE_RIGHTS_ZH.md",
  "docs/VERIFICATION_ZH.md",
];

for (const relative of required) {
  if (!fs.existsSync(path.join(root, relative))) failures.push(`Missing ${relative}`);
}

for (const forbidden of [".venv", "outputs", "resouces", "resources"]) {
  if (fs.existsSync(path.join(root, forbidden))) failures.push(`Forbidden local directory: ${forbidden}`);
}

const checkpointsDirectory = path.join(root, "checkpoints");
if (fs.existsSync(checkpointsDirectory)) {
  const checkpointFiles = fs.readdirSync(checkpointsDirectory, { withFileTypes: true });
  for (const entry of checkpointFiles) {
    if (!entry.isFile() || entry.name !== "pinyin.vocab") {
      failures.push(`Forbidden checkpoint entry: checkpoints/${entry.name}`);
    }
  }
}

const secretPatterns = [
  /AIza[0-9A-Za-z_-]{20,}/,
  /gh[pousr]_[0-9A-Za-z]{20,}/,
  /github_pat_[0-9A-Za-z_]{20,}/,
  /sk-[0-9A-Za-z_-]{20,}/,
  /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,
];
const textExtensions = new Set(["", ".css", ".html", ".js", ".json", ".md", ".mjs", ".ps1", ".py", ".toml", ".txt", ".yaml", ".yml"]);
const ignoredDirectories = new Set([".git", ".venv", "outputs"]);

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    if (ignoredDirectories.has(entry.name)) return [];
    const absolute = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(absolute) : [absolute];
  });
}

const files = walk(root);
for (const file of files) {
  if (!textExtensions.has(path.extname(file).toLowerCase())) continue;
  const content = fs.readFileSync(file, "utf8");
  if (secretPatterns.some((pattern) => pattern.test(content))) {
    failures.push(`Possible secret in ${path.relative(root, file)}`);
  }
}

const markdownLink = /\[[^\]]*\]\(([^)]+)\)/g;
for (const file of files.filter((candidate) => candidate.endsWith(".md"))) {
  const content = fs.readFileSync(file, "utf8");
  for (const match of content.matchAll(markdownLink)) {
    const href = match[1].trim().split("#", 1)[0];
    if (!href || href.startsWith("http://") || href.startsWith("https://") || href.startsWith("mailto:")) continue;
    const resolved = path.resolve(path.dirname(file), decodeURIComponent(href));
    if (!resolved.startsWith(root) || !fs.existsSync(resolved)) {
      failures.push(`Broken link in ${path.relative(root, file)}: ${match[1]}`);
    }
  }
}

if (failures.length) {
  console.error(failures.map((failure) => `- ${failure}`).join("\n"));
  process.exit(1);
}

console.log(`Release validation passed (${files.length} files inspected).`);
