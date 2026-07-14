// contribute.test.js -- node --test suite for the /api/contribute Pages Function.
//
// functions/api/contribute.js is a Cloudflare Pages Function (ESM `export` in a
// CommonJS package with no "type":"module"), so it cannot be `require`d or
// cross-imported from this CJS test without breaking the existing meet-recorder
// CJS suite. Following the repo convention (static/js/meet-recorder.test.js),
// the security-critical PURE helpers are mirrored below and MUST be kept in
// lock-step with functions/api/contribute.js by code review. These tests lock
// the header-injection guard, the base64 encoder, and the magic-byte type sniff.
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');

// ----------------------------------------------------------------------
// Pure helpers -- mirror EXACTLY functions/api/contribute.js (lock-step).
// ----------------------------------------------------------------------

// clean(): strip CR/LF/control chars, trim, hard length cap.
function clean(value, max) {
  return String(value == null ? '' : value)
    .replace(/[\r\n\t\f\v\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, ' ')
    .trim()
    .slice(0, max);
}

// cleanLines(): multiline sanitiser for the optional social-links field --
// preserves newlines (one link per line) but normalises CRLF/CR, strips control
// chars, drops blank lines, caps line count/per-line/total. Mirror EXACTLY.
function cleanLines(value, maxLines, maxLineLen, maxTotal) {
  const lines = String(value == null ? '' : value)
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map((line) => line.replace(/[\t\f\v\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, ' ').trim().slice(0, maxLineLen))
    .filter((line) => line.length > 0)
    .slice(0, maxLines);
  return lines.join('\n').slice(0, maxTotal);
}

// bytesToBase64(): chunked base64 (avoids the fromCharCode.apply stack blow-up).
function bytesToBase64(bytes) {
  let binary = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return Buffer.from(binary, 'binary').toString('base64'); // btoa() equivalent in Node
}

// EMAIL_RE: pragmatic email shape check (mirror of functions/api/contribute.js).
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// sniffImageType(): true image type from magic bytes, ignoring client Content-Type.
function sniffImageType(bytes) {
  if (!bytes || bytes.length < 12) return null;
  if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return 'image/jpeg';
  if (
    bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47 &&
    bytes[4] === 0x0d && bytes[5] === 0x0a && bytes[6] === 0x1a && bytes[7] === 0x0a
  ) return 'image/png';
  if (
    bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46 &&
    bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50
  ) return 'image/webp';
  return null;
}

// ----------------------------------------------------------------------
// clean() -- header/CRLF-injection guard
// ----------------------------------------------------------------------

test('clean strips CR/LF so a field cannot inject an email header', () => {
  const out = clean('Alice\r\nBcc: attacker@evil.example', 200);
  assert.ok(!out.includes('\r'));
  assert.ok(!out.includes('\n'));
  // each stripped control char becomes one space, so CRLF -> two spaces (no collapse)
  assert.equal(out, 'Alice  Bcc: attacker@evil.example');
});

test('clean strips tab/form-feed/vertical-tab and other control chars', () => {
  assert.equal(clean('a\tb\fc\vd', 200), 'a b c d');
  assert.equal(clean('x\x00\x07y\x7f', 200), 'x  y'); // NUL, BEL, DEL -> spaces
});

test('clean trims surrounding whitespace and enforces the length cap', () => {
  assert.equal(clean('  padded  ', 200), 'padded');
  assert.equal(clean('abcdef', 3), 'abc');
});

test('clean coerces null/undefined to an empty string', () => {
  assert.equal(clean(null, 10), '');
  assert.equal(clean(undefined, 10), '');
});

// ----------------------------------------------------------------------
// bytesToBase64() -- attachment encoder
// ----------------------------------------------------------------------

test('bytesToBase64 round-trips arbitrary byte values', () => {
  const bytes = new Uint8Array([0, 1, 2, 127, 128, 254, 255, 65, 66, 67]);
  const decoded = Uint8Array.from(Buffer.from(bytesToBase64(bytes), 'base64'));
  assert.deepEqual([...decoded], [...bytes]);
});

test('bytesToBase64 handles a large multi-chunk buffer without a stack overflow', () => {
  const big = new Uint8Array(100000);
  for (let i = 0; i < big.length; i += 1) big[i] = i % 256;
  const decoded = Uint8Array.from(Buffer.from(bytesToBase64(big), 'base64'));
  assert.equal(decoded.length, big.length);
  assert.deepEqual([...decoded.subarray(0, 8)], [...big.subarray(0, 8)]);
  assert.deepEqual([...decoded.subarray(-8)], [...big.subarray(-8)]);
});

// ----------------------------------------------------------------------
// sniffImageType() -- content-based type gate (defeats a forged Content-Type)
// ----------------------------------------------------------------------

test('sniffImageType recognises JPEG/PNG/WebP by magic bytes', () => {
  const jpeg = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0, 0, 0, 0, 0, 0, 0, 0]);
  const png = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0]);
  const webp = new Uint8Array([0x52, 0x49, 0x46, 0x46, 1, 2, 3, 4, 0x57, 0x45, 0x42, 0x50]);
  assert.equal(sniffImageType(jpeg), 'image/jpeg');
  assert.equal(sniffImageType(png), 'image/png');
  assert.equal(sniffImageType(webp), 'image/webp');
});

