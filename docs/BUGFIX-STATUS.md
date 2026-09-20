# Bug-fix checkpoint

This checkpoint is not a claim of zero bugs or approval for a physical fleet.

## Changes

- Return requests validate ride/station IDs and dock-label types before SQLite
  queries. Objects, arrays, booleans and oversized integers return JSON 400
  instead of crashing or matching integer IDs unexpectedly.
- A student reservation with a missing expiry is released on the next reservation
  cleanup. The ride remains active. Admin movement reservations are unaffected.
- Sign-out is bound to the session that initiated it. A delayed successful or
  expired-session response cannot delete a newer login or redirect it to login.
- GitHub checks cover backend regressions, mobile tests/type checking/lint/bundle
  exports, and a separate dependency-security gate. No deployment or live database
  access is part of these jobs.

## Current checkpoint — 20 September 2026

The backend and mobile jobs passed for `1b70af9` (36 backend tests). The on-device
rental/assigned-dock return/history flow was also shown in the founder’s recording.
The dependency findings described below are historical; the new dependency update
and its verification are documented in [DEPENDENCY-SECURITY.md](DEPENDENCY-SECURITY.md).
Physical dock confirmation is still simulated.

## Earlier verification and open issues

Local checks passed: three input-validation tests, nine client-session tests,
Python compilation, TypeScript, Expo lint, and Android/iOS JavaScript bundle exports (not signed installers). Full Flask integration rerun was
blocked locally because backend dependencies could not be downloaded. Two route
regressions were added for execution by GitHub checks; check the workflow outcome
before treating them as passed.

The user reported 21 npm findings (12 moderate, 9 high) after a compatible update
in their Codespace. That local lockfile has not been received or committed here;
the repository audit may therefore show a different count. No dependency fixes
or clean security audit are claimed in this commit. Do not use a forced SDK/Router
change as an untested fix. The audit job remains a failing gate while advisories
remain. Phone GPS/camera, the full on-device return flow, hosting, and real dock
hardware still need their respective acceptance checks.
