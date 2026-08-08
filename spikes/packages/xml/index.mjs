// Package "xml": fidelity-preserving XML layer, shared by every OOXML format.
// Wraps fast-xml-parser with the exact settings spike 2 proved safe, plus the
// tree helpers for its preserveOrder node shape:
//   { "tag:name": [children], ":@": {attr: value} }
import { XMLParser, XMLBuilder } from "fast-xml-parser";

const XML_OPTS = {
  ignoreAttributes: false,
  attributeNamePrefix: "",
  preserveOrder: true,
  trimValues: false,
  parseTagValue: false,
  parseAttributeValue: false,
};
const parser = new XMLParser(XML_OPTS);
const builder = new XMLBuilder({ ...XML_OPTS, suppressEmptyNode: true });
const td = new TextDecoder();
const te = new TextEncoder();

export const parseXml = (bytes) => parser.parse(typeof bytes === "string" ? bytes : td.decode(bytes));
export const serializeXml = (tree) => te.encode(builder.build(tree));

export const tagOf = (node) => Object.keys(node).find((k) => k !== ":@");
export const childrenOf = (node) => node[tagOf(node)];
export const attrsOf = (node) => (node[":@"] ??= {});
export const el = (tag, attrs = {}, children = []) => ({ [tag]: children, ":@": attrs });
export const text = (node) => childrenOf(node)?.[0]?.["#text"] ?? "";

export function* walk(nodes, tag) {
  for (const node of nodes ?? []) {
    const t = tagOf(node);
    if (t === tag) yield node;
    if (Array.isArray(node[t])) yield* walk(node[t], tag);
  }
}
export const firstChild = (node, tag) =>
  (childrenOf(node) ?? []).find((c) => tagOf(c) === tag);
