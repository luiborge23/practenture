# Practenture Android

Thin Kotlin/Jetpack Compose client for the FastAPI backend. Online simulation formulas live only in the backend.

## Requirements
- JDK 17+
- Android SDK 35

## Verify
```bash
./gradlew testDebugUnitTest assembleDebug
```

The default debug backend is `http://18.215.180.58/`. Production should use HTTPS and disable cleartext traffic.
