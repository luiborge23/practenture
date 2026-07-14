# BizSimAI iOS App — Professor API Endpoints Analysis

This document lists ALL API endpoints the iOS app calls that are relevant to the Professor role.
The backend currently has NO professor routes — these are the endpoints the iOS app expects.

---

## 1. Authentication (AuthManager.swift)

### 1.1 Professor Login
- **HTTP Method:** `POST`
- **Path:** `/api/auth/login`
- **Request Body:**
  ```json
  {
    "email": "String",
    "password": "String"
  }
  ```
- **Expected Response (`LoginResponse`):**
  ```json
  {
    "access_token": "String",
    "token_type": "String" (e.g., "bearer"),
    "user": {
      "id": "String (UUID)",
      "email": "String",
      "role": "String" ("professor" or "student"),
      "name": "String?"
    }
  }
  ```
- **Called from:** `AuthManager.swift` → `login(email:password:)` method (~line 40-60)

### 1.2 Student Login
- **HTTP Method:** `POST`
- **Path:** `/api/auth/login`
- **Request Body:** Same as above
- **Expected Response:** Same as above
- **Called from:** `AuthManager.swift` → `login(email:password:)` method

### 1.3 Register Professor
- **HTTP Method:** `POST`
- **Path:** `/api/auth/register`
- **Request Body:**
  ```json
  {
    "email": "String",
    "password": "String",
    "name": "String?",
    "role": "String" (must be "professor")
  }
  ```
- **Expected Response:** Same `LoginResponse` structure
- **Called from:** `AuthManager.swift` → `register(email:password:name:role:)` method

---

## 2. Session Management (Professor) — NetworkService.swift

### 2.1 Get Professor Dashboard Sessions
- **HTTP Method:** `GET`
- **Path:** `/api/sessions/dashboard`
- **Request Body:** None
- **Expected Response (`[SessionBackend]`):**
  ```json
  [
    {
      "id": "String (UUID)",
      "code": "String" (e.g., "BIZ-XXXX"),
      "name": "String",
      "config": {
        "name": "String",
        "totalRounds": "Int",
        "startingCash": "Double",
        "marketType": "String" ("conservative" | "moderate" | "aggressive"),
        "aiDifficulty": "String" ("easy" | "medium" | "hard"),
        "numberOfAICompetitors": "Int",
        "scoringMetric": "String" ("investorScore" | "cumulativeProfit" | "revenue" | "composite"),
        "fixedCostsPerRound": "Double",
        "baseCostPerUnit": "Double",
        "baseMarketDemand": "Int",
        "sharesOutstanding": "Int",
        "initialEquity": "Double",
        "baseInterestRate": "Double",
        "plantCapacity": "Int",
        "courseCode": "String",
        "semester": "String",
        "maxHumanTeams": "Int",
        "teamSize": "Int",
        "roundPacingMode": "String" ("timed" | "manual"),
        "roundDeadlineHours": "Int",
        "latePolicy": "String" ("usePrevious" | "zero" | "partial"),
        "isPracticeMode": "Bool",
        "template": "String" ("custom" | "intro" | "standard" | "advanced"),
        "sessionExpiryDate": "String (ISO 8601)?"
      },
      "teams": [
        {
          "id": "String (UUID)",
          "name": "String",
          "isAI": "Bool"
        }
      ],
      "currentRound": "Int",
      "state": "String" ("waitingForPlayers" | "inProgress" | "completed"),
      "results": "[TeamResultBackend]?",
      "createdBy": "String (UUID)"
    }
  ]
  ```
- **Called from:** `NetworkService.swift` → `getDashboardSessions()` (~line 192-210)

### 2.2 Create Session
- **HTTP Method:** `POST`
- **Path:** `/api/sessions`
- **Request Body (`SessionConfiguration` + `teams`):**
  ```json
  {
    "config": {
      "name": "String",
      "totalRounds": "Int",
      "startingCash": "Double",
      "marketType": "String",
      "aiDifficulty": "String",
      "numberOfAICompetitors": "Int",
      "scoringMetric": "String",
      "fixedCostsPerRound": "Double",
      "baseCostPerUnit": "Double",
      "baseMarketDemand": "Int",
      "sharesOutstanding": "Int",
      "initialEquity": "Double",
      "baseInterestRate": "Double",
      "plantCapacity": "Int",
      "courseCode": "String",
      "semester": "String",
      "maxHumanTeams": "Int",
      "teamSize": "Int",
      "roundPacingMode": "String",
      "roundDeadlineHours": "Int",
      "latePolicy": "String",
      "isPracticeMode": "Bool",
      "template": "String",
      "sessionExpiryDate": "String (ISO 8601)?"
    },
    "teams": [
      {
        "id": "String (UUID)",
        "name": "String",
        "isAI": "Bool"
      }
    ]
  }
  ```
