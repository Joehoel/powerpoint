// Spike 3: a ~150-line vertical slice of the proposed library architecture:
//   OPC part store (raw bytes) -> lazy XML parse of only the parts you touch ->
//   proxy objects with getters/setters -> save() re-serializes only dirty parts.
// API surface intentionally mirrors what the pp repo uses from python-pptx.
import { readZip, writeZip } from "./opc.mjs";
import { XMLParser, XMLBuilder } from "fast-xml-parser";

const XML_OPTS = {
  ignoreAttributes: false,
  attributeNamePrefix: "",
  attributesGroupName: false,
  preserveOrder: true,
  trimValues: false,
  parseTagValue: false,
  parseAttributeValue: false,
};
const parser = new XMLParser(XML_OPTS);
const builder = new XMLBuilder({ ...XML_OPTS, suppressEmptyNode: true });
const td = new TextDecoder();
const te = new TextEncoder();

// --- helpers over fast-xml-parser's preserveOrder tree --------------------
// Node shape: { "tag:name": [children], ":@": {attr: value} }
const tagOf = (node) => Object.keys(node).find((k) => k !== ":@");
const childrenOf = (node) => node[tagOf(node)];
const attrsOf = (node) => (node[":@"] ??= {});

function* walk(nodes, tag) {
  for (const node of nodes ?? []) {
    const t = tagOf(node);
    if (t === tag) yield node;
    if (Array.isArray(node[t])) yield* walk(node[t], tag);
  }
}
const firstChild = (node, tag) =>
  (childrenOf(node) ?? []).find((c) => tagOf(c) === tag);

const el = (tag, attrs = {}, children = []) => ({ [tag]: children, ":@": attrs });

// --- proxies ---------------------------------------------------------------
class Run {
  #node; #slide;
  constructor(node, slide) { this.#node = node; this.#slide = slide; }
  get text() {
    const t = firstChild(this.#node, "a:t");
    return t ? (childrenOf(t)[0]?.["#text"] ?? "") : "";
  }
  /** python-pptx: run.font.color.rgb = RGBColor(...) */
  setFontColor(hex) {
    let rPr = firstChild(this.#node, "a:rPr");
    if (!rPr) {
      rPr = el("a:rPr", { lang: "en-US" });
      childrenOf(this.#node).unshift(rPr);
    }
    // Replace any existing fill on the run properties.
    const kids = childrenOf(rPr);
    const idx = kids.findIndex((c) => ["a:solidFill", "a:gradFill", "a:noFill", "a:pattFill", "a:blipFill", "a:grpFill"].includes(tagOf(c)));
    const fill = el("a:solidFill", {}, [el("a:srgbClr", { val: hex })]);
    if (idx >= 0) kids.splice(idx, 1, fill);
    else kids.unshift(fill); // fills come first in the CT_TextCharacterProperties sequence
    this.#slide.markDirty();
  }
}

class Shape {
  #node; #slide;
  constructor(node, slide) { this.#node = node; this.#slide = slide; }
  get isPicture() { return tagOf(this.#node) === "p:pic"; }
  get hasTextFrame() { return !!firstChild(this.#node, "p:txBody"); }
  get name() {
    const nv = firstChild(this.#node, this.isPicture ? "p:nvPicPr" : "p:nvSpPr");
    const c = nv && firstChild(nv, this.isPicture ? "p:cNvPr" : "p:cNvPr");
    return c ? attrsOf(c).name : undefined;
  }
  *runs() {
    const body = firstChild(this.#node, "p:txBody");
    if (body) for (const r of walk(childrenOf(body), "a:r")) yield new Run(r, this.#slide);
  }
  /** python-pptx: shape.image.blob — resolve r:embed through the slide's rels. */
  imageBlob() {
    const blipFill = firstChild(this.#node, "p:blipFill");
    const blip = blipFill && firstChild(blipFill, "a:blip");
    const rId = blip && attrsOf(blip)["r:embed"];
    return rId ? this.#slide.resolveRel(rId) : null;
  }
}

class Slide {
  #pres; #partName; #tree; #dirty = false;
  constructor(pres, partName) { this.#pres = pres; this.#partName = partName; }
  get partName() { return this.#partName; }
  #root() {
    // Lazy: XML is parsed on first access, never for untouched slides.
    this.#tree ??= parser.parse(td.decode(this.#pres.parts.get(this.#partName).data));
    return this.#tree;
  }
  markDirty() { this.#dirty = true; }
  *shapes() {
    const sld = [...walk(this.#root(), "p:sld")][0];
    const tree = firstChild(firstChild(sld, "p:cSld"), "p:spTree");
    for (const c of childrenOf(tree)) {
      const t = tagOf(c);
      if (t === "p:sp" || t === "p:pic") yield new Shape(c, this);
    }
  }
  /** python-pptx: slide.background.fill.solid(); fill.fore_color.rgb = ... */
  setBackground(hex) {
    const sld = [...walk(this.#root(), "p:sld")][0];
    const cSld = firstChild(sld, "p:cSld");
    const kids = childrenOf(cSld);
    const bg = el("p:bg", {}, [
      el("p:bgPr", {}, [
        el("a:solidFill", {}, [el("a:srgbClr", { val: hex })]),
        el("a:effectLst"),
      ]),
    ]);
    const idx = kids.findIndex((c) => tagOf(c) === "p:bg");
    if (idx >= 0) kids.splice(idx, 1, bg);
    else kids.unshift(bg); // p:bg must be first child of p:cSld
    this.markDirty();
  }
  resolveRel(rId) {
    const relsName = this.#partName.replace(/^(.*)\/([^/]+)$/, "$1/_rels/$2.rels");
    const rels = parser.parse(td.decode(this.#pres.parts.get(relsName).data));
    for (const rel of walk(rels, "Relationship")) {
      if (attrsOf(rel).Id === rId) {
        const target = attrsOf(rel).Target.replace(/^\.\.\//, "ppt/");
        return this.#pres.parts.get(target)?.data ?? null;
      }
    }
    return null;
  }
  serializeIfDirty() {
    if (!this.#dirty) return;
    const xml = builder.build(this.#tree);
    this.#pres.parts.set(this.#partName, { data: te.encode(xml) });
  }
}

export class Presentation {
  parts; #slides;
  static open(bytes) { return new Presentation(readZip(bytes)); }
  constructor(parts) { this.parts = parts; }
  get slides() {
    // Spike shortcut: sort by number; the real library reads presentation.xml's
    // sldIdLst + rels for true ordering.
    this.#slides ??= [...this.parts.keys()]
      .filter((n) => /^ppt\/slides\/slide\d+\.xml$/.test(n))
      .sort((a, b) => parseInt(a.match(/\d+/)) - parseInt(b.match(/\d+/)))
      .map((n) => new Slide(this, n));
    return this.#slides;
  }
  save() {
    for (const s of this.#slides ?? []) s.serializeIfDirty();
    return writeZip(this.parts);
  }
}
