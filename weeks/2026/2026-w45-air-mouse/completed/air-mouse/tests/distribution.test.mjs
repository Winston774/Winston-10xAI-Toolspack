import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
test('source and license required for macOS build are present',async()=>{
  for(const p of ['AirMouse/main.swift','AirMouse/Info.plist','AirMouse/build.sh','scripts/check.sh','scripts/package.sh','LICENSE','.github/workflows/ci.yml','.github/workflows/release.yml'])assert((await stat(path.join(root,p))).isFile(),p);
  assert.match(await readFile(path.join(root,'LICENSE'),'utf8'),/MIT License/);
});
test('app metadata targets macOS 14 and menu bar application',async()=>{
  const text=await readFile(path.join(root,'AirMouse/Info.plist'),'utf8');
  assert.match(text,/<key>LSMinimumSystemVersion<\/key>\s*<string>14\.0<\/string>/);
  assert.match(text,/<key>LSUIElement<\/key>\s*<true\s*\/>/);
});
test('build targets Apple Silicon and supports explicit signing',async()=>{
  const text=await readFile(path.join(root,'AirMouse/build.sh'),'utf8');
  assert.match(text,/arm64-apple-macosx14\.0/);assert.match(text,/AIRMOUSE_SIGN_IDENTITY/);assert.match(text,/codesign --verify --strict/);
});