- **Expected Response (`CreatedSessionBackend`):**
  ```json
  {
    "code": "String" (e.g., "BIZ-XXXX"),
    "id": "String (UUID)",
    "teamsCount": "Int"
  }
  ```
- **Called from:** `NetworkService.swift` → `createSession(config:teams:)` (~line 213-232)
- **Also called from:** `SyncService.swift` → `syncSessionCreation(localSession:)`

### 2.3 Get Session Status
- **HTTP Method:** `GET`
- **Path:** `/api/sessions/{code}/status`
- **Request Body:** None (path parameter `code`)
- **Expected Response (`SessionStatusBackend`):**
  ```json
  {
    "state": "String" ("waitingForPlayers" | "inProgress" | "completed"),
    "teamsSubmitted": "Int",
    "totalTeams": "Int",
    "currentRound": "Int",
    "totalRounds": "Int"
  }
  ```
- **Called from:** `NetworkService.swift` → `getSessionStatus(code:)` (~line 235-250)
- **Also called from:** `SessionMonitorViewModel.swift` → `pollBackendStatus()` (~line 192)
- **Also called from:** `SyncService.swift` → `syncTeamStatus(sessionCode:)`

### 2.4 Process Round
- **HTTP Method:** `POST`
- **Path:** `/api/sessions/{code}/process-round`
- **Request Body:**
  ```json
  {
    "decisions": [
      {
        "teamId": "String (UUID)",
        "round": "Int",
        "productQuality": "Int",
        "wholesalePrice": "Double",
        "internetPrice": "Double",
        "productionQuantity": "Int",
        "rawMaterials": "Int",
        "advertisingBudget": "Double",
        "sponsoredProductBudget": "Double",
        "stockPrice": "Double",
        "equityOffered": "Double",
        "debtRatio": "Double",
        "interestRateBid": "Double",
        "laborCost": "Double",
        "laborHours": "Int",
        "deliveryTime": "String" ("standard" | "rush"),
        "celebrityEndorsement": "String" ("none" | "local" | "national" | "global"),
        "influencerTier": "String" ("none" | "nano" | "micro" | "macro" | "mega"),
        "fulfillmentMethod": "String" ("fba" | "fbm")
      }
    ]
  }
  ```
- **Expected Response (`[RoundResultBackend]`):**
  ```json
  [
    {
      "teamId": "String (UUID)",
      "profit": "Double",
      "revenue": "Double",
      "marketShare": "Double",
      "customerSatisfaction": "Double",
      "cash": "Double",
      "inventory": "Int",
      "sqRating": "Double",
      "eps": "Double",
      "roe": "Double",
      "stockPrice": "Double",
      "imageRating": "Double",
      "creditRating": "String",
      "totalScore": "Double",
      "rejectionRate": "Double",
      "round": "Int"
    }
  ]
  ```
- **Called from:** `NetworkService.swift` → `processRound(code:)` (~line 253-270)
- **Also called from:** `SessionMonitorViewModel.swift` → `processRoundWithBackend()` (~line 248)

### 2.5 End Session
- **HTTP Method:** `POST`
- **Path:** `/api/sessions/{code}/end`
- **Request Body:** None
- **Expected Response:** Empty or success acknowledgment
- **Called from:** `NetworkService.swift` → `endSession(code:)` (~line 273-288)
- **Also called from:** `SessionMonitorViewModel.swift` → `endSessionWithBackend()` (~line 293)

---

## 3. Leaderboard — NetworkService.swift

### 3.1 Get Leaderboard
- **HTTP Method:** `GET`
- **Path:** `/api/sessions/{code}/leaderboard`
- **Request Body:** None
- **Expected Response (`[LeaderboardEntryBackend]`):**
  ```json
  [
    {
      "teamId": "String (UUID)",
      "teamName": "String",
      "isAI": "Bool",
      "rank": "Int",
      "cumulativeInvestorScore": "Double",
      "cumulativeProfit": "Double",
      "cumulativeRevenue": "Double",
      "avgMarketShare": "Double",
      "avgSatisfaction": "Double",
      "currentCash": "Double",
      "currentInventory": "Int",
      "sqRating": "Double",
      "imageRating": "Double",
      "creditRating": "String",
      "roundsScored": "Int"
    }
  ]
  ```
