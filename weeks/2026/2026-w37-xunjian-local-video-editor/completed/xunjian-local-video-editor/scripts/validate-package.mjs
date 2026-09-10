import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const failures = [];
const releaseMode = process.argv.includes('--release');
const runtimeDirectories = new Set([
  '.venv',
  '.local-editor',
  '.editor-test-data',
  'artifacts',
  'output',
  'outputs',
  'projects',
]);
const requiredFiles = [
  'README.md',
  'UPSTREAM-README.md',
  'LICENSE',
  'THIRD_PARTY_NOTICES.md',
  'pyproject.toml',
  'start-local-editor.ps1',
  'local_editor/__main__.py',
  'local_editor/mcp.py',
  'docs/local-editor-mcp.md',
  'examples/local-editor.codex.toml',
  'examples/local-editor.mcp.json',
];

for (const relativePath of requiredFiles) {
  if (!existsSync(join(root, relativePath))) {
    failures.push(`Missing required source file: ${relativePath}`);
  }
}

const pyproject = readFileSync(join(root, 'pyproject.toml'), 'utf8');
if (!/^version = "0\.2\.0"$/m.test(pyproject)) {
  failures.push('pyproject.toml must declare version 0.2.0.');
}

if (releaseMode) {
  for (const forbiddenPath of ['.env', '.venv', '.local-editor', '.editor-test-data', 'artifacts', 'output']) {
    if (existsSync(join(root, forbiddenPath))) {
      failures.push(`Release package must not contain ${forbiddenPath}.`);
    }
  }
  for (const scaffoldDirectory of ['projects', 'outputs']) {
    const scaffoldPath = join(root, scaffoldDirectory);
    if (!existsSync(scaffoldPath)) continue;
    const unexpectedEntries = readdirSync(scaffoldPath).filter((name) => name !== '.gitkeep');
    if (unexpectedEntries.length > 0) {
      failures.push(`Release scaffold ${scaffoldDirectory} may only contain .gitkeep: ${unexpectedEntries.join(', ')}`);
    }
  }
}

const binaryExtensions = new Set(['.mp4', '.mov', '.mkv', '.avi', '.wav', '.mp3', '.sqlite', '.db']);
const binaryFiles = [];
function visit(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.name === '.git' || entry.name === 'node_modules' || entry.name === '__pycache__') continue;
    const absolutePath = join(directory, entry.name);
    if (entry.isDirectory()) {
      if (!releaseMode && runtimeDirectories.has(entry.name)) continue;
      visit(absolutePath);
      continue;
    }
    if (entry.isFile() && binaryExtensions.has(extname(entry.name).toLowerCase())) {
      binaryFiles.push(absolutePath.slice(root.length + 1));
    }
  }
}
visit(root);
if (binaryFiles.length > 0) {
  failures.push(`Release package contains media or database files: ${binaryFiles.join(', ')}`);
}

const packageJson = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
if (packageJson.version !== '0.2.0') {
  failures.push('package.json must declare version 0.2.0.');
}

const expectedToolMarker = 'TOOLS = [';
if (!readFileSync(join(root, 'local_editor', 'mcp.py'), 'utf8').includes(expectedToolMarker)) {
  failures.push('MCP tool registry marker is missing.');
}

if (failures.length > 0) {
  console.error('迅剪 release wrapper validation failed:');
  for (const failure of failures) console.error(`- ${failure}`);
  process.exitCode = 1;
} else {
  const sourceFiles = [];
  function countFiles(directory) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === '.git' || entry.name === 'node_modules' || entry.name === '__pycache__') continue;
    const absolutePath = join(directory, entry.name);
      if (entry.isDirectory()) {
        if (!releaseMode && runtimeDirectories.has(entry.name)) continue;
        countFiles(absolutePath);
      }
      if (entry.isFile()) sourceFiles.push(absolutePath);
    }
  }
  countFiles(root);
  const mode = releaseMode ? 'release' : 'student-runtime';
  console.log(`迅剪 ${mode} validation passed (${sourceFiles.length} files checked).`);
}
