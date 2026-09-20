#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
"${PYTHON:-python3}" -m unittest discover -s campusbike_v2/tests -v
cd CampusBikeMobile
npm test
./node_modules/.bin/tsc --noEmit
npm run lint
