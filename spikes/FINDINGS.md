# Spike-bevindingen: python-pptx → cross-runtime JavaScript-library

Zes spikes die de aannames uit het researchplan toetsen. Alle code in deze map is
wegwerp-prototype (bewust zonder edge cases als Zip64, data descriptors, strict-mode
OOXML); de conclusies zijn het deliverable.

**Testomgeving:** Node v22.22.2 en Bun 1.3.11, fixtures uit `tests/fixtures/`
(echte PowerPoint-bestanden, 86–755 KiB). Referentie: python-pptx 1.0.2 op Python 3.11.

## Spike 1 — Zelf de OPC/zip-container doen (`01-opc-zip.mjs`, `packages/opc/index.mjs`)

**Vraag:** Is JSZip/zip.js nodig, of is de OPC-container simpel genoeg om zelf te doen
op alleen fflate + web-standaarden?

**Antwoord: zelf doen.** Een complete reader/writer (central directory parsen, local
headers, CRC32, EOCD) is ~140 regels. Beide fixtures lezen foutloos, elke part is
byte-identiek na round-trip, en python-pptx opent onze herschreven bestanden zonder
klachten. Kanttekening: fflate exporteert geen `crc32` — zelf meenemen (10 regels).

**Bonus-inzicht (de grootste performancewinst van alle spikes):** door per entry de
originele *gecomprimeerde* bytes te bewaren en ongewijzigde parts bij `save()` rauw
door te kopiëren, vervalt vrijwel alle inflate/deflate-werk. Media (al gecomprimeerde
JPG/PNG, het gros van de bytes) wordt dan nooit aangeraakt. Save ging van 36ms → 0,6ms.

## Spike 2 — XML round-trip-fidelity (`02-xml-roundtrip.mjs`)

**Vraag (de riskantste aanname):** overleeft PresentationML een parse→serialize-cyclus
door een generieke JS-parser?

**Antwoord: ja, met fast-xml-parser — niet met txml.**

| Parser | Parse (2,4 KiB slide) | Round-trip | Trailing spaces in `<a:t>` |
|---|---|---|---|
| txml | 0,12 ms | verliest structuur | **verloren** ✗ |
| fast-xml-parser (`preserveOrder`, `trimValues:false`) | 0,50 ms | identiek op XML-declaratie-`\r\n` en quote-stijl na | behouden ✓ |

txml is 4× sneller maar de stringify verliest trailing whitespace in tekstruns — een
dealbreaker (PowerPoint-tekst bevat significante spaties, vandaar `xml:space="preserve"`).
De txml-*parser* zou nog als read-only fastpath kunnen dienen, maar voor lezen+schrijven
is fast-xml-parser met `preserveOrder: true, trimValues: false, parseTagValue: false` de
juiste keuze. PowerPoint en python-pptx accepteren de her-geserialiseerde XML.

## Spike 3 — Lazy-proxy-architectuur werkt (`03-proxy-prototype.mjs`, `packages/pptx/index.mjs`)

**Vraag:** is python-pptx's architectuur (proxies op een lazy geparsede XML-tree, alleen
dirty parts her-serialiseren) haalbaar in ~150 regels JS, met een API die de flow van
deze repo aankan?

**Antwoord: ja.** Het prototype doet de volledige inverter-flow van deze repo:

```js
const pres = Presentation.open(bytes);
for (const slide of pres.slides) {
  slide.setBackground("1A1A2E");                    // fill.solid() + fore_color.rgb
  for (const shape of slide.shapes()) {
    if (shape.hasTextFrame)
      for (const run of shape.runs()) run.setFontColor("E8E8F0");
    if (shape.isPicture) shape.imageBlob();          // r:embed via _rels resolven
  }
}
const out = pres.save();
```

Validatie door python-pptx zelf (`03-validate.py`): bestand opent, 6/6 achtergronden
solid met juiste kleur, 6/6 runs juiste fontkleur. Relationship-resolving (r:embed →
`ppt/media/*`) werkt.

## Spike 4 — Performance vs python-pptx (`04-bench.{mjs,py}`)

Zelfde workload (invert + save, 755 KiB deck, mediaan van 10):

| Implementatie | Mediaan |
|---|---|
| python-pptx 1.0.2 | 39,1 ms |
| prototype, alles her-deflaten | 44,0 ms |
| **prototype, lazy + copy-through** | **7,1 ms (Node) / 8,5 ms (Bun)** |

≈ **5,5× sneller dan python-pptx**, en de winst komt niet uit de parser maar uit de
architectuur: unzip 0,1 ms (lazy, niets inflaten tot het nodig is), rezip 0,6 ms
(alleen dirty slide-parts deflaten). De aanname "pure TS is snel genoeg, WASM niet
nodig als fundament" is hiermee bevestigd — er valt op deze workload simpelweg nog
maar ~6 ms te winnen.

## Spike 5 — Cross-runtime (`05-runtime.mjs`)

- Core-packages (`packages/`) bevatten **nul** Node-specifieke APIs (geen `Buffer`, `fs`, `node:*`,
  `process`) — alleen `Uint8Array`/`DataView`/`TextDecoder`/`TextEncoder`.
- Draait ongewijzigd onder Node 22 én Bun 1.3; output is **byte-identiek**
  (zelfde SHA-256) → deterministisch schrijven werkt cross-runtime.
