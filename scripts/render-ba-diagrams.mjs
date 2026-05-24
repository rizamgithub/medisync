#!/usr/bin/env node
/**
 * Render every Mermaid block inside docs/ba/<feature>/flows.md to an SVG.
 *
 * Output: docs/ba/<feature>/flows/NN-<slug>.svg
 *   - NN is the 1-based index of the block within the file (zero-padded).
 *   - <slug> is derived from the nearest preceding markdown heading
 *     (## or ###) so filenames are semantic and stable across edits.
 *
 * Theme: "neutral" — clean, prints well, readable in GitHub light/dark modes.
 *
 * Usage: pnpm render:diagrams
 */

import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { run as mermaidRun } from "@mermaid-js/mermaid-cli";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..");
const BA_ROOT = join(REPO_ROOT, "docs", "ba");
const MERMAID_THEME = "neutral";
const MERMAID_BG = "white";

async function walk(dir) {
  const out = [];
  const entries = await readdir(dir, { withFileTypes: true });
  for (const e of entries) {
    const p = join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === "_templates" || e.name.startsWith(".")) continue;
      out.push(...(await walk(p)));
    } else if (e.isFile() && e.name === "flows.md") {
      out.push(p);
    }
  }
  return out;
}

function slugify(s) {
  return s
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .slice(0, 60);
}

function extractBlocks(markdown) {
  const lines = markdown.split(/\r?\n/);
  const blocks = [];
  let currentHeading = "diagram";
  let currentHeadingNum = null;
  let inBlock = false;
  let buf = [];

  for (const line of lines) {
    const h = line.match(/^#{2,3}\s+(.+?)\s*$/);
    if (h && !inBlock) {
      const numMatch = h[1].match(/^(\d+)\.\s*/);
      currentHeadingNum = numMatch ? numMatch[1] : null;
      currentHeading = h[1].replace(/^\d+\.\s*/, "");
      continue;
    }
    if (!inBlock && /^```mermaid\s*$/.test(line)) {
      inBlock = true;
      buf = [];
      continue;
    }
    if (inBlock && /^```\s*$/.test(line)) {
      blocks.push({
        heading: currentHeading,
        headingNum: currentHeadingNum,
        source: buf.join("\n"),
      });
      inBlock = false;
      buf = [];
      continue;
    }
    if (inBlock) buf.push(line);
  }
  return blocks;
}

async function renderToSvg(inputMmd, outputSvg, attempts = 3) {
  let lastErr;
  for (let i = 1; i <= attempts; i++) {
    try {
      await mermaidRun(inputMmd, outputSvg, {
        puppeteerConfig: { headless: "new" },
        parseMMDOptions: {
          mermaidConfig: { theme: MERMAID_THEME },
          backgroundColor: MERMAID_BG,
        },
        quiet: true,
      });
      return;
    } catch (err) {
      lastErr = err;
      if (i < attempts) {
        await new Promise((r) => setTimeout(r, 1500));
      }
    }
  }
  throw lastErr;
}

async function renderFlowsFile(flowsPath) {
  const featureDir = dirname(flowsPath);
  const outDir = join(featureDir, "flows");
  const rel = relative(REPO_ROOT, flowsPath);

  const md = await readFile(flowsPath, "utf8");
  const blocks = extractBlocks(md);
  if (blocks.length === 0) {
    console.log(`  ${rel}: no mermaid blocks found, skipping.`);
    return { file: rel, rendered: 0 };
  }

  await mkdir(outDir, { recursive: true });
  // Clean only stale .mmd intermediates; leave .svg files for resumability.
  for (const entry of await readdir(outDir)) {
    if (entry.endsWith(".mmd")) await rm(join(outDir, entry));
  }

  // Prefer the heading's own number (## 0., ## 1., ...) so adding a new
  // diagram in the middle doesn't renumber the others. Fall back to the
  // block's sequential index when a heading has no leading number.
  const maxNum = Math.max(
    blocks.length,
    ...blocks.map((b) => (b.headingNum ? Number(b.headingNum) : 0)),
  );
  const pad = Math.max(2, String(maxNum).length);
  let i = 0;
  for (const b of blocks) {
    i += 1;
    const idxRaw = b.headingNum ?? String(i);
    const idx = idxRaw.padStart(pad, "0");
    const slug = slugify(b.heading) || "diagram";
    const base = `${idx}-${slug}`;
    const mmdPath = join(outDir, `${base}.mmd`);
    const svgPath = join(outDir, `${base}.svg`);
    await writeFile(mmdPath, b.source, "utf8");
    await renderToSvg(mmdPath, svgPath);
    await rm(mmdPath);
    // Brief pause helps Chromium release handles on Windows between launches.
    await new Promise((r) => setTimeout(r, 250));
    console.log(`  ✓ ${relative(REPO_ROOT, svgPath)}`);
  }
  return { file: rel, rendered: blocks.length };
}

async function main() {
  if (!existsSync(BA_ROOT)) {
    console.error(`docs/ba/ not found at ${BA_ROOT}`);
    process.exit(1);
  }
  const flowsFiles = await walk(BA_ROOT);
  if (flowsFiles.length === 0) {
    console.log("No docs/ba/*/flows.md files found.");
    return;
  }

  console.log(`Rendering Mermaid diagrams (theme=${MERMAID_THEME}) from ${flowsFiles.length} file(s):\n`);
  const results = [];
  for (const f of flowsFiles) {
    console.log(relative(REPO_ROOT, f));
    results.push(await renderFlowsFile(f));
    console.log();
  }

  const total = results.reduce((n, r) => n + r.rendered, 0);
  console.log(`Done. ${total} diagram(s) rendered across ${results.length} file(s).`);
}

main().catch((err) => {
  console.error("\nFailed:", err.message);
  process.exit(1);
});
