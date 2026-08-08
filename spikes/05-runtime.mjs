// Spike 5: cross-runtime check. Run under both `node` and `bun`.
// Verifies: (a) the core lib (lib/opc.mjs + lib/pptx.mjs) uses zero
// runtime-specific APIs, (b) native CompressionStream("deflate-raw") exists
// as a potential fast path, (c) the full invert flow produces the same bytes.
import { readFile } from "node:fs/promises"; // runner-only; core lib stays web-baseline
import { Presentation } from "./lib/pptx.mjs";

const runtime = typeof Bun !== "undefined" ? `bun ${Bun.version}`
  : typeof Deno !== "undefined" ? `deno ${Deno.version.deno}`
  : `node ${process.version}`;

console.log(`runtime: ${runtime}`);
console.log(`web baseline: Uint8Array=${typeof Uint8Array}, TextDecoder=${typeof TextDecoder}, DataView=${typeof DataView}`);

let deflateRaw = false;
try {
  new CompressionStream("deflate-raw");
  new DecompressionStream("deflate-raw");
  deflateRaw = true;
} catch { /* not supported */ }
console.log(`CompressionStream("deflate-raw") available: ${deflateRaw}`);

const bytes = new Uint8Array(await readFile(new URL("../tests/fixtures/hagar-presentatie.pptx", import.meta.url)));
const pres = Presentation.open(bytes);
for (const slide of pres.slides) {
  slide.setBackground("1A1A2E");
  for (const shape of slide.shapes()) {
    if (shape.hasTextFrame) for (const run of shape.runs()) run.setFontColor("E8E8F0");
  }
}
const out = pres.save();

// Content hash so Node/Bun outputs can be compared for determinism.
const digest = await crypto.subtle.digest("SHA-256", out);
const hex = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
console.log(`invert flow OK, output ${out.length} bytes, sha256 ${hex.slice(0, 16)}…`);
