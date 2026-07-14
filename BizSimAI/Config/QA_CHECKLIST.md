# BizSimAI iOS — App Store QA Checklist

## Pre-Submission Verification

### Build & Archive
- [ ] Clean build succeeds (Product > Clean Build Folder, then Build)
- [ ] Archive succeeds without warnings
- [ ] No memory leaks in Instruments (Leaks template)
- [ ] App launches within 3 seconds on iPhone 15 Pro Simulator

### Authentication
- [ ] Professor login works with valid credentials
- [ ] Student login works with valid credentials  
- [ ] Student registration creates account and joins session
- [ ] Apple Sign-In flow completes successfully
- [ ] Google Sign-In flow completes successfully
- [ ] Invalid credentials show error message
- [ ] Token refresh works when access token expires
- [ ] Logout clears keychain and resets state
- [ ] Session expiry redirects to login

### Session Management
- [ ] Create session as professor
- [ ] Join session with code as student
- [ ] Session status updates in real-time via WebSocket
- [ ] End session as professor
- [ ] Delete session as professor
- [ ] Session list refreshes on pull-down

### Decision Submission
- [ ] Submit decisions for current round
- [ ] Decision validation prevents over-budget submissions
- [ ] Offline decisions are queued and synced on reconnect
- [ ] Haptic feedback on submission success/failure
- [ ] Sync banner shows correct status

### Results & Leaderboard
- [ ] Round results display correctly after processing
- [ ] Leaderboard sorts by cumulative investor score
- [ ] PDF export generates valid multi-page PDF
- [ ] Grade mapping applies correctly

### Offline / Sync
- [ ] App works offline with cached data
- [ ] Sync banner appears when offline
- [ ] Queued operations flush on reconnect
- [ ] LifecycleAwarePolling pauses in background
- [ ] LifecycleAwarePolling resumes with fast tick on foreground

### UI / UX
- [ ] Dark mode renders correctly on all views
- [ ] Haptic feedback on key interactions
- [ ] All text uses Localizable.strings (no hardcoded English)
- [ ] Navigation flows work in both compact and regular size classes
- [ ] No layout issues on iPad

### Security
- [ ] Keychain uses kSecAttrAccessibleAfterFirstUnlock
- [ ] No hardcoded API keys or secrets in code
- [ ] ATS configuration allows only necessary domains
- [ ] Privacy manifest (PrivacyInfo.xcprivacy) is present
- [ ] Entitlements file correctly configured

### Performance
- [ ] No ANRs (Application Not Responding) events
- [ ] SwiftData queries execute under 100ms
- [ ] WebSocket heartbeat maintains connection
- [ ] URLCache reduces duplicate network requests
- [ ] Logger replaces all print() calls

### App Store Metadata
- [ ] App name: BizSimAI
- [ ] Category: Education
- [ ] Age rating: 4+ (no user-generated content, no gambling)
- [ ] Privacy policy URL configured
- [ ] Support URL configured
- [ ] App description reviewed
- [ ] Screenshots for 6.7", 6.5", 5.5" devices
- [ ] App preview video (optional)

### Localization
- [ ] English (base)
- [ ] Spanish
- [ ] Brazilian Portuguese
- [ ] French
- [ ] German
- [ ] Simplified Chinese
- [ ] Japanese
- [ ] Korean

### Version
- [ ] Marketing version: 1.0.0
- [ ] Build number incremented
- [ ] What's New text written
