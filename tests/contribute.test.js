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

// ----------------------------------------------------------------------
// Consent-label version (#3 AC 1.9).
//
// An Article 9(2)(a) explicit-consent surface: "they ticked a box" is not
// enough on its own, the record has to show WHICH wording they ticked. The
// form posts the version it rendered; the endpoint rejects absent/unknown
// rather than defaulting, because a default would attribute the current
// wording to someone who agreed to different wording.
//
// KNOWN_CONSENT_VERSIONS mirrors functions/api/contribute.js in lock-step per
// this file's header convention. tests/test_agit_consent_version.py asserts
// the two lists and the form's hidden input all agree, so this mirror cannot
// drift silently.
// ----------------------------------------------------------------------

const KNOWN_CONSENT_VERSIONS = ['2026-07-28'];

// Mirror of the endpoint's acceptance test: clean() first, then membership.
function consentVersionAccepted(raw) {
  return KNOWN_CONSENT_VERSIONS.includes(clean(raw, 32));
}

test('consent version: a submission with no consent_version is rejected', () => {
  assert.equal(consentVersionAccepted(undefined), false);
  assert.equal(consentVersionAccepted(null), false);
  assert.equal(consentVersionAccepted(''), false);
});

test('consent version: an unrecognised version is rejected, never defaulted', () => {
  assert.equal(consentVersionAccepted('2026-01-01'), false);
  assert.equal(consentVersionAccepted('latest'), false);
  assert.equal(consentVersionAccepted('2026-07-2'), false);
});

test('consent version: the current label version is accepted', () => {
  assert.equal(consentVersionAccepted('2026-07-28'), true);
});

test('consent version: surrounding whitespace and control chars do not smuggle a match', () => {
  // clean() trims and strips control chars, so a padded value still resolves.
  assert.equal(consentVersionAccepted('  2026-07-28  '), true);
  // ...but injected structure does not become a different accepted value.
  assert.equal(consentVersionAccepted('2026-07-28\nBcc:evil'), false);
});

// ----------------------------------------------------------------------
// FIELD_FLOORS -- the story minimum, and the browser/server agreement (hoiboy-uk#57)
// ----------------------------------------------------------------------

// Mirror EXACTLY functions/api/contribute.js (lock-step, code review). Note the
// asymmetry with the client half below: this file cannot import contribute.js
// (ESM Pages Function in a CommonJS package), so the SERVER side is mirrored,
// but the CLIENT side is the real exported helper. Only one of the two is a copy.
const FIELD_FLOORS = { feature: 1200 };
const FIELD_CAPS_FEATURE = 8000;

// The shipped client helper -- imported, NOT mirrored, so a divergence between
// what the browser counts and what these tests believe cannot hide here.
const { storyLength, STORY_MIN } = require('../static/js/agit-form.js');

/** What the server sees: the browser value after form serialisation, then clean(). */
function serverLength(browserValue) {
  // WHATWG form serialisation normalises every newline in a textarea to CRLF on
  // the wire, so an interior LF arrives as two characters. That is why the
  // server count is always >= the client count and never the other way round.
  const onTheWire = String(browserValue).replace(/\r\n?|\n/g, '\r\n');
  return clean(onTheWire, FIELD_CAPS_FEATURE).length;
}

const serverAccepts = (browserValue) => serverLength(browserValue) >= FIELD_FLOORS.feature;
const clientAccepts = (browserValue) => storyLength(browserValue) >= STORY_MIN;

test('the floor mirrors the shipped client threshold, so the two cannot drift apart', () => {
  assert.equal(FIELD_FLOORS.feature, STORY_MIN);
});

test('shape A: 1200 plain characters, no trailing newline -- both accept', () => {
  const value = 'x'.repeat(1200);
  assert.equal(storyLength(value), 1200);
  assert.equal(serverLength(value), 1200);
  assert.equal(serverAccepts(value), clientAccepts(value));
  assert.equal(serverAccepts(value), true);
});

test('shape B: 1199 characters plus Enter -- both reject, no silent server rejection', () => {
  // The discriminating shape. A client counting raw .value.length would show
  // 1200 and let this through, and the server would then reject it: the member
  // sees green and is refused anyway. Both sides must say no here.
  const value = 'x'.repeat(1199) + '\n';
  assert.equal(storyLength(value), 1199);
  assert.equal(serverLength(value), 1199);
  assert.equal(serverAccepts(value), clientAccepts(value));
  assert.equal(serverAccepts(value), false);
});

test('shape C: one astral emoji among 1200 UTF-16 units -- both accept', () => {
  // Both sides measure .length on a JS string, so one astral character is two
  // units on both. What matters is that they agree, not which unit they use.
  const value = '\u{1F600}' + 'x'.repeat(1198);
  assert.equal(storyLength(value), 1200);
  assert.equal(serverLength(value), 1200);
  assert.equal(serverAccepts(value), clientAccepts(value));
  assert.equal(serverAccepts(value), true);
});

