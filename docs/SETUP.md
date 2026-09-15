# Install or upgrade CampusBike MVP 1.0.0

Supported development baseline: Python 3.12, Node 22, npm, Expo SDK 54.
Native operation is the supported mobile target. Browser preview is not a
substitute for native maps, camera, location or secure storage.

## Fresh installation

From the repository root, in the backend terminal:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r campusbike_v2/requirements-lock.txt
.venv/bin/python campusbike_v2/bootstrap.py
.venv/bin/python campusbike_v2/set_mobile_password.py STU001
.venv/bin/python campusbike_v2/run_server.py
```

Windows uses `.venv\Scripts\python.exe` instead of `.venv/bin/python`.
Bootstrap asks privately for a new admin password and creates a random session
secret. It refuses to overwrite an existing `.env`. Student password setup asks
for a separate password, creates/migrates the database and seeds five test bikes,
five stations and STU001–STU005. No password is supplied in source control.

Open the backend's `/admin/login`, sign in as `admin`, and:

1. Give return stations their real latitude and longitude.
2. Draw the campus boundary if a service-area check is desired.
3. Use **Manage student accounts** to add students or set their passwords.
4. Use the QR page to display/print the current bike codes.

Do not fabricate a campus location to present a demo as a real operating service.

## Mobile terminal

Create `CampusBikeMobile/.env` using `.env.example`:

```dotenv
EXPO_PUBLIC_API_BASE_URL=https://YOUR-BACKEND-HOST
```

This is a public URL, not a credential. In Codespaces, use the forwarded **5000**
port URL. The phone must be able to reach it. Codespaces access controls may
require making that port reachable; do not expose a backend with weak admin
credentials or development login enabled. Bootstrap fills this URL automatically
when `CODESPACE_NAME` is available and the mobile `.env` does not exist.

Then use a second terminal:

```bash
cd CampusBikeMobile
npm ci
npx expo start --tunnel --clear
```

Use a compatible Expo Go/development build. Sign in as STU001 with the password
you set. Keep both processes running. Configure precise foreground location and
camera permissions when prompted. No additional terminal is required.

## Upgrade an existing Codespace

First stop Flask/Waitress and Expo with Ctrl+C. Preserve local untracked files;
never run `git clean` or overwrite your database to install this release.

Before migrating, create a dated backup using the previous release's backup
procedure, or stop the backend and copy `campusbike_v2/campusbike.db` to a secure
location. The repository does not contain your live database.

From the root:

```bash
git pull --ff-only origin main
python3 -m pip install -r campusbike_v2/requirements-lock.txt
```

Review `campusbike_v2/.env.example` and retain your actual `.env` values. Set a
strong admin password and persistent random SECRET_KEY. Debug and development
login should be off. Create the mobile `.env` as above; the old hard-coded
Codespace URL has been removed. Existing student passwords and ride history are
preserved. Existing student dock assignments get a ten-minute upgrade grace
period. Update backend and mobile together: old return clients lack the new
ride ID and GPS sample payload.

Run `python3 campusbike_v2/run_server.py`, then `npm ci` and restart Expo in the
mobile terminal. If an old version is still cached, use `--clear` and reopen it.

## Hosting

Use `run_server.py` (Waitress), one application process with persistent SQLite
storage, behind an HTTPS reverse proxy. Do not put the database on ephemeral
container storage or share the same SQLite file among independent replicas.
Set `CAMPUSBIKE_DB_PATH` to an absolute path if needed. The directory must exist
and be writable by the service account. Keep backups outside the repository.

Set `CAMPUSBIKE_ENV=production`, `SESSION_COOKIE_SECURE=1`, `FLASK_DEBUG=0`,
`CAMPUSBIKE_DEV_LOGIN=0`, a random SECRET_KEY (32+ characters), and a unique admin
password (12+ characters). Production startup rejects missing/weak settings.
Do not rely on the mode name as a claim of physical-fleet readiness.

A domain, server, TLS configuration and uptime monitoring are not provisioned by
this source release. Native APK/IPA signing, developer accounts, app identifiers,
Android map-provider configuration and store review are also separate work.
`expo export` builds JavaScript/assets; it does not create an installable APK/IPA.
