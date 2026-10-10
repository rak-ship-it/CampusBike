# Contributing to CampusBike

Thanks for taking a look at CampusBike. It is a student-built software MVP, so clear bug reports and small, understandable changes are especially helpful.

## Before you start

1. Read the [main README](README.md) for the project overview and limitations.
2. Follow the [setup guide](docs/SETUP.md).
3. Read the relevant section of the [handover notes](docs/HANDOVER.md) before changing the backend or data model.
4. Never commit real credentials, environment files, tokens, personal data, or a live database.

## Suggested workflow

1. Create a branch for one focused change.
2. Explain the problem or improvement before making a large change.
3. Keep the change as small as practical.
4. Run the checks described in the setup guide and project scripts.
5. Update documentation when behavior or setup steps change.
6. Open a pull request describing what changed, how it was tested, and any known limitations.

## Bug reports

Please include:

- What you were trying to do
- The steps needed to reproduce the issue
- What you expected to happen
- What actually happened
- Relevant error messages with passwords, tokens, and private information removed
- Device/OS or runtime details when relevant

## Development principles

- Do not claim that simulated docking proves a physical lock is closed.
- Preserve server-side validation for important rental and return actions.
- Keep authentication tokens and secrets out of logs and screenshots.
- Prefer tests that use disposable data rather than a real database.
- Be clear about what has and has not been tested.

## Scope

CampusBike is not currently a production service. Contributions should not imply that it is ready for real campus deployment without the required security, hardware, and operational validation.
