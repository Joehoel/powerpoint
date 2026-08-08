// Spike 4 (JS side): same invert flow through the prototype, median of 10.
// Also isolates where time goes (unzip / mutate / rezip) and what deflate
// level costs, since zip write dominated spike 1.
import { readFile } from "node:fs/promises";
import { deflateSync } from "fflate";
import { Presentation } from "./lib/pptx.mjs";
import { readZip, writeZip } from "./lib/opc.mjs";

const fixture = process.argv[2] ?? "../tests/fixtures/hagar-presentatie.pptx";
const bytes = new Uint8Array(await readFile(fixture));

function invertOnce() {
  const pres = Presentation.open(bytes);
  for (const slide of pres.slides) {
    slide.setBackground("1A1A2E");
    for (const shape of slide.shapes()) {
      if (shape.hasTextFrame) for (const run of shape.runs()) run.setFontColor("E8E8F0");
    }
  }
  return pres.save().length;
}

invertOnce(); // warmup
const times = [];
for (let i = 0; i < 10; i++) {
  const t0 = performance.now();
  invertOnce();
  times.push(performance.now() - t0);
}
times.sort((a, b) => a - b);
console.log(`prototype invert+save median: ${times[5].toFixed(1)}ms (min ${times[0].toFixed(1)}ms)`);

// --- phase breakdown -------------------------------------------------------
let t = performance.now();
const parts = readZip(bytes);
const unzipMs = performance.now() - t;
t = performance.now();
writeZip(parts);
const rezipMs = performance.now() - t;
console.log(`phases: unzip ${unzipMs.toFixed(1)}ms, rezip ${rezipMs.toFixed(1)}ms (rest = parse+mutate)`);

// --- deflate level cost on the biggest part -------------------------------
const biggest = [...parts.values()].sort((a, b) => b.data.length - a.data.length)[0].data;
for (const level of [1, 6, 9]) {
  const t0 = performance.now();
  const out = deflateSync(biggest, { level });
  console.log(`deflate level ${level}: ${(performance.now() - t0).toFixed(1)}ms -> ${(out.length / 1024).toFixed(0)} KiB (input ${(biggest.length / 1024).toFixed(0)} KiB)`);
}