- **Called from:** `NetworkService.swift` → `getLeaderboard(code:)` (~line 291-306)
- **Also called from:** `LeaderboardViewModel.swift` → `loadLeaderboard()` (~line 80-95)
- **Also called from:** `SyncService.swift` → `syncLeaderboard(sessionCode:)`

### 3.2 Export Grades (CSV)
- **HTTP Method:** `GET`
- **Path:** `/api/sessions/{code}/export/grades`
- **Request Body:** None
- **Expected Response:** CSV text content (not JSON)
- **Called from:** `NetworkService.swift` → `exportGrades(code:)` (~line 309-320)
- **Also called from:** `SessionResultsView.swift` → `CSVExportViewModel.exportGrades()` (~line 58)

### 3.3 Export Leaderboard (CSV)
- **HTTP Method:** `GET`
- **Path:** `/api/sessions/{code}/export/leaderboard`
- **Request Body:** None
- **Expected Response:** CSV text content (not JSON)
- **Called from:** `NetworkService.swift` → `exportLeaderboard(code:)` (~line 323-334)
- **Also called from:** `SessionResultsView.swift` → `CSVExportViewModel.exportLeaderboard()` (~line 97)

---

## 4. Session Detail — NetworkService.swift

### 4.1 Get Session by Code
- **HTTP Method:** `GET`
- **Path:** `/api/sessions/{code}`
- **Request Body:** None
- **Expected Response:** `SessionBackend` (same structure as in dashboard list)
- **Called from:** `NetworkService.swift` → `getSession(code:)` (~line 337-350)
- **Also called from:** `SessionListViewModel.swift` → `syncSessions()` (~line 60-65)

### 4.2 Get Session Results
- **HTTP Method:** `GET`
- **Path:** `/api/sessions/{code}/results`
- **Request Body:** None
- **Expected Response (`[String: [RoundResultBackend]]` — keyed by teamId):**
  ```json
  {
    "team-uuid-1": [
      { "teamId": "String", "round": "Int", "profit": "Double", ... },
      { "teamId": "String", "round": "Int", "profit": "Double", ... }
    ],
    "team-uuid-2": [...]
  }
  ```
- **Called from:** `NetworkService.swift` → `getResults(code:)` (~line 353-366)
- **Also called from:** `SyncService.swift` → `syncRoundResults(sessionCode:)`

---

## 5. Announcements — NetworkService.swift

### 5.1 Get Announcements
- **HTTP Method:** `GET`
- **Path:** `/api/sessions/{code}/announcements`
- **Request Body:** None
- **Expected Response (`[AnnouncementBackend]`):**
  ```json
  [
    {
      "id": "String (UUID)",
      "message": "String",
      "roundNumber": "Int?",
      "authorId": "String (UUID)",
      "authorName": "String",
      "createdAt": "String (ISO 8601)"
    }
  ]
  ```
- **Called from:** `NetworkService.swift` → `getAnnouncements(code:)` (~line 369-380)
- **Also called from:** `SyncService.swift` → `syncAnnouncements(sessionCode:)`
- **Also called from:** `AnnouncementViewModel.swift` → `loadAnnouncements()`

### 5.2 Send Announcement
- **HTTP Method:** `POST`
- **Path:** `/api/sessions/{code}/announcements`
- **Request Body:**
  ```json
  {
    "message": "String",
    "roundNumber": "Int?",
    "authorId": "String (UUID)",
    "authorName": "String"
  }
  ```
- **Expected Response:** `AnnouncementBackend` (same structure as above)
- **Called from:** `NetworkService.swift` → `sendAnnouncement(code:message:authorId:authorName:)` (~line 383-396)
- **Also called from:** `AnnouncementsView.swift` → `sendAnnouncement()` (~line 65-78)
- **Also called from:** `SyncService.swift` → `executeSyncAction(.sendAnnouncement)`

---

## 6. WebSocket (Real-time Updates) — WebSocketManager.swift

### 6.1 WebSocket Connection
- **Protocol:** `WS` / `WSS`
- **Path:** `/ws/{sessionCode}`
- **Request Body:** N/A (WebSocket handshake)
- **Expected Messages:** JSON events — `connected`, `disconnected`, `message`, `error`
- **Called from:** `WebSocketManager.swift` → `connect(toSession:baseURL:)` (~line 69-86)
- **Also called from:** `JoinSessionView.swift` → `joinSession()` (~line 60-75)