- `CompressionStream("deflate-raw")` is in beide runtimes aanwezig → native fastpath
  is beschikbaar, maar met copy-through (spike 4) nauwelijks nog nodig.
- Deno niet getest (niet in deze omgeving); risico laag omdat de core alleen
  web-baseline gebruikt, maar hoort in de CI-matrix van het echte project.

## Spike 6 — Gelaagde package-split: OPC als formaat-agnostische onderlaag (`06-layered-packages.mjs`)

**Vraag:** kan de library gesplitst worden in een low-level package dat "de spec praat"
(ECMA-376 Part 2 / OPC + XML-infrastructuur), zodat Word/Excel-libraries later op
dezelfde onderlaag gebouwd kunnen worden?

**Antwoord: ja, en de laaggrens ligt precies waar de spec hem legt.** De code is
geherstructureerd naar drie packages:

```
packages/xml/    fidelity-preserving parse/serialize + tree-helpers   (formaat-agnostisch)
packages/opc/    ECMA-376 Part 2: zip, parts, relationships,          (formaat-agnostisch)
                 target-resolutie, mainPart() via officeDocument-rel
packages/pptx/   PresentationML-proxies (slides/shapes/runs)          (formaat-specifiek)
```

Bewijs van formaat-agnosticisme in twee aktes:

- **Akte A:** de volledige pptx-invert-flow draait ongewijzigd op de nieuwe lagen,
  mét als bonus spec-correcte slide-volgorde via `p:sldIdLst` + rels (open vraag uit
  ronde 1 opgelost) — de pptx-laag bevat nu nul zip- of relationship-code.
- **Akte B:** een complete WordprocessingML-minilaag (paragrafen lezen, runs
  herkleuren) bleek **~40 regels** bovenop dezelfde `opc`+`xml`-packages. Een door
  python-docx gegenereerde .docx wordt gelezen, herkleurd en teruggeschreven;
  python-docx valideert het resultaat (3/3 runs juiste kleur, en de trailing space
  in "Hello from python-docx. " overleeft de round-trip — fidelityprobe geslaagd).
- Zelfs `mainPart()` is gedeeld: pptx én docx vinden hun hoofddocument via exact
  dezelfde `officeDocument`-relationship op package-niveau.

Precedent dat deze split de juiste keuze is: python-pptx en python-docx dragen elk
een *gedupliceerde* interne `opc`-package mee (de aparte python-opc-package is ooit
gestrand), terwijl .NET's Open XML SDK de OPC-laag wél apart heeft
(`System.IO.Packaging`). De gedeelde DrawingML-laag (kleuren, thema's, units — door
alle drie de formaten gebruikt) is de logische vierde package zodra theme-resolutie
gespiked wordt.

Voorgestelde package-structuur voor het echte project:

```
@scope/ooxml-xml   (of gevouwen in opc)     ← spike: packages/xml
@scope/opc                                   ← spike: packages/opc
@scope/ooxml-dml   DrawingML: kleuren/thema's/units (nog niet gespiked)
@scope/pptx                                  ← spike: packages/pptx
@scope/docx        later                     ← spike: WordDocument-demo (40 regels)
@scope/xlsx        later
```

## Beantwoorde aannames

1. ✅ Eigen OPC-laag op fflate: simpel, correct, en de sleutel tot copy-through-saves.
2. ✅ Round-trip-fidelity haalbaar met een bestaande parser (fast-xml-parser + preserveOrder);
   geen custom tokenizer nodig voor v1.
3. ✅ python-pptx's lazy-proxy-model vertaalt direct naar JS en de API kan compacter.
4. ✅ Pure TS ruim snel genoeg (5,5× python-pptx); WASM uitgesteld, terecht.
5. ✅ Web-baseline-only core draait identiek op meerdere runtimes.
6. ✅ De OPC/XML-onderlaag is formaat-agnostisch splitsbaar: dezelfde packages dragen
   pptx én een 40-regels docx-laag (spike 6).

## Openstaande vragen voor een volgende ronde

- **Theme-kleurresolutie** (`schemeClr` → RGB via master/layout/theme-keten): de
  beloofde differentiator, nog niet gespiked — goede kandidaat voor spike 6.
- **Grote bestanden / Zip64** (>4 GB offsets, >65k entries): irrelevant voor pptx in de
  praktijk, maar de writer moet er netjes op falen.
- **`xml:space`/entity-details**: fast-xml-parser ontsnapt entiteiten correct in onze
  tests, maar een fuzz-ronde over een corpus echte decks (de andere repos!) is de
  echte test voor round-trip-fidelity.
- **Deno + Cloudflare workerd** in de testmatrix.

## Reproduceren

```sh
cd spikes && npm install
node 01-opc-zip.mjs && node 02-xml-roundtrip.mjs && node 03-proxy-prototype.mjs
uv run python spikes/03-validate.py spikes/out/spike3-inverted.pptx  # vanuit repo-root
node 04-bench.mjs && uv run python spikes/04-bench.py tests/fixtures/hagar-presentatie.pptx
node 05-runtime.mjs && bun 05-runtime.mjs
# spike 6 (vanuit repo-root): layered packages, pptx + docx op dezelfde onderlaag
uv run --with python-docx spikes/06-validate.py generate
cd spikes && node 06-layered-packages.mjs && cd ..
uv run python spikes/03-validate.py spikes/out/spike6-inverted.pptx
uv run --with python-docx spikes/06-validate.py verify
```
