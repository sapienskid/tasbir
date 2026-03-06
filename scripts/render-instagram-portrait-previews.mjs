#!/usr/bin/env node

import { spawn } from "node:child_process";
import { resolve } from "node:path";

const projectRoot = process.cwd();
const renderScript = resolve(projectRoot, "scripts/render-template-previews.mjs");
const outDir = process.env.OUT_DIR?.trim() || "artifacts/previews/instagram-portrait-only";

const child = spawn(process.execPath, [renderScript], {
  cwd: projectRoot,
  stdio: "inherit",
  env: {
    ...process.env,
    FORMAT_ONLY: "instagram-portrait",
    OUT_DIR: outDir
  }
});

child.on("exit", (code, signal) => {
  if (typeof code === "number") {
    process.exit(code);
  }
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(1);
});