---

## 7. Student Operations (Professor may need these for team management)

### 7.1 Join Session (Student registers for a session)
- **HTTP Method:** `POST`
- **Path:** `/api/sessions/{code}/join`
- **Request Body:**
  ```json
  {
    "teamName": "String",
    "studentId": "String"
  }
  ```
- **Expected Response (`JoinSessionBackend`):**
  ```json
  {
    "teamId": "String (UUID)",
    "teamName": "String",
    "sessionCode": "String",
    "sessionName": "String"
  }
  ```
- **Called from:** `NetworkService.swift` → `joinSession(code:teamName:studentId:)` (~line 400-415)
- **Also called from:** `SyncService.swift` → `syncSessionJoin(sessionCode:teamName:studentId:)`
- **Also called from:** `JoinSessionViewModel.swift` → `joinSession()`

### 7.2 Submit Decision
- **HTTP Method:** `POST`
- **Path:** `/api/sessions/{code}/submit-decision`
- **Request Body:**
  ```json
  {
    "round": "Int",
    "teamId": "String (UUID)",
    "decision": {
      "productQuality": "Int",
      "wholesalePrice": "Double",
      "internetPrice": "Double",
      "productionQuantity": "Int",
      "rawMaterials": "Int",
      "advertisingBudget": "Double",
      "sponsoredProductBudget": "Double",
      "stockPrice": "Double",
      "equityOffered": "Double",
      "debtRatio": "Double",
      "interestRateBid": "Double",
      "laborCost": "Double",
      "laborHours": "Int",
      "deliveryTime": "String",
      "celebrityEndorsement": "String",
      "influencerTier": "String",
      "fulfillmentMethod": "String"
    }
  }
  ```
- **Expected Response:** Success acknowledgment
- **Called from:** `NetworkService.swift` → `submitDecision(code:round:teamId:decision:)` (~line 418-435)
- **Also called from:** `SyncService.swift` → `syncDecisionSubmission(...)`

---

## 8. Health Check

### 8.1 Health Check
- **HTTP Method:** `GET`
- **Path:** `/api/health`
- **Request Body:** None
- **Expected Response:** `true` (boolean)
- **Called from:** `NetworkService.swift` → `healthCheck()` (~line 438-448)
- **Also called from:** `SyncService.swift` → `checkConnection()` (~line 181)

---

## 9. Models Used by Professor Views

### 9.1 `SessionBackend` (NetworkService.swift, lines ~563-590)
```swift
struct SessionBackend: Codable {
    let id: String
    let code: String
    let config: SessionConfigBackend
    let teams: [TeamConfigBackend]
    let currentRound: Int
    let state: String
    let results: [TeamResultBackend]?
    let createdBy: String
}
```

### 9.2 `SessionConfigBackend` (NetworkService.swift)
```swift
struct SessionConfigBackend: Codable {
    let name: String
    let totalRounds: Int
    let startingCash: Double
    let marketType: String
    let aiDifficulty: String
    let numberOfAICompetitors: Int
    let scoringMetric: String
    let fixedCostsPerRound: Double
    let baseCostPerUnit: Double
    let baseMarketDemand: Int
    let sharesOutstanding: Int
    let initialEquity: Double
    let baseInterestRate: Double
    let plantCapacity: Int
    let courseCode: String
    let semester: String
    let maxHumanTeams: Int
    let teamSize: Int
    let roundPacingMode: String
    let roundDeadlineHours: Int
    let latePolicy: String
    let isPracticeMode: Bool
    let template: String
    let sessionExpiryDate: String?
}
```

### 9.3 `TeamConfigBackend` (NetworkService.swift)
```swift
struct TeamConfigBackend: Codable {
    let id: String
    let name: String
    let isAI: Bool
}
```

### 9.4 `TeamResultBackend` (NetworkService.swift)
```swift
struct TeamResultBackend: Codable {
    let teamId: String
    let profit: Double
    let revenue: Double
    let marketShare: Double
    let customerSatisfaction: Double
    let cash: Double
    let inventory: Int
    let sqRating: Double
    let eps: Double
    let roe: Double
    let stockPrice: Double
    let imageRating: Double
    let creditRating: String
    let totalScore: Double
    let rejectionRate: Double
    let round: Int
}
```

