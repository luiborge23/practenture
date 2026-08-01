# Practenture Android

Thin Kotlin/Jetpack Compose client for the FastAPI backend. Online simulation formulas live only in the backend.

## Requirements
- JDK 17+
- Android SDK 35

## Verify
```bash
./gradlew testDebugUnitTest assembleDebug
```

The debug and production clients use the canonical backend origin `https://practenture.com/`. Cleartext traffic is disabled.

Password/session contracts are covered by JVM tests. Google authentication still uses the legacy Android API and must be migrated to Credential Manager and device-validated before distribution.
