# CampusBike native mobile app

Software MVP 1.0.0, Expo SDK 54 / React Native 0.81.

Follow [setup](../docs/SETUP.md) first. Create `.env` from `.env.example` with your
public HTTPS backend URL. Then:

```bash
npm ci
npx expo start --tunnel --clear
```

Use an existing administrator-provisioned student ID and password. Native session
tokens use Expo SecureStore. Map, scanner, My Ride, History, Help and Profile are
the supported flows. My Ride displays elapsed time and a ten-minute numbered
dock assignment. A software confirmation button simulates a physical return.

Checks:

```bash
node --test tests/api.test.cjs
npx tsc --noEmit
npm run lint
npx expo export --platform android --platform ios
```

Exports are JavaScript/assets, not signed APK/IPA files. On-device camera/GPS,
secure storage and UI acceptance remain separate. Native builds require owner
accounts, identifiers/signing and platform-specific map configuration. Browser
preview is not the supported production map client.

Do not run the old `reset-project` helper to install or upgrade CampusBike.
