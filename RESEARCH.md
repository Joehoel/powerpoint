# Research: van python-pptx naar een cross-runtime JavaScript OOXML-library

*Status: research + 7 gevalideerde spikes · augustus 2026*
*Spike-code en ruwe meetresultaten: [`spikes/`](spikes/), conclusies per spike: [`spikes/FINDINGS.md`](spikes/FINDINGS.md)*

## 1. Aanleiding en vraagstelling

Meerdere repos (waaronder deze PowerPoint-inverter) leunen op **python-pptx** voor het
lezen en bewerken van .pptx-bestanden. De vraag: op welke spec is die library gebouwd,
en wat is een goede aanpak voor een JavaScript-variant die (a) in alle runtimes draait
(Node, Deno, Bun, browser, edge/Workers), (b) snel is, en (c) een fijnere API biedt —
uiteindelijk splitsbaar zodat dezelfde onderlaag ook Word- en Excel-libraries kan dragen.

## 2. Het spec-fundament

- **ECMA-376 "Office Open XML" (OOXML)**, identiek gestandaardiseerd als **ISO/IEC 29500**,
  is de governing spec ([ecma-international.org](https://ecma-international.org/publications-and-standards/standards/ecma-376/)).
- **Part 2 — Open Packaging Conventions (OPC):** het zip-containerformaat met
  `[Content_Types].xml` en het `_rels/`-relatiemodel. De "envelop" om elk Office-bestand.
- **Part 1 — PresentationML** (`p:`): slides, layouts, masters, presentation.xml.
- **Part 1 — DrawingML** (`a:`): shapes, geometrie, fills, kleuren, thema's, tekst.
  Vrijwel al het inhoudelijke werk (kleuren, tekst, afbeeldingen) leeft hier — en
  DrawingML wordt gedeeld door pptx, docx én xlsx.
- **Conformance:** er zijn twee klassen, *Strict* en *Transitional*. Vrijwel alle echte
  bestanden (en alles wat PowerPoint schrijft) zijn **Transitional** — dat is het doel,
  niet Strict ([Library of Congress](https://www.loc.gov/preservation/digital/formats/fdd/fdd000399.shtml)).
- python-pptx verwijst per feature naar ISO/IEC 29500-secties
  ([docs](https://python-pptx.readthedocs.io/en/latest/dev/analysis/)) en is architectonisch
  een laag **lazy proxy-objecten op een lxml-elementtree**: alleen aangeraakte XML wordt
  geparsed, al het andere blijft byte-voor-byte bewaard. Die round-trip-fidelity is de
  eigenschap die vrijwel alle JS-libraries missen — en het na te volgen model.

## 3. Het gat in het JavaScript-ecosysteem (2025–2026)

| Library | Status |
|---|---|
| [PptxGenJS](https://github.com/gitbrent/PptxGenJS) | Alleen *schrijven*; kan geen bestaande bestanden lezen/bewerken. Onderhouden (v4, 2025). |
| [pptx-automizer](https://github.com/singerla/pptx-automizer) | Het dichtst bij read+edit (template-chirurgie), maar Node-only, callbacks op raw XML. |
| officegen | Dood (~5 jaar geen release). |
| [docxtemplater](https://docxtemplater.com/) | Alleen templating; de nuttige pptx-modules zijn betaald (~€500/module/jaar). |
| pptx-parser / pptx2json / [pptxtojson](https://github.com/pipipi-pikachu/pptxtojson) | Read-only éénrichtingsconverters, deels verouderd. |
| Rust-crates (`pptx`, `office_oxide`) | Bestaan, maar geen serieuze npm-adoptie of gepolijste WASM-binding. |

**Conclusie:** er bestaat geen JS-library met python-pptx-pariteit (openen → inspecteren
→ bewerken → opslaan met fidelity) die cross-runtime draait. Referentie-ontwerpen:
[dolanmiu/docx](https://github.com/dolanmiu/docx) (beste TS-API in OOXML-land, scheept de
ISO-XSD's in-repo als source of truth, maar creatie-georiënteerd) en
[SheetJS](https://docs.sheetjs.com/docs/csf/) (bewijs dat een pure-JS objectmodel schaalt;
waarschuwing qua distributie/licentie-frictie).

## 4. Architectuurkeuzes (gevalideerd in spikes)

1. **Pure TypeScript, geen WASM als fundament.** Pptx-parts zijn KB's, geen MB's; een
   lazy pure-TS core is 5,5× sneller dan python-pptx gebleken (spike 4). WASM-marshalling
   vreet de winst op bij een objectmodel-API en knelt op edge-bundlelimieten. De zip/XML-laag
   blijft achter een interface zodat een WASM-fastpath later inpasbaar is.
2. **ESM-only, web-baseline-only core.** Geen `Buffer`, `fs` of `node:*` — alleen
   `Uint8Array`, `DataView`, `TextEncoder/Decoder`, optioneel Web Streams. Runtime-gemak
   (`fromFile()`) in aparte entrypoints. Bewezen: byte-identieke output op Node 22 en
   Bun 1.3 (spike 5).
3. **Zip zelf doen op [fflate](https://github.com/101arrowz/fflate).** De OPC-container is
   ~140 regels (spike 1). Sleutel-optimalisatie: bewaar per entry de originele
   *gecomprimeerde* bytes en kopieer ongewijzigde parts rauw door bij `save()` —
   save ging van 36ms → 0,6ms. Native `CompressionStream("deflate-raw")` is overal
   aanwezig als optioneel fastpath.
4. **XML via fast-xml-parser** (`preserveOrder`, `trimValues:false`): round-tript
   PresentationML op quote-stijl en één `\r\n` na exact, en behoudt significante spaties.
   txml is 4× sneller maar verliest trailing whitespace in tekstruns — dealbreaker
   (spike 2). Geen custom tokenizer nodig voor v1.
5. **Lazy proxies op de live XML-tree** (het python-pptx-model): parse alleen aangeraakte
   parts, her-serialiseer alleen dirty parts, bewaar al het onbekende verbatim (spike 3 —
   volledige inverter-flow van deze repo, gevalideerd door python-pptx zelf).

### Benchmark (invert + save, 755 KiB deck, mediaan van 10)

| Implementatie | Mediaan |
|---|---|
| python-pptx 1.0.2 | 39,1 ms |
| Prototype, alles her-deflaten | 44,0 ms |
| **Prototype, lazy + copy-through** | **7,1 ms (Node) / 8,5 ms (Bun)** |

## 5. Package-split: de spec als laaggrens

Gevalideerd in spike 6–7: de onderlagen zijn echt formaat-agnostisch. Een complete
WordprocessingML-minilaag (paragrafen lezen, runs herkleuren) bleek **~40 regels** bovenop
dezelfde `opc`+`xml`-packages, gevalideerd met python-docx inclusief
trailing-space-fidelityprobe. Zelfs `mainPart()` is gedeeld: pptx en docx vinden hun
hoofddocument via dezelfde `officeDocument`-relationship.

```
@scope/xml    fidelity-behoudende parse/serialize + tree-helpers      (formaat-agnostisch)
@scope/opc    ECMA-376 Part 2: zip, parts, relationships,             (formaat-agnostisch)
              target-resolutie, mainPart()
@scope/dml    gedeeld DrawingML: clrScheme, kleurtransforms, units    (formaat-agnostisch)
@scope/pptx   PresentationML-proxies + fluent laag
@scope/docx   later — WordprocessingML op dezelfde onderlaag
@scope/xlsx   later — SpreadsheetML op dezelfde onderlaag
```

Precedent: python-pptx en python-docx slepen elk een *gedupliceerde* interne opc-package
mee (python-opc strandde ooit); .NET's Open XML SDK heeft de OPC-laag wél apart
(`System.IO.Packaging`). De grens dml↔pptx tekende zichzelf in spike 7: pure kleurwiskunde
en clrScheme-parsing zijn gedeeld, de `p:clrMap`-indirectie en de
slide→layout→master→theme-ketenwandeling zijn PresentationML-specifiek.

### Theme-kleurresolutie (spike 7) — de differentiator

`schemeClr` → echte RGB, wat python-pptx niet kan (daar geeft `run.font.color.rgb` dan
`None`). Gevalideerd drie kanten op: PowerPoint's eigen UI-waarden voor de
accent1-varianten (±1/kanaal, merendeel exact; `L' = L·lumMod + lumOff` in HSL), een
sweep van 101 schemeClr-nodes over echte decks zonder één miss, en cross-validatie tegen
een deck geschreven door python-pptx's eigen theme-color-API. Voor de inverter-use-case
betekent dit: ook theme-gekleurde tekst en vlakken kunnen straks geïnverteerd worden.

## 6. API-ontwerp

Drie lagen: **OPC (publieke escape hatch) → proxies (python-pptx-vormig, maar getypeerd
en compacter) → fluent/templating**. De proxy-laag houdt het mentale model van
python-pptx zodat migratie 1-op-1 overzet; de fluent laag is wat python-pptx nooit kreeg.

### Leidend principe: de API als ladder

Toetssteen voor dit ontwerp is [*APIs as ladders*](https://blog.sbensu.com/posts/apis-as-ladders/)
(Sebastian Bensusan; sinds 2019 in gebruik bij Stripe): een API is een leerladder waarop
elke geleerde concept-sport meer problemen oplosbaar maakt. Beginners eisen *convenient*,
gevorderden *gradual* (geen "knowledge cliffs"), experts *flexible* — en je bouwt in
omgekeerde volgorde: **eerst flexibel, dan gradueel, dan convenient**. Onze spike-volgorde
(OPC → proxies → fluent) volgde dat al; de publieke OPC-laag garandeert dat "sorry, onze
API zou dat moeten kunnen maar kan het niet" nooit ons antwoord is. De ladder-toets
scherpte het ontwerp op vijf punten aan:

1. **Closure property: fluent geeft de proxy terug.** `s.addText(...)` retourneert de
   `Shape`, geen `void` — elke gemaksoperatie landt op de volgende sport in plaats van
   in een doodlopend steegje.
2. **Geen semantische sprong tussen lagen.** Unit-tagged waardes (`cm(2)`, `pt(32)`) en
   het kleurtype zijn op élke laag hetzelfde type; alleen de XML-laag spreekt EMU.
3. **Tussensport naar de XML.** `shape.xml` geeft geen kale parser-tree maar een dun
   `XmlElement`-wrappertje met de publieke helpers uit de `xml`-package
   (`firstChild`/`walk`/`attrs`), en elke proxy documenteert wélk element hij wrapt
   (à la python-pptx' analysis-docs).
4. **Anti-create-react-app-regel.** Elke fluent methode toont in zijn documentatie het
   proxy-equivalent ("dit is suiker voor …"), zodat elke gemakssport de laag eronder
   onthult in plaats van verstopt.
5. **Middensport voor kleuren.** Tussen `"#E8E8F0"` en raw `lumMod`-transforms zit het
   PowerPoint-UI-vocabulaire als API: `{ theme: "accent1", lighter: 0.4 }` ("Accent 1,
   Lighter 40%") — vertaalt intern naar lumMod/lumOff.

De `./effect`- en `./result`-adapters (§7) zijn in ladder-termen geen extra sporten maar
**parallelle ladders met dezelfde sporten**: dunne vertalingen over dezelfde core, dus in
elk ecosysteem dezelfde leercurve.

```ts
import { Presentation } from "@scope/pptx";

const deck = await Presentation.open(bytes);           // Uint8Array | ArrayBuffer | Blob

for (const slide of deck.slides) {
  slide.background.fill.solid("#1A1A2E");
  for (const shape of slide.shapes) {
    for (const run of shape.textRuns())                 // flattent paragraphs → runs
      run.font.color = "#E8E8F0";
    if (shape.isPicture()) {                            // TS type guard i.p.v. enum-vergelijking
      shape.image.replace(await invert(await shape.image.bytes()));
    }
  }
}
const out = await deck.save();
```

```ts
// Theme-resolutie en overerving — waar python-pptx None teruggeeft:
run.font.color.raw;         // { scheme: "accent1", lumMod: 0.6, lumOff: 0.4 } | { rgb: "..." } | null
run.font.color.resolve();   // "#8EAADB" — via clrMap + master/theme-keten
run.font.color.effective(); // loopt ook run → paragraaf → placeholder → master af
```

```ts
// Fluent creatie met unit-tagged waardes (geen EMU-rekenwerk). Elke fluent
// call geeft de onderliggende proxy terug (ladder-regel 1):
import { pt, cm } from "@scope/pptx/units";
deck.addSlide((s) => {
  s.title("Kwartaalcijfers Q3");
  const box = s.addText("Omzet +12%", {                       // → Shape, geen void
    at: [cm(2), cm(4)],
    font: { size: pt(32), bold: true, color: { theme: "accent1", lighter: 0.4 } }, // ladder-regel 5
  });
  box.name = "KPI";                                           // naadloos één sport lager
});

// First-class templating (de docxtemplater/pptx-automizer-use-case in de core):
template.cloneSlide(2, (s) => {
  s.fillPlaceholders({ name: product.name, price: `€ ${product.price}` });
  s.shape("HeroImage").image.replace(product.photo);
});

// Escape hatches — shape._element en slide.part.package, maar dan als nette API.
// shape.xml is een XmlElement-wrapper met de publieke xml-helpers (ladder-regel 3):
shape.xml.firstChild("p:txBody");  slide.part.name;
deck.package.relationshipsOf(slide.part.name);
```

Verdere ontwerpkeuzes: strikte TS-types (op termijn gegenereerd uit de ECMA-376 XSD's,
zoals dolanmiu/docx ze in-repo heeft maar niemand end-to-end doet), `toJSON()` als bewust
lossy interchange-laag voor AI-pipelines/diffing (het XML-model blijft bron van waarheid),
en async `save()` zodat streaming later zonder API-breuk kan.

## 7. Foutmodel en ecosysteem-adapters

De core throwt gewone `Error`-subclasses **met een `_tag`-property** (nul dependencies).
Zowel Effect's `catchTag` als better-result's tagged matching werken op `_tag`, dus één
foutdefinitie voedt drie API-smaken via dunne, optionele subpath-adapters:

```jsonc
{
  "exports": { ".": "...", "./node": "...", "./effect": "...", "./result": "..." },
  "peerDependencies": { "effect": ">=4.0.0-beta <5", "better-result": ">=3 <4" },
  "peerDependenciesMeta": { "effect": { "optional": true }, "better-result": { "optional": true } }
}
```

- **`.` (Promise/sync):** de default; geen dependencies.
- **`./effect` ([Effect v4](https://www.effect.website/blog/releases/effect/40-beta), nu beta → LTS):**
  `Effect.gen`-composities, typed error-channel, en vooral batch-verwerking:
  `Effect.forEach(files, invert, { concurrency: 2 })` met timeouts en per-bestand-isolatie
  vervangt de handmatige ProcessPool/BatchResult-machinerie van de huidige Python-inverter.
  Adapter ≈ 100 regels (`Effect.try`/`tryPromise` + niets meer).
- **`./result` ([better-result v3](https://github.com/dmmulroy/better-result)):**
  `Result.gen` + `yield*`, `Result.tryPromise` met retry, en `Result.codec` voor het
  serialiseren van `Result<T, PptxError>` over Worker/RPC-grenzen. Voor apps die expliciete
  fouten willen zonder een runtime te adopteren — de auteur zegt zelf: kun je Effect
  gebruiken, gebruik dan Effect. Adapter ≈ 50 regels.

Elke feature in de core landt automatisch in alle drie de smaken; bij churn in de
beta-API's hoeft alleen het adapterbestand mee.

## 8. Open vragen en roadmap

**Open (bekend, geen blockers):**
- PowerPoint's exacte kleurafronding wijkt soms ±1/kanaal af (vermoedelijk fixed-point);
  `hueMod`/`comp`/`inv`/`gamma` en `phClr`-doorvertaling nog niet geïmplementeerd.
- Zip64-randen (netjes op falen), `mc:AlternateContent` (Part 3) bij lezen.
- Deno en Cloudflare workerd horen in de CI-matrix (core is web-baseline, risico laag).
- De echte round-trip-stresstest: een fuzz-corpus van decks uit de andere repos.

**Roadmap-voorstel:**
1. Monorepo-opzet: `xml`/`opc`/`dml`/`pptx` in TypeScript, testmatrix Node/Bun/Deno/workerd + Playwright.
2. Corpus-round-trip-suite (decks uit de eigen repos) als regressie-fundament.
3. pptx-proxylaag tot inverter-pariteit → eerste echte consument: deze repo porten.
4. Fluent + templating-laag; `./effect`- en `./result`-adapters.
5. XSD-typegeneratie; daarna `docx` als tweede formaat op de bewezen onderlaag.

## Bronnen

- Spec: [ECMA-376](https://ecma-international.org/publications-and-standards/standards/ecma-376/) · [LoC OOXML-formaatbeschrijving](https://www.loc.gov/preservation/digital/formats/fdd/fdd000399.shtml) · [python-pptx analysis-docs](https://python-pptx.readthedocs.io/en/latest/dev/analysis/)
- Ecosysteem: [PptxGenJS](https://github.com/gitbrent/PptxGenJS) · [pptx-automizer](https://github.com/singerla/pptx-automizer) · [docxtemplater-modules](https://docxtemplater.com/shop/modules/) · [dolanmiu/docx](https://github.com/dolanmiu/docx) · [SheetJS CSF](https://docs.sheetjs.com/docs/csf/)
- Bouwstenen: [fflate](https://github.com/101arrowz/fflate) · [fast-xml-parser](https://github.com/NaturalIntelligence/fast-xml-parser) · [txml-benchmarks](https://tnickel.de/2020/08/30/2020-08-how-the-fastest-xml-parser-is-build/) · [Workers web-standards](https://developers.cloudflare.com/workers/runtime-apis/web-standards/)
- Adapters: [Effect v4 beta](https://www.effect.website/blog/releases/effect/40-beta) · [better-result](https://better-result.dev/)
- API-ontwerp: [APIs as ladders — Sebastian Bensusan](https://blog.sbensu.com/posts/apis-as-ladders/)
- Empirie: [`spikes/FINDINGS.md`](spikes/FINDINGS.md) in deze repo