### 9.5 `SessionStatusBackend` (NetworkService.swift)
```swift
struct SessionStatusBackend: Codable {
    let state: String
    let teamsSubmitted: Int
    let totalTeams: Int
    let currentRound: Int
    let totalRounds: Int
}
```

### 9.6 `LeaderboardEntryBackend` (NetworkService.swift)
```swift
struct LeaderboardEntryBackend: Codable {
    let teamId: String
    let teamName: String
    let isAI: Bool
    let rank: Int
    let cumulativeInvestorScore: Double
    let cumulativeProfit: Double
    let cumulativeRevenue: Double
    let avgMarketShare: Double
    let avgSatisfaction: Double
    let currentCash: Double
    let currentInventory: Int
    let sqRating: Double
    let imageRating: Double
    let creditRating: String
    let roundsScored: Int
}
```

### 9.7 `RoundResultBackend` (NetworkService.swift)
```swift
struct RoundResultBackend: Codable {
    let teamId: String
    let profit: Double
    let revenue: Double
    let marketShare: Double
    let customerSatisfaction: Double
    let cash: Double
    let inventory: Int
    let sqRating: Double
    let eps: Double
    let roe: Double
    let stockPrice: Double
    let imageRating: Double
    let creditRating: String
    let totalScore: Double
    let rejectionRate: Double
    let round: Int
}
```

### 9.8 `AnnouncementBackend` (NetworkService.swift)
```swift
struct AnnouncementBackend: Codable {
    let id: String
    let message: String
    let roundNumber: Int?
    let authorId: String
    let authorName: String
    let createdAt: String
}
```

### 9.9 `CreatedSessionBackend` (NetworkService.swift)
```swift
struct CreatedSessionBackend: Codable {
    let code: String
    let id: String
    let teamsCount: Int
}
```

### 9.10 `JoinSessionBackend` (NetworkService.swift)
```swift
struct JoinSessionBackend: Codable {
    let teamId: String
    let teamName: String
    let sessionCode: String
    let sessionName: String
}
```

### 9.11 `TeamConfig` (SyncService.swift)
```swift
struct TeamConfig: Codable {
    let id: UUID
    let name: String
    let isAI: Bool
}
```

### 9.12 `FinalTeamResult` (SessionResultsView.swift)
```swift
struct FinalTeamResult: Identifiable {
    let id: UUID
    let rank: Int
    let teamName: String
    let isAI: Bool
    let totalProfit: Double
    let totalRevenue: Double
    let avgMarketShare: Double
    let avgSatisfaction: Double
}
```

### 9.13 `GradeMapping` (SimulationSession.swift)
```swift
struct GradeMapping: Codable {
    let label: String  // "A+", "A", "A-", "B+", etc.
    let minScore: Double
}
```

### 9.14 `EnrolledStudent` (SimulationSession.swift)
```swift
struct EnrolledStudent: Identifiable {
    let id: UUID
    let name: String
    let email: String
    var isActive: Bool = true
    var teamId: UUID?
}
```

### 9.15 `TeamStatus` (SimulationModels.swift)
```swift
struct TeamStatus: Identifiable {
    let id: UUID
    var name: String
    var cash: Double
    var reputation: Double
    var inventory: Int
    var sqRating: Double
    var imageRating: Double
    var creditRating: String
    var rank: Int
    var hasSubmittedDecisions: Bool
    var isAI: Bool
    var equity: Double
    var sharesOutstanding: Int
    var cumulativeInvestorScore: Double
    var cumulativeProfit: Double
    var roundsScored: Int
}
```

### 9.16 `PlayerDecision` (SimulationModels.swift)
```swift
struct PlayerDecision: Codable {
    let teamId: UUID
    let round: Int
    let productQuality: Int
    let wholesalePrice: Double
    let internetPrice: Double
    let productionQuantity: Int
    let rawMaterials: Int
    let advertisingBudget: Double
    let sponsoredProductBudget: Double
    let stockPrice: Double
    let equityOffered: Double
    let debtRatio: Double
    let interestRateBid: Double
    let laborCost: Double
    let laborHours: Int
    let deliveryTime: String
    let celebrityEndorsement: String
    let influencerTier: String
    let fulfillmentMethod: String
}
```

