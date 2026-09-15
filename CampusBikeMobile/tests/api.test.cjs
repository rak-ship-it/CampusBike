// Run: node --test tests/api.test.cjs (no native device needed).
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../services/api.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;

function setup(platform = 'android', fetchMock) {
  const storage = new Map();
  const redirects = [];
  const calls = [];
  let status = 200;
  const modules = {
    '@react-native-async-storage/async-storage': { default: {
      removeItem: async key => storage.delete(key)
    } },
    'expo-secure-store': {
      getItemAsync: async key => storage.get(key) || null,
      setItemAsync: async (key, value) => storage.set(key, value),
      deleteItemAsync: async key => storage.delete(key)
    },
    'react-native': { Platform: { OS: platform } },
    'expo-router': { router: { replace: route => redirects.push(route) } }
  };
  const context = {
    exports: {}, Headers, Error, AbortController, setTimeout, clearTimeout, process: { env: { EXPO_PUBLIC_API_BASE_URL: 'https://campusbike.example' } },
    require: name => { assert.ok(modules[name], name); return modules[name]; },
    fetch: async (url, options) => {
      calls.push({ url, options });
      if (fetchMock) return fetchMock(url, options);
      return { status, ok: status >= 200 && status < 300 };
    }
  };
  vm.runInNewContext(compiled, context);
  return { api: context.exports, storage, calls, redirects, setStatus: value => { status = value; } };
}

test('native token uses secure storage and accompanies API requests', async () => {
  const { api, calls, storage } = setup();
  await api.saveToken('test-token');
  await api.apiFetch(api.API_BASE_URL + '/api/end-ride', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  assert.equal(storage.get('campusbike_access_token'), 'test-token');
  assert.equal(calls[0].options.headers.get('Authorization'), 'Bearer test-token');
  assert.equal(calls[0].options.headers.get('Content-Type'), 'application/json');
  assert.equal(calls[0].options.body, '{}');
  await assert.rejects(api.apiFetch('https://another-server.example/api/me'));
  assert.equal(calls.length, 1);
});

test('expired session clears cached identity and redirects to login', async () => {
  const { api, storage, setStatus, redirects } = setup();
  await api.saveToken('expired');
  storage.set('campusbike_student', '{}');
  setStatus(401);
  await api.apiFetch(api.API_BASE_URL + '/api/me');
  assert.equal(await api.getToken(), null);
  assert.equal(storage.has('campusbike_student'), false);
  assert.deepEqual(redirects, ['/']);
});

test('logout revokes server session before deleting local credentials', async () => {
  const { api, setStatus, calls } = setup();
  await api.saveToken('valid');
  setStatus(500);
  await assert.rejects(api.logoutSession());
  assert.equal(await api.getToken(), 'valid');
  setStatus(200);
  await api.logoutSession();
  assert.equal(calls.at(-1).url, api.API_BASE_URL + '/api/logout');
  assert.equal(calls.at(-1).options.method, 'POST');
  assert.equal(await api.getToken(), null);
});

test('web preview credentials stay in memory', async () => {
  const { api, storage } = setup('web');
  await api.saveToken('web-token');
  assert.equal(await api.getToken(), 'web-token');
  assert.equal(storage.size, 0);
  await api.clearSession();
  assert.equal(await api.getToken(), null);
});

function pendingFetch(url, options) {
  return new Promise((resolve, reject) => {
    if (options.signal.aborted) return reject(new Error('aborted'));
    options.signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
  });
}

test('timeout aborts a stalled write without retries or deleting credentials', async () => {
  const { api, calls } = setup('android', pendingFetch);
  await api.saveToken('valid');
  await assert.rejects(api.fetchWithTimeout(api.API_BASE_URL + '/api/end-ride', { method: 'POST' }, 10), /aborted/);
  assert.equal(calls.length, 1);
  assert.equal(await api.getToken(), 'valid');
});

test('caller cancellation is forwarded to the request', async () => {
  const { api, calls } = setup('android', pendingFetch);
  const controller = new AbortController();
  const result = api.fetchWithTimeout(api.API_BASE_URL + '/api/me', { signal: controller.signal });
  controller.abort();
  await assert.rejects(result, /aborted/);
  assert.equal(calls[0].options.signal.aborted, true);
});
