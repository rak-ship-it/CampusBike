# CampusBike Roadmap

CampusBike is a learning and demonstration project. This roadmap describes possible next steps, not promises or completed features.

## Current milestone: software MVP

- [x] Student mobile app and admin dashboard
- [x] Flask API with SQLite storage
- [x] Bike rental and return flows for the software demo
- [x] Station and numbered dock management
- [x] Maintenance reporting and fleet visibility
- [x] Setup, operations, handover, and release notes
- [ ] Capture real screenshots from a working run and add them to the README
- [ ] Complete a fresh-install walkthrough and record the test results

## Next: reliability and usability

- [ ] Test the complete student journey on a clean development setup
- [ ] Review empty states, loading states, network errors, and expired sessions
- [ ] Review mobile layout and accessibility on different screen sizes
- [ ] Make the demo setup and sample data easier for a new contributor to understand
- [ ] Keep setup instructions aligned with the current code and dependencies

## Later: physical prototype

These items require hardware and real-world testing; they are not part of the current software MVP.

- [ ] Define a safe, low-cost physical docking prototype
- [ ] Evaluate a lock/actuator and a way to confirm its actual state
- [ ] Test reliable bike and dock identification
- [ ] Compare physical sensor results with server-side rental/return records
- [ ] Document failure cases and a manual recovery procedure

## Before any real campus pilot

- [ ] Review authentication, authorization, secrets, data retention, and backups
- [ ] Test location checks in realistic conditions; GPS alone is not proof of physical docking
- [ ] Run security and reliability checks with a disposable test database
- [ ] Get campus/operator approval and define a support and maintenance process
- [ ] Do not use this demonstration MVP to manage real bikes until the necessary safety, security, and operational work is complete

## How to help

Small, focused contributions are easiest to review. See [CONTRIBUTING.md](../CONTRIBUTING.md) for the suggested workflow. If you find a bug, open an issue with the steps to reproduce it.