### 9.17 `RoundResult` (SimulationModels.swift)
```swift
struct RoundResult: Codable {
    let teamId: UUID
    let round: Int
    let profit: Double
    let revenue: Double
    let marketShare: Double
    let customerSatisfaction: Double
    let cash: Double
    let inventory: Int
    let sqRating: Double
    let eps: Double
    let roe: Double
    let stockPrice: Double
    let imageRating: Double
    let creditRating: String
    let totalScore: Double
    let rejectionRate: Double
    let scorecard: InvestorScorecard
}
```

### 9.18 `InvestorScorecard` (SimulationModels.swift)
```swift
struct InvestorScorecard: Codable {
    let eps: Double
    let roe: Double
    let stockPrice: Double
    let imageRating: Double
    let creditRating: String
    let totalScore: Double
}
```

### 9.19 `CoachMessage` (SimulationModels.swift)
```swift
struct CoachMessage: Identifiable {
    let id: UUID
    let message: String
    let roundNumber: Int?
    let timestamp: Date
}
```

### 9.20 `RoundSummary` (SimulationModels.swift)
```swift
struct RoundSummary: Identifiable {
    let id: UUID
    let round: Int
    let message: String
    let timestamp: Date
}
```

### 9.21 `Announcement` (SimulationSession.swift)
```swift
struct Announcement: Identifiable {
    let id: UUID
    let message: String
    let roundNumber: Int?
}
```

### 9.22 `MonitoredTeamStatus` (SessionMonitorViewModel.swift)
```swift
struct MonitoredTeamStatus: Identifiable {
    let id: UUID
    let teamName: String
    let isAI: Bool
    var hasSubmittedDecision: Bool
    var cash: Double
    var reputation: Double
    var rank: Int
    var sqRating: Double
    var imageRating: Double
    var investorScore: Double
}
```

---

## 10. Professor Tab Views (UI Layer — no direct API calls)

| File | Purpose |
|------|---------|
| `ProfessorTabView.swift` | Main tab container with 5 tabs: Dashboard, Sessions, Monitor, Leaderboard, Results |
| `SessionListView.swift` | List of sessions + create session form |
| `CreateSessionView.swift` | Form for creating a new simulation session |
| `SessionMonitorView.swift` | Live monitoring dashboard with team grid |
| `RoundControlView.swift` | Round control (advance, end session) |
| `ProfessorLeaderboardView.swift` | Team rankings table |
| `SessionResultsView.swift` | Final results with podium + CSV export |
| `TeamManagementView.swift` | Student roster + team assignment |
| `AnnouncementsView.swift` | Professor sends announcements |
| `GradeMappingView.swift` | Configure grade thresholds |

---

## 11. Summary of All Professor API Endpoints

| # | HTTP | Path | Method |
|---|------|------|--------|
| 1 | POST | `/api/auth/login` | AuthManager |
| 2 | POST | `/api/auth/register` | AuthManager |
| 3 | GET | `/api/sessions/dashboard` | NetworkService |
| 4 | POST | `/api/sessions` | NetworkService |
| 5 | GET | `/api/sessions/{code}` | NetworkService |
| 6 | GET | `/api/sessions/{code}/status` | NetworkService |
| 7 | POST | `/api/sessions/{code}/process-round` | NetworkService |
| 8 | POST | `/api/sessions/{code}/end` | NetworkService |
| 9 | GET | `/api/sessions/{code}/leaderboard` | NetworkService |
| 10 | GET | `/api/sessions/{code}/export/grades` | NetworkService |
| 11 | GET | `/api/sessions/{code}/export/leaderboard` | NetworkService |
| 12 | GET | `/api/sessions/{code}/results` | NetworkService |
| 13 | GET | `/api/sessions/{code}/announcements` | NetworkService |
| 14 | POST | `/api/sessions/{code}/announcements` | NetworkService |
| 15 | POST | `/api/sessions/{code}/join` | NetworkService |
| 16 | POST | `/api/sessions/{code}/submit-decision` | NetworkService |
| 17 | GET | `/api/health` | NetworkService |
| 18 | WS | `/ws/{sessionCode}` | WebSocketManager |

**Total: 18 endpoints (17 REST + 1 WebSocket)**

The backend currently has only `/api/auth/*` and `/api/sessions/*` (auth + session creation/status). The iOS app expects professor-specific endpoints like `/api/sessions/dashboard`, `/api/sessions/{code}/results`, `/api/sessions/{code}/leaderboard`, `/api/sessions/{code}/export/grades`, `/api/sessions/{code}/export/leaderboard`, `/api/sessions/{code}/announcements`, etc. that do NOT exist yet.