test('sniffImageType rejects a payload that merely claims to be an image', () => {
  const html = new Uint8Array([...Buffer.from('<html>not an image at all</html>')]);
  assert.equal(sniffImageType(html), null);
});

test('sniffImageType rejects too-short and empty inputs', () => {
  assert.equal(sniffImageType(new Uint8Array([0xff, 0xd8, 0xff])), null); // < 12 bytes
  assert.equal(sniffImageType(new Uint8Array(0)), null);
  assert.equal(sniffImageType(null), null);
});

test('EMAIL_RE accepts plausible addresses', () => {
  for (const e of ['a@b.co', 'hoi@hoiboy.uk', 'first.last+tag@sub.example.com']) {
    assert.equal(EMAIL_RE.test(e), true, e);
  }
});

test('EMAIL_RE rejects malformed addresses', () => {
  for (const e of ['', 'plainstring', 'no@domain', 'no-at.example.com', 'spaces in@x.com', 'a@b@c.com', '@nolocal.com']) {
    assert.equal(EMAIL_RE.test(e), false, e);
  }
});

// ----------------------------------------------------------------------
// cleanLines() -- multiline social-links sanitiser (one link per line)
// ----------------------------------------------------------------------

test('cleanLines keeps one link per line and normalises CRLF/CR to LF', () => {
  const out = cleanLines('https://a.com\r\nhttps://b.com\rhttps://c.com', 20, 300, 1000);
  assert.equal(out, 'https://a.com\nhttps://b.com\nhttps://c.com');
});

test('cleanLines drops blank lines and trims each line', () => {
  const out = cleanLines('  https://a.com  \n\n\n   \nhttps://b.com', 20, 300, 1000);
  assert.equal(out, 'https://a.com\nhttps://b.com');
});

test('cleanLines strips tab/control chars so nothing structures the MIME body', () => {
  // A tab or control char cannot smuggle structure in: tab -> space, controls
  // removed, and the (safe) newline between real links is preserved.
  const out = cleanLines('https://a.com\tBcc:evil\x00\x07\nhttps://b.com', 20, 300, 1000);
  assert.equal(out, 'https://a.com Bcc:evil\nhttps://b.com');
});

test('cleanLines caps the number of lines', () => {
  const many = Array.from({ length: 25 }, (_, i) => 'https://s' + i + '.com').join('\n');
  assert.equal(cleanLines(many, 20, 300, 1000).split('\n').length, 20);
});

test('cleanLines caps per-line and total length', () => {
  const longLine = 'https://' + 'a'.repeat(500) + '.com';
  assert.ok(cleanLines(longLine, 20, 300, 1000).length <= 300);
  const big = Array.from({ length: 20 }, () => 'https://' + 'a'.repeat(290) + '.com').join('\n');
  assert.ok(cleanLines(big, 20, 300, 1000).length <= 1000);
});

test('cleanLines coerces null/undefined/blank to an empty string', () => {
  assert.equal(cleanLines(null, 20, 300, 1000), '');
  assert.equal(cleanLines(undefined, 20, 300, 1000), '');
  assert.equal(cleanLines('', 20, 300, 1000), '');
  assert.equal(cleanLines('   \n  \n', 20, 300, 1000), '');
});
