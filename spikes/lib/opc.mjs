// Spike: minimal OPC (zip) reader/writer on Web-platform APIs + fflate only.
// Question answered: is hand-rolling the zip container simple enough that we
// don't need JSZip/zip.js, and does it survive a PowerPoint round-trip?
import { inflateSync, deflateSync } from "fflate";

// fflate keeps its crc32 internal, so bring our own (standard table-based).
const CRC_TABLE = new Uint32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c;
});
function crc32(data) {
  let c = 0xffffffff;
  for (let i = 0; i < data.length; i++) c = CRC_TABLE[(c ^ data[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

const td = new TextDecoder();
const te = new TextEncoder();

const EOCD_SIG = 0x06054b50;
const CEN_SIG = 0x02014b50;
const LOC_SIG = 0x04034b50;

/** Read a zip archive into a Map<name, {data: Uint8Array}> (eager for spike purposes). */
export function readZip(bytes) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  // Find End Of Central Directory record (scan back over optional comment).
  let eocd = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 22 - 65535); i--) {
    if (dv.getUint32(i, true) === EOCD_SIG) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("not a zip: EOCD not found");
  const count = dv.getUint16(eocd + 10, true);
  let off = dv.getUint32(eocd + 16, true);

  const entries = new Map();
  for (let i = 0; i < count; i++) {
    if (dv.getUint32(off, true) !== CEN_SIG) throw new Error("bad central directory entry");
    const method = dv.getUint16(off + 10, true);
    const csize = dv.getUint32(off + 20, true);
    const usize = dv.getUint32(off + 24, true);
    const nameLen = dv.getUint16(off + 28, true);
    const extraLen = dv.getUint16(off + 30, true);
    const commentLen = dv.getUint16(off + 32, true);
    const localOff = dv.getUint32(off + 42, true);
    const name = td.decode(bytes.subarray(off + 46, off + 46 + nameLen));

    // Local header repeats name/extra lengths; data follows it.
    if (dv.getUint32(localOff, true) !== LOC_SIG) throw new Error("bad local header");
    const lNameLen = dv.getUint16(localOff + 26, true);
    const lExtraLen = dv.getUint16(localOff + 28, true);
    const dataStart = localOff + 30 + lNameLen + lExtraLen;
    const raw = bytes.subarray(dataStart, dataStart + csize);
    const crc = dv.getUint32(off + 16, true);
    // Lazy: inflate on first access. Untouched parts keep their original
    // compressed bytes, which writeZip copies through without re-deflating.
    const entry = {
      raw, method, crc, usize,
      dirty: false,
      _data: null,
      get data() {
        return (this._data ??= this.method === 0 ? this.raw.slice() : inflateSync(this.raw, { size: this.usize }));
      },
      set data(v) { this._data = v; this.dirty = true; },
    };
    entries.set(name, entry);
    off += 46 + nameLen + extraLen + commentLen;
  }
  return entries;
}

/** Write a Map<name, {data}> back to a zip (deflate everything, like PowerPoint does). */
export function writeZip(entries) {
  const chunks = [];
  const central = [];
  let offset = 0;
  for (const [name, entry] of entries) {
    const nameBytes = te.encode(name);
    let crc, body, method, usize;
    if (entry.raw && !entry.dirty) {
      // Clean part: copy original compressed bytes through, no inflate/deflate.
      ({ crc, method, usize } = entry);
      body = entry.raw;
    } else {
      const data = entry.data;
      usize = data.length;
      crc = crc32(data);
      const compressed = deflateSync(data, { level: 6 });
      // Store when deflate doesn't help (rare for XML, common for already-compressed media).
      const store = compressed.length >= data.length;
      body = store ? data : compressed;
      method = store ? 0 : 8;
    }

    const local = new Uint8Array(30 + nameBytes.length);
    const ldv = new DataView(local.buffer);
    ldv.setUint32(0, LOC_SIG, true);
    ldv.setUint16(4, 20, true); // version needed
    ldv.setUint16(8, method, true);
    ldv.setUint32(14, crc, true);
    ldv.setUint32(18, body.length, true);
    ldv.setUint32(22, usize, true);
    ldv.setUint16(26, nameBytes.length, true);
    local.set(nameBytes, 30);

    const cen = new Uint8Array(46 + nameBytes.length);
    const cdv = new DataView(cen.buffer);
    cdv.setUint32(0, CEN_SIG, true);
    cdv.setUint16(4, 20, true);
    cdv.setUint16(6, 20, true);
    cdv.setUint16(10, method, true);
    cdv.setUint32(16, crc, true);
    cdv.setUint32(20, body.length, true);
    cdv.setUint32(24, usize, true);
    cdv.setUint16(28, nameBytes.length, true);
    cdv.setUint32(42, offset, true);
    cen.set(nameBytes, 46);
    central.push(cen);

    chunks.push(local, body);
    offset += local.length + body.length;
  }
  const cenStart = offset;
  let cenSize = 0;
  for (const c of central) { chunks.push(c); cenSize += c.length; }
  const eocd = new Uint8Array(22);
  const edv = new DataView(eocd.buffer);
  edv.setUint32(0, EOCD_SIG, true);
  edv.setUint16(8, central.length, true);
  edv.setUint16(10, central.length, true);
  edv.setUint32(12, cenSize, true);
  edv.setUint32(16, cenStart, true);
  chunks.push(eocd);

  const total = chunks.reduce((n, c) => n + c.length, 0);
  const out = new Uint8Array(total);
  let pos = 0;
  for (const c of chunks) { out.set(c, pos); pos += c.length; }
  return out;
}
