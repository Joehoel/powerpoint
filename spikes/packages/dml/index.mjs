// Package "dml": shared DrawingML color machinery (ECMA-376 Part 1 §20.1.2.3).
// Format-agnostic: pptx, docx and xlsx all reference the same a:clrScheme
// theme part and the same color transforms. Knows nothing about slides or
// clrMap indirection — that's PresentationML and lives in the pptx package.
import { walk, firstChild, childrenOf, attrsOf, tagOf } from "../xml/index.mjs";

/** Parse a:clrScheme from a theme part into {dk1: "RRGGBB", ..., folHlink}. */
export function parseColorScheme(themeTree) {
  const scheme = [...walk(themeTree, "a:clrScheme")][0];
  if (!scheme) throw new Error("theme has no a:clrScheme");
  const out = {};
  for (const slot of childrenOf(scheme)) {
    const name = tagOf(slot).replace("a:", "");
    const srgb = firstChild(slot, "a:srgbClr");
    const sys = firstChild(slot, "a:sysClr");
    // sysClr resolves to what the OS last rendered; lastClr is the spec's answer.
    out[name] = srgb ? attrsOf(srgb).val.toUpperCase() : attrsOf(sys).lastClr?.toUpperCase();
  }
  return out;
}

// --- color math ------------------------------------------------------------

const clamp01 = (x) => Math.min(1, Math.max(0, x));

function hexToRgb(hex) {
  const n = parseInt(hex, 16);
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff].map((v) => v / 255);
}
function rgbToHex([r, g, b]) {
  // floor matches PowerPoint's observed values more often than round,
  // but ±1/channel differences remain (see FINDINGS) — spike-level accuracy.
  return [r, g, b].map((v) => Math.floor(clamp01(v) * 255).toString(16).padStart(2, "0")).join("").toUpperCase();
}
function rgbToHsl([r, g, b]) {
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  const l = (max + min) / 2;
  if (d === 0) return [0, 0, l];
  const s = d / (1 - Math.abs(2 * l - 1));
  let h;
  if (max === r) h = 60 * (((g - b) / d) % 6);
  else if (max === g) h = 60 * ((b - r) / d + 2);
  else h = 60 * ((r - g) / d + 4);
  return [(h + 360) % 360, s, l];
}
function hslToRgb([h, s, l]) {
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  const [r, g, b] =
    h < 60 ? [c, x, 0] : h < 120 ? [x, c, 0] : h < 180 ? [0, c, x]
    : h < 240 ? [0, x, c] : h < 300 ? [x, 0, c] : [c, 0, x];
  return [r + m, g + m, b + m];
}

/** Apply DrawingML color transform children (a:lumMod, a:tint, ...) to an RGB triplet. */
function applyTransforms(rgb, transformNodes) {
  let out = rgb;
  let alpha = 1;
  for (const node of transformNodes) {
    const tag = tagOf(node);
    const val = Number(attrsOf(node).val) / 100000; // ST_Percentage in 1000ths of a percent
    switch (tag) {
      case "a:lumMod": case "a:lumOff": {
        const [h, s, l] = rgbToHsl(out);
        out = hslToRgb([h, s, clamp01(tag === "a:lumMod" ? l * val : l + val)]);
        break;
      }
      case "a:satMod": {
        const [h, s, l] = rgbToHsl(out);
        out = hslToRgb([h, clamp01(s * val), l]);
        break;
      }
      case "a:tint": // toward white: c' = c*val + (1-val)
        out = out.map((c) => c * val + (1 - val));
        break;
      case "a:shade": // toward black
        out = out.map((c) => c * val);
        break;
      case "a:alpha":
        alpha = val;
        break;
      // spike scope: hueMod/comp/inv/gamma etc. not implemented
    }
  }
  return { rgb: out, alpha };
}

/**
 * Resolve a DrawingML color choice node (a:srgbClr | a:sysClr | a:schemeClr)
 * to {hex, alpha}. `schemeLookup(name)` maps a scheme name (already through
 * any format-specific clrMap) to a base hex from the theme.
 */
export function resolveColor(colorNode, schemeLookup) {
  const tag = tagOf(colorNode);
  const a = attrsOf(colorNode);
  let base;
  if (tag === "a:srgbClr") base = a.val.toUpperCase();
  else if (tag === "a:sysClr") base = (a.lastClr ?? "000000").toUpperCase();
  else if (tag === "a:schemeClr") base = schemeLookup(a.val);
  else return null; // prstClr/hslClr/scrgbClr out of spike scope
  if (!base) return null;
  const { rgb, alpha } = applyTransforms(hexToRgb(base), childrenOf(colorNode) ?? []);
  return { hex: rgbToHex(rgb), alpha };
}
