// Run separately: this starts Expo with watching enabled (CI normally disables it).
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const fs = require('node:fs/promises');
const net = require('node:net');
const path = require('node:path');
const { setTimeout: delay } = require('node:timers/promises');

async function main() {
  const root = path.resolve(__dirname, '..');
  const route = `metro-smoke-${require('node:crypto').randomUUID()}`;
  const fixture = path.join(root, 'app', `${route}.tsx`);
  const types = path.join(root, '.expo/types/router.d.ts');
  const socket = net.createServer();
  socket.listen(0, '127.0.0.1');
  await once(socket, 'listening');
  const port = socket.address().port;
  await new Promise(resolve => socket.close(resolve));
  const env = { ...process.env, DEBUG: 'expo:typed-routes,expo:start:server:metro:metroWatchTypeScriptFiles', EXPO_OFFLINE: '1', EXPO_NO_TELEMETRY: '1',
    EXPO_PUBLIC_API_BASE_URL: 'https://campusbike.example' };
  delete env.CI;
  const child = spawn(process.execPath,
    [require.resolve('expo/bin/cli'), 'start', '--localhost', '--port', String(port)],
    { cwd: root, env, detached: process.platform !== 'win32', stdio: ['ignore', 'pipe', 'pipe'] });
  let logs = '';
  child.stdout.on('data', data => { logs += data; });
  child.stderr.on('data', data => { logs += data; });
  const closed = once(child, 'close');
  const base = `http://127.0.0.1:${port}`;
  async function until(check, label, timeout = 90000) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      if (child.exitCode !== null || child.signalCode !== null) throw Error(`Expo exited during ${label}\n${logs}`);
      try { if (await check()) { console.log(`PASS: ${label}`); return; } } catch (error) {
        if (error.message.startsWith('Expo exited')) throw error;
      }
      await delay(300);
    }
    throw Error(`Timed out: ${label}\n${logs}`);
  }
  async function hasRoute() {
    return (await fs.readFile(types, 'utf8')).includes(`/${route}`);
  }
  async function bundleContains(marker) {
    const response = await fetch(`${base}/app/${route}.bundle?platform=android&dev=true&minify=false`,
      { signal: AbortSignal.timeout(60000) });
    return response.ok && (await response.text()).includes(marker);
  }
  try {
    await until(async () => (await fetch(`${base}/status`, { signal: AbortSignal.timeout(1500) })).ok, 'server ready');
    await until(() => logs.includes('Logs for your project'), 'watchers ready');
    await delay(1500);
    await fs.writeFile(fixture, 'export default function Probe() { return "METRO_FIRST_VALUE"; }\n', { flag: 'wx' });
    await until(hasRoute, 'added route observed by Expo');
    await until(() => bundleContains('METRO_FIRST_VALUE'), 'initial development bundle');
    await fs.writeFile(fixture, 'export default function Probe() { return "METRO_UPDATED_VALUE"; }\n');
    await until(() => bundleContains('METRO_UPDATED_VALUE'), 'edited development bundle invalidated');
    await fs.unlink(fixture);
    await until(async () => !(await hasRoute()), 'deleted route removed from Expo types');
    await delay(1200);
    assert.equal(child.exitCode, null, logs);
    assert.equal(child.signalCode, null, logs);
    assert.doesNotMatch(logs, /TypeError:.*not iterable/);
    console.log('PASS: live Expo server survived file add/edit/delete; route types and development bundle updated.');
  } finally {
    await fs.rm(fixture, { force: true });
    if (child.exitCode === null && child.signalCode === null) {
      if (process.platform === 'win32') child.kill('SIGTERM');
      else process.kill(-child.pid, 'SIGTERM');
    }
    await closed;
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
