const assert = require('node:assert/strict');
const { test } = require('node:test');
const { createRequire } = require('node:module');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const routerRequire = createRequire(require.resolve('expo-router/package.json'));
const queryPath = routerRequire.resolve('query-string');
const queryRequire = createRequire(queryPath);

test('Expo Router query parsing retains IDs, spaces, UTF-8 and repeated values', () => {
  const query = routerRequire('query-string');
  assert.deepEqual({ ...query.parse('bike=CB002&slot=SLOT-02&note=Flat+tyre&name=%E0%A4%B0%E0%A4%BE%E0%A4%AE&tag=a&tag=b') }, {
    bike: 'CB002', slot: 'SLOT-02', note: 'Flat tyre', name: 'राम', tag: ['a', 'b'],
  });
  const data = { bike: 'CB004', station: 'Spotify ClubHouse', note: 'Tyre & chain' };
  assert.deepEqual({ ...query.parse(query.stringify(data)) }, data);
});

test('the decoder default export also works after Babel transforms it for native bundling', () => {
  const { transformSync } = require('@babel/core');
  const decoderPath = queryRequire.resolve('decode-uri-component');
  const code = transformSync(fs.readFileSync(decoderPath, 'utf8'), {
    filename: decoderPath, configFile: false, babelrc: false,
    plugins: [require.resolve('@babel/plugin-transform-modules-commonjs')],
  }).code;
  const decoder = { exports: {} };
  vm.runInNewContext(code, { module: decoder, exports: decoder.exports });
  const query = { exports: {} };
  vm.runInNewContext(fs.readFileSync(queryPath, 'utf8'), {
    module: query, exports: query.exports,
    require: name => name === 'decode-uri-component' ? decoder.exports : queryRequire(name),
    URL, URLSearchParams,
  });
  assert.equal(query.exports.parse('note=Flat%20tyre').note, 'Flat tyre');
});

test('malformed query escapes terminate without hanging the calling process', () => {
  // Isolate this regression so a vulnerable decoder cannot hang the test runner.
  const source = `const q=require(${JSON.stringify(queryPath)}); const result=q.parse('note='+ '%FF'.repeat(2000)); if(typeof result.note!=='string') process.exit(1);`;
  execFileSync(process.execPath, ['-e', source], { timeout: 3000, stdio: 'pipe' });
});

test('Metro reads the app PNG assets after removing image-size', () => {
  const { getAssetSize } = require('metro/private/Assets');
  const bytes = fs.readFileSync(path.join(__dirname, '../assets/images/icon.png'));
  const size = getAssetSize('png', bytes, 'icon.png');
  assert.ok(size.width > 0 && size.height > 0);
});

test('xcode can still generate unique project identifiers with patched uuid', () => {
  const project = require('xcode').project('test.pbxproj');
  project.hash = { project: { objects: {} } };
  const first = project.generateUuid();
  assert.match(first, /^[A-F0-9]{24}$/);
  assert.notEqual(first, project.generateUuid());
});

test('PostCSS parses normal CSS without loading an unrelated absolute source map', async () => {
  const metroRequire = createRequire(require.resolve('@expo/metro-config/package.json'));
  const postcss = metroRequire('postcss');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'campusbike-css-'));
  try {
    const file = path.join(dir, 'private.map');
    fs.writeFileSync(file, JSON.stringify({ version: 3, sources: ['fixture.css'], names: [], mappings: 'AAAA', sourcesContent: ['campusbike-test-private-content'] }));
    const result = await postcss([]).process(`a { color: red }\n/*# sourceMappingURL=${file} */`, { from: undefined, map: { inline: false } });
    assert.match(result.css, /color: red/);
    assert.ok(!JSON.stringify(result.map?.toJSON()).includes('campusbike-test-private-content'));
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
