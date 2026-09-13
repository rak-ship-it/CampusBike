# CampusBike V2

This rebuild changes the student experience to a station-first, authenticated, QR-verified rental flow.

## Student flow

1. Sign in with Google.
2. Select a station.
3. Select an available bike at that station.
4. Tap **Rent · Scan bike QR**.
5. Browser opens the camera and scans the QR attached to that exact bike.
6. Server verifies the QR and starts the ride.
7. To end the ride, choose a return station. CampusBike assigns the first free slot automatically.

## Admin flow

- `/admin/login` – admin login
- `/admin` – fleet, students, rides, stations and slots
- `/admin/qr` – printable unique QR labels for the five bikes

## What this migration preserves

`database.py` migrates the existing `campusbike.db`; it does **not** delete ride history. It keeps CB001-CB005 and places available bikes at five different active stations:

- CB001 → Main Gate
- CB002 → Library
- CB003 → Hostel
- CB004 → Canteen
- CB005 → Mechanical Block

If a bike is currently in an active ride, the migration does not forcibly park it.

## 1. Install

```bash
pip install -r requirements.txt
cp .env.example .env
python3 database.py
python3 app.py
```

## 2. Google sign-in setup

Create a Google Cloud OAuth client of type **Web application**. Add your live callback URL as an authorized redirect URI:

```text
https://YOUR-CODESPACE-5000.APP.GITHUB.DEV/auth/google/callback
```

The redirect URI must exactly match the address the browser uses, including `https` and the full callback path.

Put the credentials in `.env`:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

During your own testing, leave `ALLOWED_EMAIL_DOMAINS` blank to allow any verified Google account. For a college deployment, restrict it:

```env
ALLOWED_EMAIL_DOMAINS=college.edu
```

If the college uses Microsoft 365 instead of Google Workspace, add Microsoft/Entra sign-in as a second identity provider rather than accepting an unverified typed email address.

## 3. Security settings before deployment

Change these in `.env`:

```env
SECRET_KEY=a-long-random-secret
ADMIN_USERNAME=your-admin-user
ADMIN_PASSWORD=a-strong-password
SESSION_COOKIE_SECURE=1
```

Never commit `.env` to GitHub.

## 4. QR labels

After admin login, open `/admin/qr` and print the labels. The QR contains a per-bike secret, not only `CB001`, so the server can verify that the scanned code belongs to the bike the student selected.

## 5. Camera requirement

Camera access requires HTTPS (or localhost) and browser permission. GitHub Codespaces forwarded sites use HTTPS. Test QR scanning from a phone for the real flow.

## Production note

This is a production-style web architecture, but a real physical dock/lock requires a separate hardware controller/API. The current `lock_status` is software state only. Before a real campus launch, move from SQLite to PostgreSQL, add deployment monitoring/backups, rotate QR secrets when needed, and integrate the physical lock controller.

## Mobile exact-dock return and automated checks

The Expo app now reserves a numbered dock after its phone GPS check. The
ride remains active until the prototype confirmation button completes the
return. Refreshing the app or restarting Flask preserves the reservation.
Cancelling the assignment frees the dock without ending the ride. Admin
rebalancing reservations also survive restarts; completion/cancellation stays
an explicit admin action.

Run the backend regression suite from the repository root:

```bash
python -m pip install -r campusbike_v2/requirements.txt
python -m unittest discover -s campusbike_v2/tests -v
```

Tests use disposable databases, including during Flask import. They cover
first-boot setup, exact returns/history, restart recovery, cancellation,
full/inactive stations, maintenance returns, simultaneous rentals for one
student, and admin rebalancing completion/cancellation after restart.

Mobile checks (inside `CampusBikeMobile`): `npm ci`, `npx tsc --noEmit`,
`npm run lint`, and `npx expo export --platform android`.
An export verifies bundling, not real device operation. Camera permissions,
phone GPS and physical locking still need device/hardware validation.

Known prototype limits: GPS is checked by the app, not the API; the legacy
return API still supports authenticated callers without prior reservations.
Reservations do not expire automatically. Resolve these lifecycle/location
rules and deployment security before a real pilot.

## Mobile authentication

The mobile app uses a student ID and an administrator-provisioned password.
Google web login remains separate; Google login is not yet wired into the mobile
app. No passwords are seeded or committed. Old clients without a session token
receive 401; update the backend and app together.

After pulling, install backend requirements and run the backend as usual
(startup creates the auth tables). Run `npm ci` inside `CampusBikeMobile` and
restart Expo to install the new SecureStore dependency.

To set/reset a password for an existing active student, run inside `campusbike_v2`:

```bash
python set_mobile_password.py STU001
```

Enter a unique password of 12–128 characters at the hidden prompts. The password
is hashed with Werkzeug's default scrypt. Setting it revokes existing mobile
sessions for that student. Reset is currently an administrator operation, not
self-service. Never put passwords in command arguments, Git, or chat. Provision
accounts only after verifying who the student is.

Sessions are random bearer tokens lasting 24 hours. SQLite stores only SHA-256
token hashes. Native apps store tokens in Expo SecureStore; web previews keep
them in memory only. Logout revokes the server session before clearing local
state; offline logout asks the user to retry. Expiry returns the app to login,
without deleting an active ride. Re-login recovers the ride. Disabled accounts
and password resets also invalidate access. Five failed attempts per account
within 15 minutes trigger a temporary login throttle. Add gateway/IP rate
limiting for deployment.

All mobile blueprint routes except health/login/config require a session.
Supplied student IDs must match the session; write handlers use session identity.
Public campus-boundary metadata remains public. Admin uses its separate Flask
session.

Development login is **off by default**. For isolated testing only, set
`CAMPUSBIKE_DEV_LOGIN=1` in the backend `.env`. The app then offers a labelled
button for seeded STU001–STU005 accounts. This deliberately skips passwords;
keep it off for a real pilot. Turning it off also rejects existing dev tokens.

Before deployment, configure HTTPS, a strong Flask SECRET_KEY and admin password,
secure web cookies, and disable Flask debug mode. This mobile session change
does not automatically harden those separate deployment settings.

Run client auth tests inside `CampusBikeMobile`:

```bash
node --test tests/api.test.cjs
```

These mock native storage and network responses. Device SecureStore operation,
camera permissions and GPS still need later on-device testing.
