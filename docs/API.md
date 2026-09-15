# Mobile API contract — MVP 1.0.0

Base URL is `EXPO_PUBLIC_API_BASE_URL`. All routes below use `/api`.
JSON writes require `Content-Type: application/json`. Authenticated routes
require `Authorization: Bearer <access_token>`. Never put tokens in query strings.

| Route | Purpose |
|---|---|
| GET `/health` | Public liveness |
| GET `/auth/config` | Public development-login availability |
| POST `/login` | `student_id`, `password`; returns student, token and expiry |
| POST `/dev-login` | Explicit test-mode-only login for seeded accounts |
| GET `/me` | Verified current student |
| POST `/logout` | Revoke current token |
| GET `/campuses`, `/stations` | Active station/campus metadata |
| POST `/bike-by-qr` | Identify bike from `qr_token` |
| POST `/rent` | Start ride using `bike_id`, `qr_token` |
| GET `/students/{id}/active-ride` | Current ride plus pending dock/expiry |
| POST `/reserve-return-slot` | Exact-dock reservation, schema below |
| POST `/cancel-return-slot` | Cancel assignment for `ride_id` |
| POST `/end-ride` | Confirm assigned dock for a specific ride |
| GET `/students/{id}/rides` | Completed personal history |
| POST `/maintenance-reports` | `bike_id`, `issue_type`, optional description/severity |

Student IDs supplied in paths or JSON must match the authenticated account;
write handlers derive identity from the session. Campus-boundary metadata at
`GET /api/campus-boundary` is a separate public Flask route.

## Reservation

```json
{
  "ride_id": 42,
  "station_id": 2,
  "location_samples": [
    {"latitude": 18.65, "longitude": 73.77, "accuracy": 5, "timestamp": 0},
    {"latitude": 18.65, "longitude": 73.77, "accuracy": 6, "timestamp": 0},
    {"latitude": 18.65, "longitude": 73.77, "accuracy": 5, "timestamp": 0}
  ]
}
```

The coordinates above are illustrative, not deployment settings. Replace each
zero timestamp with that GPS reading's Unix timestamp in milliseconds; zero is
intentionally rejected. The server accepts 3–6 readings with at least two usable
samples. `accuracy` is metres. A reservation response includes `ride_id`,
`bike_id`, `station_id`, public `station`, numbered `slot`, and `expires_at`
(Unix seconds). Retrying an existing live assignment returns that assignment
without extending it. To select another station, cancel first.

## Confirmation

```json
{"ride_id": 42, "station_id": 2, "slot_number": "SLOT-02"}
```

These IDs must refer to the authenticated student's active assignment. No free
slot fallback is allowed. Success contains `return`, including the exact dock,
bike status, lock status, timestamp and `confirmation: "simulated"`. A repeated
matching confirmation returns the stored result. Reusing a receipt with another
dock is rejected. A retry for an old ride cannot complete a newer ride.

401 means sign in again; 403 means identity/location is not permitted; 409 means
state changed (refresh My Ride); 429 means login throttling. Invalid GPS or JSON
can return 400. Network failures should not be interpreted as proof a write
failed—refresh/read the ride state or retry the same ride-specific request.

Timestamps in ride history are legacy IST strings; token/lease expiries use Unix
seconds. GPS timestamps use Unix milliseconds. Keep these units distinct.
