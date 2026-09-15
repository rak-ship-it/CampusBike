# Software MVP release 1.0.0 — 2026-09-15

This is a reproducible software handover checkpoint. It does not assert complete
physical-fleet readiness or real-device acceptance.

## Changes since 4944175

- Dedicated, transactional exact-return module; removed legacy mobile fallback.
- Ride ID bound to reservation/cancellation/confirmation; repeat confirmation
  returns a stored receipt and cannot accidentally finish a later ride.
- Server checks GPS freshness, finite coordinates, accuracy, distance, optional
  campus polygon and starting-campus relationship.
- Ten-minute student reservations and lazy expiry; admin movements remain explicit.
- Account-management page, password reset/session revocation, safe disabling,
  CSV export, online backup, restore-to-new-file and consistency audit.
- Backend URL via mobile `.env`, ride timer and assignment-expiry information.
- Backend-relative configuration, unique-secret bootstrap, deployment checks,
  debug off by default, no fallback admin password, Waitress launcher.
- Legacy web rent/return writes disabled; mobile is the supported ride interface.
- Current root documentation plus preserved legacy attribution.

## Verification

The release was checked in an isolated environment with temporary databases:

- 24 backend tests: authentication, ownership, throttling, expiry, exact return,
  wrong dock, restart recovery, maintenance, cancellation, concurrent rentals,
  competing dock claims, retry protection, account controls/CSRF, backup/restore
  configuration guard and admin login throttling.
- Four mocked client session tests: authorization header, secure-storage calls,
  401 handling, logout and web-memory storage.
- TypeScript `--noEmit` and Expo lint passed.
- A real Waitress process passed an HTTP health check with production configuration.
- Android and iOS JavaScript/Hermes bundle exports passed using a placeholder
  HTTPS backend address. These exports are not signed APK/IPA installers.

## Remaining acceptance work

Actual camera, phone GPS, native SecureStore, on-device UI and physical fleet
behavior are not confirmed by these tests. Hosting, store signing and physical
dock integration require separate environments/accounts/hardware. There is no
claim of a penetration test, load certification or full tenancy isolation.
Server-generated `Locked` values must be treated as simulated.

Authentication, PostgreSQL migration, tenant isolation, telemetry and hardware
integration can be extended by a future maintainer; see HANDOVER.md for the
precise implemented/future split. No automatic sale or publication of business
claims is part of this release.
