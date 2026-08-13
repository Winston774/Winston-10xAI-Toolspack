import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");
const derivativeStatement = "Any modifications made to the original model in this Derivative Work are not endorsed, warranted, or guaranteed by the original right-holder of the original model, and the original right-holder disclaims all liability related to this Derivative Work.";

test("retains upstream license and derivative statement", () => {
  assert.match(read("LICENSE"), /bilibili Model Use License Agreement/);
  assert.ok(read("README.md").includes(derivativeStatement));
  assert.ok(read("NOTICE.md").includes(derivativeStatement));
});

test("keeps the workbench local-first", () => {
  assert.match(read("htmlui_server.py"), /default="127\.0\.0\.1"/);
  assert.match(read("htmlui_server.py"), /permits one GPU job at a time/i);
  assert.match(read(".gitignore"), /\/checkpoints\*\/\*/);
  assert.match(read(".gitignore"), /!\/checkpoints\/pinyin\.vocab/);
  assert.match(read(".gitignore"), /\/outputs\//);
});

test("aligns release and API versions", () => {
  const packageJson = JSON.parse(read("package.json"));
  assert.equal(packageJson.version, "1.0.0");
  assert.match(read("htmlui_server.py"), /version="1\.0\.0"/);
});

test("ships learner and verification documents", () => {
  for (const relative of [
    "docs/STUDENT_GUIDE_ZH.md",
    "docs/PRIVACY_AND_VOICE_RIGHTS_ZH.md",
    "docs/VERIFICATION_ZH.md",
  ]) {
    assert.ok(fs.existsSync(path.join(root, relative)), relative);
  }
});
