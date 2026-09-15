# CampusBike handover

## What this release is

A source-code software MVP for a controlled-campus bicycle-sharing demonstration.
It includes a native Expo application, a Flask administrator application and
SQLite storage. It can be paused, reproduced and evaluated by another developer.
It is not evidence of a deployed business, revenue, active customers, working
physical locks, or a signed/store-published app.

## Architecture

- `database.py`: legacy-compatible initialization/seeding and schema additions.
- `settings.py`: backend-relative environment loading and deployment checks.
- `mobile_auth.py`: password verification, throttling and revocable bearer sessions.
- `mobile_api.py`: station/bike lookup, QR rental, personal history and reports.
- `ride_returns.py`: GPS validation, ride-bound leases and atomic return receipts.
- `app.py`: admin, maintenance, station configuration, rebalancing and legacy web views.
- `operator_routes.py`: student administration and CSV export.
- `manage.py`: backup/restore and invariant audit.
- `CampusBikeMobile/services/api.ts`: authenticated requests and token storage.
- `CampusBikeMobile/app/`: login, map, scanner, My Ride, history, help and profile.

Passwords use Werkzeug scrypt hashing. Tokens are random, expire after 24 hours,
and are stored hashed server-side and in native SecureStore client-side. Student
identity is checked server-side. Admin login uses its own Flask cookie session.
Database writes for rentals/returns/rebalancing use transactions. Schema retains
some legacy station text alongside permanent station IDs; replacing this with
formal migrations is a future engineering task, not hidden completed work.

## Implemented versus future

| Capability | Release status |
|---|---|
| Mobile password login / admin account tools | Implemented and automatically tested |
| QR rent / exact dock return / personal history | Implemented; backend flow tested |
| GPS validation on server / campus polygon | Implemented using phone-supplied readings |
| Reservation expiry, restart recovery, retry receipt | Implemented and tested |
| Ride timer | Implemented; not a billing meter |
| Maintenance / stations / naming rights / rebalancing | Implemented software workflows |
| Backup/restore / audit / CSV export | Implemented operator tools |
| Lock status | Software simulation only |
| Physical docking / bike identity sensor / LED control | Not built |
| Background bike GPS / journey-distance tracking | Not built |
| Full tenant isolation / PostgreSQL migration | Not built |
| Mobile Google sign-in / self-service password reset | Not built |
| Hosted service / APK or IPA signing / app-store release | Not delivered |
| Payments / sponsor billing / commercial analytics | Not built |

A server-side distance check is more consistent than client-only checks but is
not tamper-proof GPS evidence. A future dock controller must authenticate itself,
identify the actual bike and lock state, and deliver replay-safe events before
software return confirmation can represent a physical return. No hardware
controller credentials or hardware API are included here.

## Evaluation script

Use a fresh database. Provision one admin and STU001. Configure two real test
station locations and display a seeded bike's QR. Log in on a real phone, rent,
request an exact dock, confirm the simulated return and check history/admin.
Repeat cancellation, expired assignment and restart recovery. Validate physical
camera/location/secure-storage behavior on both intended phone platforms before
any field pilot. Automated tests do not replace this acceptance step.

## Source provenance and transfer boundaries

The original root README credits Jhoan Landazabal and Valentina Rivera for an
older Spanish-language database project. It is preserved with attribution in
`docs/legacy-database-project.md`. Root SQL exercises, `CasosDeUso/` and `IMG/`
are legacy material and are not needed by the current runtime. Old patch helper
scripts are historical only. Do not erase their provenance or describe all
repository history as independently authored CampusBike code.

Third-party packages and starter assets retain their own terms. This work has
not established ownership, exclusivity, trademark availability, or transfer
rights. No new project license or sale contract is granted by this release.
Resolve what can be transferred before representing a sale as ready to close.

A technical handover should supply: the agreed source commit, these docs, test
results, a clean demo dataset, dependency manifests, and an agreed list of assets.
Transfer operational credentials separately only if needed; rotate them and
exclude private student records from evaluation copies. Price, buyer commitments
and any business valuation have not been assessed.
