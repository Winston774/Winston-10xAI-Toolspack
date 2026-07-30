import assert from "node:assert/strict";
import { mkdtemp, mkdir, readdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { after, before, test } from "node:test";

import {
  checkCodexAgent,
  runCodexAnalysis,
} from "../src/codex-agent.mjs";

const FAKE_CODEX_LAUNCHER = String.raw`
const fs = require("node:fs");

const args = process.argv.slice(2);

if (args.length === 1 && args[0] === "--version") {
  process.stdout.write("codex-cli 0.132.0\n");
  process.exit(0);
}

if (args[0] === "login" && args[1] === "status") {
  process.stdout.write("Logged in using ChatGPT\n");
  process.exit(0);
}

const approvalIndex = args.indexOf("-a");
const execIndex = args.indexOf("exec");
if (
  approvalIndex === -1 ||
  args[approvalIndex + 1] !== "never" ||
  execIndex === -1 ||
  approvalIndex > execIndex
) {
  process.stderr.write("Expected '-a never' before 'exec'.\n");
  process.exit(2);
}

function valueAfter(flag) {
  const index = args.indexOf(flag);
  if (index === -1 || !args[index + 1]) {
    process.stderr.write("Missing " + flag + ".\n");
    process.exit(2);
  }
  return args[index + 1];
}

const schemaPath = valueAfter("--output-schema");
const outputPath = valueAfter("--output-last-message");
fs.accessSync(schemaPath, fs.constants.R_OK);

const analysis = {
  schemaVersion: "stylebase-visual-v1",
  language: "zh-Hant",
  summary:
    "  High-contrast editorial interface with a calm modular rhythm.  ",
  detailedDescription:
    "A restrained reference built from generous whitespace, an assertive display face, compact supporting copy, and a repeatable card grid that can guide a production design system.",
  designDomains: [" web design ", "brand design"],
  artifactTypes: ["landing page", "editorial system"],
  visualDNA: {
    lineage: "Swiss editorial modernism with contemporary product restraint.",
    composition: "Asymmetric hero balanced by a disciplined modular card field.",
    grid: "Twelve-column desktop grid with consistent inset margins.",
    hierarchy: "Oversized headline, quiet metadata, then modular content cards.",
    density: "Low to medium density.",
    whitespace: "Large negative-space zones separate primary story beats.",
    rhythm: "Alternating large and compact modules create a measured cadence."
  },
  typography: {
    category: "Grotesk sans serif",
    scale: "A steep display-to-body scale establishes immediate hierarchy.",
    weight: "Bold display weight paired with regular body copy.",
    tracking: "Tight display tracking and neutral body tracking.",
    case: "Sentence case with sparse uppercase labels.",
    notes: "Use optical sizing and keep body lines short."
  },
  color: {
    mode: "Light",
    temperature: "Neutral-cool",
    saturation: "Low",
    contrast: "Near-black typography against a warm white field.",
    palette: [
      { hex: "#1a2b3c", role: " Ink ", proportion: 0.65 },
      { hex: "#f4f1ea", role: "Canvas", proportion: 0.35 }
    ],
    notes: "Reserve color for structure and a single restrained accent."
  },
  imagery: {
    types: ["product stills", "cropped interface details"],
    treatment: "Crisp, softly lit, and minimally retouched.",
    cropping: "Use decisive close crops inside fixed-ratio frames.",
    notes: "Images function as evidence rather than decoration."
  },
  materials: ["matte paper", "soft glass"],
  components: ["hero", "metadata rail", "reference cards"],
  interactionSignals: ["subtle hover lift", "quiet underline reveal"],
  whyItWorks: [
    "Hierarchy is legible at a glance.",
    "Whitespace makes each reference feel deliberate."
  ],
  implementationRecipe: [
    "Establish spacing and type tokens first.",
    "Build the card grid from reusable primitives."
  ],
  avoid: ["ornamental gradients", "dense control clusters"],
  tags: [" editorial ", "", "minimal"],
  prompts: {
    imageGeneration:
      "Generate a restrained editorial product composition with modular rhythm.",
    uiImplementation:
      "Build a responsive twelve-column editorial interface with reusable cards.",
    designTokens:
      "Define warm-white surfaces, near-black ink, and a steep type scale.",
    negative:
      "Avoid visual clutter, glossy effects, and excessive accent colors."
  },
  confidence: 0.91
};

fs.writeFileSync(outputPath, JSON.stringify(analysis), "utf8");
process.stdout.write(
  JSON.stringify({
    type: "turn.completed",
    usage: { input_tokens: 120, output_tokens: 240 }
  }) + "\n"
);
`;

let temporaryRoot;
let fakeLauncherPath;
let imagePath;

async function removeOwnedTemporaryDirectory(target) {
  const resolvedTempRoot = path.resolve(os.tmpdir()).toLowerCase();
  const resolvedTarget = path.resolve(target);
  const normalizedTarget = resolvedTarget.toLowerCase();

  assert.ok(
    normalizedTarget.startsWith(`${resolvedTempRoot}${path.sep}`),
    `Refusing to remove a directory outside the OS temp root: ${resolvedTarget}`,
  );
  assert.match(
    path.basename(resolvedTarget),
    /^stylebase-codex-agent-test-/,
    `Refusing to remove an unexpected temp directory: ${resolvedTarget}`,
  );

  await rm(resolvedTarget, { recursive: true, force: true });
}

before(async () => {
  temporaryRoot = await mkdtemp(
    path.join(os.tmpdir(), "stylebase-codex-agent-test-"),
  );
  fakeLauncherPath = path.join(temporaryRoot, "fake-codex.js");
  imagePath = path.join(temporaryRoot, "reference.png");

  await writeFile(fakeLauncherPath, FAKE_CODEX_LAUNCHER, "utf8");
  await writeFile(
    imagePath,
    Uint8Array.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  );
});

after(async () => {
  if (temporaryRoot) {
    await removeOwnedTemporaryDirectory(temporaryRoot);
  }
});

test("checkCodexAgent reports a ready authenticated launcher", async () => {
  const status = await checkCodexAgent({
    executable: fakeLauncherPath,
    workingDirectory: temporaryRoot,
    model: "fixture-model",
  });

  assert.equal(status.id, "codex");
  assert.equal(status.ready, true);
  assert.equal(status.authenticated, true);
  assert.equal(status.version, "codex-cli 0.132.0");
  assert.equal(status.execution, "ephemeral / read-only / approval never");
  assert.equal(status.model, "fixture-model");
});

test("runCodexAnalysis returns the normalized schema result", async () => {
  const dataDirectory = path.join(temporaryRoot, "agent-data");
  await mkdir(dataDirectory, { recursive: true });

  const result = await runCodexAnalysis({
    imagePath,
    mimeType: "image/png",
    configuration: {
      executable: fakeLauncherPath,
      dataDirectory,
      model: "fixture-model",
      timeoutMs: 5_000,
    },
  });

  assert.equal(
    result.analysis.summary,
    "High-contrast editorial interface with a calm modular rhythm.",
  );
  assert.deepEqual(result.analysis.designDomains, [
    "web design",
    "brand design",
  ]);
  assert.equal(result.analysis.color.palette[0].hex, "#1A2B3C");
  assert.equal(result.analysis.color.palette[0].role, "Ink");
  assert.deepEqual(result.analysis.tags, ["editorial", "minimal"]);
  assert.equal(result.analysis.confidence, 0.91);
  assert.equal(result.model, "fixture-model");
  assert.match(
    result.raw.jobId,
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
  );
  assert.equal(Number.isNaN(Date.parse(result.raw.completedAt)), false);
  assert.deepEqual(await readdir(dataDirectory), []);
});

test("runCodexAnalysis rejects a non-image input before launching Codex", async () => {
  const textPath = path.join(temporaryRoot, "not-an-image.txt");
  await writeFile(textPath, "not image data", "utf8");

  await assert.rejects(
    runCodexAnalysis({
      imagePath: textPath,
      mimeType: "text/plain",
      configuration: {
        executable: fakeLauncherPath,
        dataDirectory: path.join(temporaryRoot, "unused-data"),
        timeoutMs: 5_000,
      },
    }),
    (error) => {
      assert.equal(error?.code, "CODEX_CONFIGURATION");
      return true;
    },
  );
});
