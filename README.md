# Practenture

## Prerequisites

- Xcode 26.5 with the iOS 26.5 runtime
- Apple Developer account ($99/yr)
- A concrete iPhone simulator destination; a connected device is optional for production integration checks

## Quick Start

1. Open `Practenture.xcodeproj` in Xcode
2. Select `Practenture` scheme and simulator target
3. Build: ⌘+B

## Backend Configuration

The app reads backend URL from `Info.plist`:

```xml
<key>PRACTENTURE_BACKEND_URL</key>
<string>https://practenture.com</string>
```

Debug and Release xcconfig files currently publish the same canonical HTTPS origin. Do not add raw-IP HTTP or ATS exceptions for production.

## Running Tests

CI and local qualification use the pinned iPhone 17 Pro simulator on iOS 26.5. Production integration checks may additionally use a connected physical device.

```bash
xcodebuild -project Practenture.xcodeproj \
  -scheme Practenture \
  -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=26.5' \
  test
```

## API Contract

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login (professor/student) |
| `/api/sessions` | GET | List sessions |
| `/api/sessions/{code}` | GET | Get session details |

## Common Issues

### "Cannot test target on Any iOS Simulator Device"
- Select a concrete simulator such as iPhone 17 Pro on iOS 26.5 rather than the generic simulator destination.

### "Failed to resolve package dependencies"
- Resolve package versions in Xcode, then retry with a fresh project-specific `-derivedDataPath`.
