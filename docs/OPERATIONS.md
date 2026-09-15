# Operator guide

## Before a demonstration

Confirm the server is reachable at `/health`, admin login works, stations have
correct coordinates, and a bike is Available in an Occupied dock. Run the audit
command below. Use seeded accounts only for supervised tests. Keep development
login off and use the configured passwords.

## Ride and return

Scan the bike's current QR in the mobile app. My Ride shows elapsed time. To end
a ride, select a return station. The phone sends three GPS readings; the server
requires at least two recent usable readings and checks their median distance.
The limit is 100 metres plus up to 30 metres of accuracy allowance. Each usable
reading must be no older than 60 seconds and report accuracy of 100 metres or
better. If configured, a majority of usable readings must be within the campus
polygon. The return station must belong to the starting campus.

A numbered dock is reserved for ten minutes. Put the bike at that dock and use
the clearly labelled prototype confirmation. The software marks that dock
Occupied and the bike Locked/Available (or Maintenance for an unresolved report).
This does not actuate or sense a real lock. A repeated confirmation returns the
same receipt. Cancelling/expiry frees only the assignment, not the active ride.
Expiry is applied lazily on API access and admin dashboard load; no scheduler
is required. Admin rebalancing reservations do not expire this way.

If assignment expiry or a connection error occurs, refresh My Ride. Request a
new assignment if needed. Do not manually mark a ridden bike Available. If a
physical bike cannot be returned, the operator must reconcile it before resuming
service; this release has no sensor-confirmed recovery workflow.

## Accounts and maintenance

`/admin/accounts` creates accounts, sets/resets passwords and enables/disables
students. Password changes revoke sessions. Disabling an account with an active
ride is blocked so the student retains access to their return. Use the existing
maintenance dashboard to resolve reports after checking the bike. Rebalancing
reserves a destination dock and requires explicit completion or cancellation.
The admin's CSV export contains ride records; handle it as private operational
data, not promotional material.

## Backup, restore and audit

From the repository root, with backend dependencies installed:

```bash
python3 campusbike_v2/manage.py audit
python3 campusbike_v2/manage.py backup /secure/location/campusbike-2026-09-15.db
```

Use a new filename each time. Backup uses SQLite's online backup API and refuses
to overwrite files. Restrict access: a backup contains student records, password
hashes, session hashes and QR secrets. Code archives intentionally exclude it.

Restore to a **new** destination, with the service stopped:

```bash
python3 campusbike_v2/manage.py restore /secure/location/snapshot.db /secure/location/restored.db
```

The source is checked for SQLite integrity, existing destinations are refused,
and mobile sessions in the restored copy are revoked. Set `CAMPUSBIKE_DB_PATH`
to the new file, start the backend, run audit, and verify fleet positions. A
snapshot may be older than physical movements—reconcile the fleet before use.
Retain the previous database until the restore has been accepted.

Audit reports inconsistent occupied docks, active ride/bike ownership and
duplicate active rides. It does not automatically change records or prove the
physical fleet matches the database.

## Pause the project

1. Finish/reconcile all active rides and admin movements.
2. Create and verify a private backup; retain your `.env` separately.
3. Save the source release and record the Git commit you used.
4. Stop both servers and remove any public demo access.
5. On resumption, restore/configure, run tests and audit, and test a real phone.

Do not send passwords, live databases or QR secrets to prospective buyers as a
demo. Use a fresh seeded database with separately provisioned test passwords.

Admin login is limited to ten POST attempts per source address per 15-minute
window. A reverse proxy may make addresses shared; configure a gateway rate
limit deliberately rather than trusting arbitrary forwarded-IP headers.

## Student password changes

Students who know their password can use Profile → Change password. This signs
out all their devices without deleting history or ending an active ride. Forgotten
passwords still require the administrator's identity-verification/reset process.
A timeout does not prove a write failed: refresh My Ride after an uncertain return;
try the new password at login after an uncertain password change.