test('shape D: 12 interior newlines -- server counts 1212, both still accept', () => {
  // LF expands to CRLF on the wire, so the server counts 12 higher. It reads as
  // a discrepancy but it is the safe direction: the server can only ever count
  // MORE than the browser, never less.
  // 1200 browser units exactly: 1188 ordinary characters plus 12 INTERIOR
  // newlines (13 blocks joined by 12 separators, so none is leading or trailing
  // and trim() cannot absorb one).
  const value = Array.from({ length: 13 }, (_, i) => 'x'.repeat(i < 12 ? 91 : 96)).join('\n');
  assert.equal(storyLength(value), 1200);
  assert.equal(serverLength(value), 1212);
  assert.equal(serverAccepts(value), clientAccepts(value));
  assert.equal(serverAccepts(value), true);
});

test('the server is never the stricter of the two, across the whole boundary region', () => {
  // The invariant behind "a green counter is a guarantee", swept rather than
  // spot-checked: for every shape and every length around the threshold, the
  // client must never accept something the server would refuse.
  const shapes = {
    plain: (n) => 'x'.repeat(n),
    trailingNewline: (n) => 'x'.repeat(Math.max(0, n - 1)) + '\n',
    interiorNewlines: (n) => 'x\n'.repeat(Math.floor(n / 2)) + 'x'.repeat(n % 2),
    leadingWhitespace: (n) => '  \n' + 'x'.repeat(n),
    tabs: (n) => 'x\t'.repeat(Math.floor(n / 2)) + 'x'.repeat(n % 2),
  };
  for (const [name, build] of Object.entries(shapes)) {
    for (let n = 1190; n <= 1210; n += 1) {
      const value = build(n);
      assert.ok(
        serverLength(value) >= storyLength(value),
        `${name} at n=${n}: server counted ${serverLength(value)} but client counted ${storyLength(value)}`
      );
      if (clientAccepts(value)) {
        assert.equal(serverAccepts(value), true, `${name} at n=${n}: counter said green, server refused`);
      }
    }
  }
});

test('a story one character under the floor is refused by the server', () => {
  assert.equal(serverAccepts('x'.repeat(1199)), false);
  assert.equal(serverAccepts('x'.repeat(1200)), true);
});

test('the floor is measured after clean(), so whitespace padding cannot fake it', () => {
  // A bot padding with spaces or control characters gets nothing: clean() trims
  // the ends, and interior padding is still only as long as it looks.
  assert.equal(serverAccepts('   ' + 'x'.repeat(1199) + '   '), false);
  assert.equal(serverAccepts(' '.repeat(5000)), false);
  assert.equal(serverAccepts(' '.repeat(1200)), false);
});

// ----------------------------------------------------------------------
// Lock-step: the mirror above vs the shipped Pages Function (hoiboy-uk#57)
// ----------------------------------------------------------------------
//
// Every mirrored helper in this file is kept in step with contribute.js BY CODE
// REVIEW, with no automated check -- which means a mirror can drift and this
// whole suite keeps passing while asserting things about a function that no
// longer exists as written. contribute.js is ESM in a CommonJS package so it
// cannot be required, but its SOURCE can still be read, and a constant can be
// compared without executing anything. These two close that gap for the floor.

const CONTRIBUTE_SRC = require('node:fs').readFileSync(
  require('node:path').join(__dirname, '..', 'functions', 'api', 'contribute.js'),
  'utf8'
);

test('lock-step: the mirrored floor equals the one contribute.js actually ships', () => {
  const match = CONTRIBUTE_SRC.match(/FIELD_FLOORS\s*=\s*\{[^}]*feature:\s*(\d+)/);
  assert.ok(match, 'FIELD_FLOORS.feature not found in functions/api/contribute.js');
  assert.equal(
    Number(match[1]),
    FIELD_FLOORS.feature,
    'the mirror in this file has drifted from the shipped Pages Function'
  );
});

test('the server floor is checked after the presence check and before the email format check', () => {
  // Placement is behaviour here, not tidiness. Before the presence check, an
  // empty story would be reported as "too short" instead of "please fill this
  // in". After the email check, a member with both problems gets told about the
  // wrong one. Asserted on the handler body so an unrelated earlier mention
  // cannot satisfy it.
  const presence = CONTRIBUTE_SRC.indexOf('Please fill in your name, email, and your story.');
  const floor = CONTRIBUTE_SRC.indexOf('feature.length < FIELD_FLOORS.feature');
  const emailFormat = CONTRIBUTE_SRC.indexOf('!EMAIL_RE.test(email)');

  assert.ok(presence > -1 && floor > -1 && emailFormat > -1, 'all three checks must be present');
  assert.ok(presence < floor, 'the floor must come after the presence check');
  assert.ok(floor < emailFormat, 'the floor must come before the email format check');
});

test('the server floor rejects loudly, with a structured log line and a 400', () => {
  // AP #12: the client-side block sends no request and so is uncountable. This
  // rejection is the only one that leaves a trace, which makes its log line the
  // single measurable signal that the floor is doing anything at all.
  const floorAt = CONTRIBUTE_SRC.indexOf('feature.length < FIELD_FLOORS.feature');
  const block = CONTRIBUTE_SRC.slice(floorAt, floorAt + 600);
  assert.match(block, /log\("validation-reject", \{ reason: "story too short", length: feature\.length \}\)/);
  assert.match(block, /textResponse\(\s*400/);
});
