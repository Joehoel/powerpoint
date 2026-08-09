// Spike 1: hand-rolled OPC container (readZip/writeZip on fflate).
// Success criteria:
//  a) reads a real PowerPoint-authored .pptx
//  b) byte-identical part contents after read
//  c) unzip -> rezip output is accepted by python-pptx (validated separately)
import { readFile, writeFile } from "node:fs/promises";
import { readZip, writeZip } from "./packages/opc/index.mjs";

const fixture = process.argv[2] ?? "../tests/fixtures/hagar-presentatie.pptx";
const bytes = new Uint8Array(await readFile(fixture));

const t0 = performance.now();
const parts = readZip(bytes);
const t1 = performance.now();

console.log(`read ${parts.size} parts from ${fixture} (${(bytes.length / 1024).toFixed(0)} KiB) in ${(t1 - t0).toFixed(1)}ms`);
const names = [...parts.keys()];
console.log("required OPC parts present:",
  ["[Content_Types].xml", "_rels/.rels", "ppt/presentation.xml"].every(n => names.includes(n)));
console.log("slides:", names.filter(n => /^ppt\/slides\/slide\d+\.xml$/.test(n)).length,
  "media:", names.filter(n => n.startsWith("ppt/media/")).length);

const t2 = performance.now();
const out = writeZip(parts);
const t3 = performance.now();
console.log(`rewrote zip in ${(t3 - t2).toFixed(1)}ms (${(out.length / 1024).toFixed(0)} KiB)`);

// Verify our own round-trip: re-read what we wrote, compare every part byte-for-byte.
const reread = readZip(out);
let identical = reread.size === parts.size;
for (const [name, { data }] of parts) {
  const other = reread.get(name)?.data;
  if (!other || other.length !== data.length || !other.every((b, i) => b === data[i])) {
    identical = false;
    console.log("MISMATCH:", name);
  }
}
console.log("all parts byte-identical after rezip:", identical);

await writeFile("out/spike1-rezipped.pptx", out);
console.log("wrote out/spike1-rezipped.pptx (validate with python-pptx)");
