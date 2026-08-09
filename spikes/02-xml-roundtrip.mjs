// Spike 2: XML round-trip fidelity — the riskiest assumption in the plan.
// Question: can a general-purpose JS XML parser re-serialize PresentationML
// without corrupting it? Measured per parser:
//  - byte-identical round-trip? (expected: no)
//  - namespace declarations preserved?
//  - whitespace-only text nodes preserved? (a:t with trailing spaces matters!)
//  - parse speed on a real slide part
import { readFile } from "node:fs/promises";
import { readZip } from "./packages/opc/index.mjs";
import * as txml from "txml";
import { XMLParser, XMLBuilder } from "fast-xml-parser";

const fixture = process.argv[2] ?? "../tests/fixtures/hagar-presentatie.pptx";
const parts = readZip(new Uint8Array(await readFile(fixture)));
const td = new TextDecoder();
const slideXml = td.decode(parts.get("ppt/slides/slide1.xml").data);
console.log(`slide1.xml: ${slideXml.length} chars\n`);

function report(name, roundTripped, parseMs) {
  const identical = roundTripped === slideXml;
  // Strip the XML declaration for structural comparison; normalize quote style.
  const norm = (s) => s.replace(/^<\?xml[^?]*\?>\s*/, "").replace(/'/g, '"');
  const structurallyEqual = norm(roundTripped) === norm(slideXml);
  const keepsNamespaces = roundTripped.includes("xmlns:a=") && roundTripped.includes("xmlns:p=");
  console.log(`${name}:`);
  console.log(`  parse time (median of 20): ${parseMs.toFixed(2)}ms`);
  console.log(`  byte-identical: ${identical}`);
  console.log(`  identical modulo xml-decl/quotes: ${structurallyEqual}`);
  console.log(`  namespace declarations kept: ${keepsNamespaces}`);
  if (!identical) {
    for (let i = 0; i < Math.min(roundTripped.length, slideXml.length); i++) {
      if (roundTripped[i] !== slideXml[i]) {
        console.log(`  first divergence at ${i}:`);
        console.log(`    original: …${JSON.stringify(slideXml.slice(Math.max(0, i - 40), i + 40))}…`);
        console.log(`    output:   …${JSON.stringify(roundTripped.slice(Math.max(0, i - 40), i + 40))}…`);
        break;
      }
    }
  }
  console.log();
}

function median(fn, n = 20) {
  const times = [];
  for (let i = 0; i < n; i++) {
    const t0 = performance.now();
    fn();
    times.push(performance.now() - t0);
  }
  return times.sort((a, b) => a - b)[Math.floor(n / 2)];
}

// --- txml ---------------------------------------------------------------
{
  const parseMs = median(() => txml.parse(slideXml));
  const dom = txml.parse(slideXml);
  // txml has no serializer with attribute escaping guarantees; use its stringify.
  const out = txml.stringify(dom);
  report("txml", out, parseMs);
}

// --- fast-xml-parser ------------------------------------------------------
{
  const opts = {
    ignoreAttributes: false,
    attributeNamePrefix: "@_",
    preserveOrder: true,
    trimValues: false,
    parseTagValue: false,
    parseAttributeValue: false,
  };
  const parser = new XMLParser(opts);
  const builder = new XMLBuilder({ ...opts, suppressEmptyNode: true });
  const parseMs = median(() => parser.parse(slideXml));
  const out = builder.build(parser.parse(slideXml));
  report("fast-xml-parser (preserveOrder)", out, parseMs);
}

// --- whitespace-sensitivity check ---------------------------------------
// PresentationML text runs may contain significant leading/trailing spaces.
const wsProbe = `<a:t xml:space="preserve">hello </a:t>`;
const fxp = new XMLParser({ ignoreAttributes: false, preserveOrder: true, trimValues: false });
const fxb = new XMLBuilder({ ignoreAttributes: false, preserveOrder: true, suppressEmptyNode: true });
console.log("whitespace probe original:", JSON.stringify(wsProbe));
console.log("fast-xml-parser keeps trailing space:", fxb.build(fxp.parse(wsProbe)).includes("hello "));
const t = txml.parse(wsProbe);
console.log("txml keeps trailing space:", txml.stringify(t).includes("hello "));
