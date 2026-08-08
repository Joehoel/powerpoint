// Spike 3: run the pp repo's inverter flow through the prototype library:
// dark background + light text on every slide, and prove image blobs resolve.
// Output is validated against python-pptx separately (03-validate.py).
import { readFile, writeFile } from "node:fs/promises";
import { Presentation } from "./lib/pptx.mjs";

const fixture = process.argv[2] ?? "../tests/fixtures/hagar-presentatie.pptx";
const BG = "1A1A2E";
const FG = "E8E8F0";

const bytes = new Uint8Array(await readFile(fixture));
const t0 = performance.now();
const pres = Presentation.open(bytes);

let shapes = 0, runs = 0, pictures = 0;
for (const slide of pres.slides) {
  slide.setBackground(BG);
  for (const shape of slide.shapes()) {
    shapes++;
    if (shape.hasTextFrame) {
      for (const run of shape.runs()) {
        runs++;
        run.setFontColor(FG);
      }
    }
    if (shape.isPicture) {
      pictures++;
      const blob = shape.imageBlob();
      if (!blob) throw new Error(`image blob failed to resolve for ${shape.name}`);
    }
  }
}
const out = pres.save();
const ms = performance.now() - t0;

console.log(`inverted ${pres.slides.length} slides, ${shapes} shapes, ${runs} runs, ${pictures} pictures in ${ms.toFixed(1)}ms`);
await writeFile("out/spike3-inverted.pptx", out);
console.log("wrote out/spike3-inverted.pptx");
