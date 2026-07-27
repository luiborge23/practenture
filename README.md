# Practenture iOS App Setup

## Prerequisites

- Xcode 15.4+ (with iOS 17.4 SDK)
- Apple Developer account ($99/yr)
- Physical device for testing (XCTest requires concrete device)

## Quick Start

1. Open `Practenture.xcodeproj` in Xcode
2. Select `Practenture` scheme and simulator target
3. Build: ⌘+B

## Backend Configuration

The app reads backend URL from `Info.plist`:

```xml
<key>PRACTENTURE_BACKEND_URL</key>
<string>https://api.practenture.com</string>
```

For local development, ensure backend is running on port 8000:

```bash
cd /Users/luisborges/2026/Practenture-ios/Practenture/backend
./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Running Tests

Tests require a physical device:

```bash
xcodebuild -project Practenture.xcodeproj \
  -scheme Practenture \
  -configuration Debug \
  -sdk iphonesimulator \
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
- XCTest requires physical device. Connect iPhone/iPad and select as target.

### "Failed to resolve package dependencies"
- Clean derived data: `rm -rf ~/Library/Developer/Xcode/DerivedData/*`
