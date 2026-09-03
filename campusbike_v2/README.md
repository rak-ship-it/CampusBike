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
