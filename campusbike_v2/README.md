# CampusBike backend

Supported backend for software MVP 1.0.0. See the root documentation:

- [Setup and upgrades](../docs/SETUP.md)
- [Operator guide](../docs/OPERATIONS.md)
- [API contract](../docs/API.md)
- [Handover](../docs/HANDOVER.md)
- [Verified release scope](../docs/RELEASE.md)

Start with `python run_server.py` after installing `requirements-lock.txt` and
configuring `.env`. `app.py` is also available for development, with debug off
unless explicitly requested. Database paths are resolved relative to the backend
unless `CAMPUSBIKE_DB_PATH` is absolute.

Main operator pages: `/admin/login`, `/admin`, `/admin/accounts`, `/admin/qr`.
Google web views are legacy/read-only for ride actions; the mobile app is the
supported rental/return client. Mobile login uses an administrator-provisioned
password, not a Google token. Read the setup guide before exposing a server.

The physical dock is simulated. Keep `CAMPUSBIKE_SIMULATED_DOCKS=1` for a software
demonstration; setting it to 0 blocks manual returns and does not activate an
unimplemented hardware adapter.
