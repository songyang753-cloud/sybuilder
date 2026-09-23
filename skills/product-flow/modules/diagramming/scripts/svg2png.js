#!/usr/bin/env node
// Compatibility entry: every export uses the same validated renderer.
const fs = require("fs"), path = require("path"), cp = require("child_process");
const directory = path.resolve(process.argv[2] || ".");
const files = fs.readdirSync(directory).filter(file => file.endsWith(".svg"));
if (!files.length) { console.error("FAIL: no SVG input"); process.exit(1); }
for (const file of files) {
  const source = path.join(directory, file);
  const result = cp.spawnSync("python3", [path.join(__dirname, "render-svg.py"),
    source, source.replace(/\.svg$/, ".png")], {stdio: "inherit", timeout: 180000});
  if (result.error || result.status !== 0) process.exit(result.status || 2);
}
