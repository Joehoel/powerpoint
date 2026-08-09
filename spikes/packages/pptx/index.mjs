// Package "pptx": PresentationML proxies on top of the format-agnostic
// "opc" and "xml" packages. This layer knows slides/shapes/runs; it contains
// zero zip or relationship-resolution code.
// Slide order now follows p:sldIdLst + rels (spec-correct), not filename sort.
import { OpcPackage } from "../opc/index.mjs";
import { parseXml, serializeXml, walk, firstChild, childrenOf, attrsOf, tagOf, el, text } from "../xml/index.mjs";
import { parseColorScheme, resolveColor } from "../dml/index.mjs";

class Run {
  #node; #slide;
  constructor(node, slide) { this.#node = node; this.#slide = slide; }
  get text() {
    const t = firstChild(this.#node, "a:t");
    return t ? text(t) : "";
  }
  setFontColor(hex) {
    let rPr = firstChild(this.#node, "a:rPr");
    if (!rPr) {
      rPr = el("a:rPr", { lang: "en-US" });
      childrenOf(this.#node).unshift(rPr);
    }
    const kids = childrenOf(rPr);
    const idx = kids.findIndex((c) => ["a:solidFill", "a:gradFill", "a:noFill", "a:pattFill", "a:blipFill", "a:grpFill"].includes(tagOf(c)));
    const fill = el("a:solidFill", {}, [el("a:srgbClr", { val: hex })]);
    if (idx >= 0) kids.splice(idx, 1, fill);
    else kids.unshift(fill);
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
    const c = nv && firstChild(nv, "p:cNvPr");
    return c ? attrsOf(c).name : undefined;
  }
  *runs() {
    const body = firstChild(this.#node, "p:txBody");
    if (body) for (const r of walk(childrenOf(body), "a:r")) yield new Run(r, this.#slide);
  }
  imageBlob() {
    const blipFill = firstChild(this.#node, "p:blipFill");
    const blip = blipFill && firstChild(blipFill, "a:blip");
    const rId = blip && attrsOf(blip)["r:embed"];
    if (!rId) return null;
    const target = this.#slide.pkg.resolve(this.#slide.partName, rId);
    return target ? this.#slide.pkg.read(target) : null;
  }
}

class Slide {
  pkg; partName; #tree; #dirty = false;
  constructor(pkg, partName) { this.pkg = pkg; this.partName = partName; }
  #root() {
    this.#tree ??= parseXml(this.pkg.read(this.partName));
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
    else kids.unshift(bg);
    this.markDirty();
  }
  serializeIfDirty() {
    if (this.#dirty) this.pkg.write(this.partName, serializeXml(this.#tree));
  }

  /**
   * Theme color resolution context for this slide (spike 7).
   * PresentationML-specific: walks slide -> layout -> master -> theme through
   * OPC rels, applies p:clrMap (+ any a:overrideClrMapping on slide/layout),
   * then delegates the actual color math to the format-agnostic dml package.
   */
  colorContext() {
    const relOf = (part, suffix) =>
      this.pkg.relationshipsOf(part).find((r) => r.type.endsWith(suffix))?.target;
    const layout = relOf(this.partName, "/slideLayout");
    const master = layout && relOf(layout, "/slideMaster");
    const themePart = master && relOf(master, "/theme");
    if (!themePart) throw new Error("could not walk slide->layout->master->theme chain");

    const scheme = parseColorScheme(parseXml(this.pkg.read(themePart)));
    let clrMap = { ...attrsOf([...walk(parseXml(this.pkg.read(master)), "p:clrMap")][0]) };
    for (const part of [layout, this.partName]) {
      const ovr = [...walk(parseXml(this.pkg.read(part)), "a:overrideClrMapping")][0];
      if (ovr) clrMap = { ...attrsOf(ovr) };
    }
    const lookup = (name) => scheme[clrMap[name] ?? name];
    return {
      scheme,
      clrMap,
      themePart,
      /** Resolve an a:srgbClr/a:sysClr/a:schemeClr node to {hex, alpha}. */
      resolve: (colorNode) => resolveColor(colorNode, lookup),
    };
  }
}

export class Presentation {
  #pkg; #slides;
  static open(bytes) { return new Presentation(OpcPackage.open(bytes)); }
  constructor(pkg) { this.#pkg = pkg; }
  get package() { return this.#pkg; } // escape hatch, python-pptx's `.part.package` done right

  get slides() {
    if (!this.#slides) {
      // Spec-correct ordering: presentation.xml's p:sldIdLst gives r:id order,
      // the presentation part's rels map r:id -> slide part.
      const presPart = this.#pkg.mainPart();
      const presXml = parseXml(this.#pkg.read(presPart));
      this.#slides = [...walk(presXml, "p:sldId")].map((sldId) => {
        const rId = attrsOf(sldId)["r:id"];
        const target = this.#pkg.resolve(presPart, rId);
        return new Slide(this.#pkg, target);
      });
    }
    return this.#slides;
  }

  save() {
    for (const s of this.#slides ?? []) s.serializeIfDirty();
    return this.#pkg.save();
  }
}
