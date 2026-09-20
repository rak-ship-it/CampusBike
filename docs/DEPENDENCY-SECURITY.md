# Mobile dependency security checkpoint — 20 September 2026

The fresh audit of commit `1b70af9` reported 23 affected dependency entries
(13 moderate, 10 high). These included downstream packages that inherited a
finding from the same vulnerable dependency; they were not 23 independent
vulnerabilities in CampusBike's own code.

The updated lockfile reports **0 npm audit vulnerabilities** as of this checkpoint.
The security job still runs `npm audit --audit-level=moderate`; there are no audit
exclusions or ignored advisories. A clean package audit is not proof that the
application, deployment or physical dock has no security issues.

## Changes and why

Expo remains **54.0.37**, Expo Router **6.0.24**, React Native **0.81.5**, and React
**19.1.0**. Native SDK versions and the application's ride/report API are unchanged.

| Dependency | Resolution | Reason |
| --- | --- | --- |
| `js-yaml` | 3.15.2 / 4.3.2 in their existing major lines | Fix merge-source CPU exhaustion. |
| `@react-navigation/core` | 7.22.1 | Compatible update removes its vulnerable query-string chain. |
| Metro package family | 0.83.8, aligned through overrides | Upstream security patch replaces `image-size` with patched vendored parsers. Expo 54 otherwise pins 0.83.3. |
| `postcss` | 8.5.23 override | Addresses the reported stylesheet/source-map advisories, including the incomplete earlier fix. |
| `xcode` → `uuid` | 11.1.1 scoped override | Fixes buffer bounds handling and retains the CommonJS `v4()` API used by xcode. |
| `query-string@7.1.3` → `decode-uri-component` | 0.5.0 scoped override and one-line compatibility patch | Uses the upstream decoder fix while retaining Router 6's existing query-string API. |

### Why the query-string patch exists

The fixed decoder is an ES module. Simply overriding its version breaks the old
CommonJS consumer: it receives a module object instead of the decoding function.
`patches/query-string+7.1.3.patch` changes only that import to read `.default`.
It does not replace or modify the fixed decoding algorithm.

`npm ci` applies the patch automatically through `patch-package --error-on-fail`.
A failed patch fails installation instead of leaving a silently broken navigation
path. Keep the patch, package.json and package-lock.json together. Use the normal
install including development dependencies and scripts; `--ignore-scripts` skips
this required compatibility step. Node 22 LTS is recommended (CI uses Node 22);
the declared Node engine range supports synchronous loading of ES modules.

Remove these temporary overrides and the patch together only when a reviewed Expo
upgrade resolves the same findings upstream. Repeat the compatibility tests and
native exports; do not substitute `npm audit fix --force` for that review.

## Verification

Passed locally after a fresh `npm ci`: 15 mobile tests, TypeScript, Expo lint,
Expo dependency alignment, and Android/iOS Hermes bundle exports. The security
audit returned zero findings. GitHub runs the same checks plus the backend suite
on the committed files.

The new dependency tests exercise Router query parameters and UTF-8 decoding,
Babel-transformed decoder interoperation, malformed escape handling with a process
timeout, Metro PNG loading, xcode UUID generation, and PostCSS source-map handling.
Existing client-session tests remain included by `npm test` and GitHub checks.

Acceptance commands (from `CampusBikeMobile`):

```bash
npm ci
npm audit
npm test
npx tsc --noEmit
npm run lint
npx expo install --check
npx expo export --platform android --platform ios
```

Exports verify JavaScript/assets and Hermes compilation, not signed native
installers or a physical phone run. After installing this update, reopen the app
and check login, map/navigation, QR scan and the existing return flow on the phone.

## Upstream evidence

- [Metro 0.83.8 security release](https://github.com/react/metro/releases/tag/v0.83.8)
- [Decoder advisory and fixed release](https://github.com/advisories/GHSA-vcc3-ghjq-m6fr)
- [PostCSS incomplete-fix advisory](https://github.com/advisories/GHSA-fxqj-rqcc-2cmp)
- [UUID bounds-check advisory](https://github.com/advisories/GHSA-w5hq-g745-h8pq)
- [YAML merge-source advisory](https://github.com/advisories/GHSA-2883-xcg3-v3hh)
- [Expo SDK 54 reference](https://docs.expo.dev/versions/v54.0.0/)
