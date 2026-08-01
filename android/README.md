# Practenture Android

Thin Kotlin/Jetpack Compose client for the FastAPI backend. Online simulation formulas live only in the backend.

## Requirements
- JDK 17+
- Android SDK 35

## Verify
```bash
ANDROID_HOME="$HOME/Library/Android/sdk" \
ANDROID_SDK_ROOT="$HOME/Library/Android/sdk" \
./gradlew --no-daemon --warning-mode=fail clean testDebugUnitTest assembleDebug
```

The debug and production clients use the canonical backend origin `https://practenture.com/`. Cleartext traffic is disabled.

Password/session contracts are covered by JVM tests. Google authentication uses
Credential Manager and requires the Web OAuth client ID through the
`PRACTENTURE_GOOGLE_SERVER_CLIENT_ID` Gradle property or environment variable.
The client ID must match the backend's configured Google audience. Complete
physical-device Google authentication validation before distribution.
