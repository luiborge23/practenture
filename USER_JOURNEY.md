# BizSimAI — User Journey Guide

## Complete End-to-End User Experience

---

## 🎓 Professor Journey

### Step 1: Authentication & Setup

**Access the Platform**
1. Open BizSimAI on iOS device or web dashboard
2. Select "Professor Login" mode
3. Enter credentials (default: `professor` / `bizsimai2026`)
4. Or use Apple/Google Sign-In for single-sign-on
5. Token stored securely in iOS Keychain (24h expiry)
6. App auto-redirects to Professor Dashboard

**Dashboard Overview**
- Session list with active/completed simulations
- Quick stats: total sessions, active teams, students
- Recent activity feed
- Create new session button

### Step 2: Create Simulation Session

**Configuration**
1. Tap "Create Session"
2. Set simulation parameters:
   - **Total Rounds**: 1-10 (recommended: 5-8 for classroom)
   - **Number of Teams**: 4-8 (recommended: 4-6)
   - **AI Difficulty**: Easy / Medium / Hard
   - **Seed Value**: For reproducible results (optional)
3. Tap "Create"
4. System generates unique session code: `BIZ-XXXXXX` (10 chars)
5. Code displayed prominently for sharing

**Session Setup**
- Session code appears with copy-to-clipboard button
- QR code generated for easy mobile scanning
- Session settings displayed for reference
- "Start Simulation" button ready

### Step 3: Student Onboarding

**Student Registration**
1. Students open BizSimAI on their device
2. Select "Student Login" or "Student Register"
3. Enter credentials:
   - Student ID (e.g., `S12345678`)
   - Full Name
   - Password
   - Team Name (e.g., "Team Alpha")
4. Or use Apple/Google Sign-In for instant access
5. Register is idempotent — can join multiple times

**Joining Session**
1. Navigate to "Join Session"
2. Enter session code: `BIZ-XXXXXX`
3. System assigns team (Alpha, Beta, Gamma, Delta, etc.)
4. Redirected to Team Dashboard
5. Real-time WebSocket connection established

### Step 4: Monitor Live Simulation

**Professor Monitoring Dashboard**
1. Access session detail from dashboard
2. Real-time monitoring view shows:
   - **Team List**: With submission status (✓ submitted / ✗ pending)
   - **Live Leaderboard**: Auto-updates via WebSocket
   - **Stock Price Charts**: Per team performance
   - **Key Metrics**: EPS, ROE, cumulative profit
3. Send announcements to all students
4. View individual student decisions (audit trail)
5. Export grades at any time (even mid-simulation)

**Round Management**
1. Wait for all teams to submit decisions
2. Tap "Process Round"
3. Simulation engine calculates outcomes
4. WebSocket broadcasts results to all students
5. Professor sees updated leaderboard
6. Can send round-specific announcements

### Step 5: Analytics & Reporting

**Class Analytics Dashboard**
1. Tap "Analytics" in session view
2. View comprehensive metrics:
   - **Class Overview Cards**: Total teams, avg equity, profit, market share, S/Q rating, credit rating
   - **Round Trends**: Charts showing performance over time
   - **Team Comparison**: Side-by-side team metrics
   - **Strategy Distribution**: Pie chart of AI strategies used
3. Export analytics as CSV
4. Share reports with department

**Grade Export**
1. Tap "Export Grades"
2. Choose export type:
   - **Full Grades**: All student decisions + results
   - **Leaderboard CSV**: Team rankings
   - **Round-by-Round**: Detailed per-round data
3. CSV file generated for LMS upload
4. Compatible with Canvas, Blackboard, Moodle

### Step 6: End Simulation

**Final Results**
1. After final round, tap "End Session"
2. System generates comprehensive results
3. Final standings displayed
4. All student data archived
5. Session moves to "Completed" list

---

## 🎒 Student Journey

### Step 1: Registration & Login

**First-Time Setup**
1. Download BizSimAI from App Store
2. Open app — LaunchView checks for stored token
3. No token → LoginView displayed
4. Select "Student Register"
5. Fill in:
   - Student ID
   - Full Name
   - Team Name
   - Password
6. Or tap "Student Login" if already registered
7. Or use Apple/Google Sign-In for instant access
8. Token stored in Keychain — auto-login on future opens

### Step 2: Join Simulation

**Session Access**
1. After login, see "Enter Session Code" screen
2. Enter professor's code: `BIZ-XXXXXX`
3. System confirms team assignment
4. Redirected to Team Dashboard
5. WebSocket connection established for real-time updates

### Step 3: Team Dashboard

**Dashboard Overview**
- **Market Information**: Current conditions, industry stats
- **Competitor Analysis**: Team rankings, market share
- **Current Round**: Round number, teams submitted
- **Team Status**: Your team's current position
- **Announcements**: Professor messages
- **Navigation**: Bottom tab bar for different sections

### Step 4: Make Decisions (Per Round)

**Decision Interface**
1. Navigate to "Decisions" tab
2. Six decision categories presented:

**Pricing Decisions**
- Wholesale Price
- Internet Price
- Private Label Bid Price
- Amazon Price
- Amazon Ad Budget

**Product Decisions**
- Materials Quality (Economy / Standard / Superior)
- Styling Budget
- Models Offered
- TQM Investment

**Marketing Decisions**
- Advertising Budget
- Celebrity Endorsement (None / Local / National)
- Retail Outlets
- Mail-in Rebate
- Delivery Time (Standard / Rush)
- Free Shipping Threshold
- TikTok/Instagram/YouTube Budget
- Influencer Tier (None / Nano / Micro / Macro)

**Workforce Decisions**
- Base Wage
- Incentive Pay
- Training Hours
- Best Practices Investment

**Production Decisions**
- Production Quantity
- Overtime Percent

**Finance Decisions**
- CSR Investment
- Dividends Per Share
- New Loan Amount
- Shares Buyback
- Shares Issued

**Submission**
1. Review all decisions
2. Tap "Submit Decision"
3. Confirmation displayed
4. Status shows "Submitted" in dashboard
5. Wait for professor to process round

### Step 5: View Results

**Round Results**
1. WebSocket delivers `round_complete` message
2. Results screen shows:
   - Revenue, Profit, Net Income
   - Market Share
   - Stock Price
   - S/Q Rating
   - Credit Rating
   - Investor Score
3. Navigate to "Leaderboard" for team rankings
4. View "Performance History" for trend charts
5. Check "Announcements" for professor feedback

### Step 6: AI Coach Assistance

**Smart Recommendations**
1. Tap "AI Coach" bubble
2. Receive contextual suggestions:
   - Pricing advice based on market conditions
   - Production recommendations
   - Marketing strategy tips
   - Financial planning guidance
3. Suggestions adapt based on your performance
4. Available throughout decision-making

### Step 7: Final Results

**End of Simulation**
1. After final round, see "Final Standings"
2. Comprehensive results displayed:
   - Team rankings
   - Individual team metrics
   - Performance charts
3. Tap "Export Results" for PDF report
4. PDF includes:
   - Session details
   - Team performance
   - Round-by-round results
   - Cumulative investments
5. Share PDF with professor or save locally

---

## 🤖 AI Competitor Behaviors

### Easy Difficulty
- **Strategies**: Best-Cost or Low-Cost Leader
- **Behavior**: Predictable, moderate risk-taking
- **Adaptation**: Minimal response to player actions

### Medium Difficulty
- **Strategies**: All four strategies distributed
- **Behavior**: Balanced risk, moderate adaptation
- **Adaptation**: Responds to player pricing and quality

### Hard Difficulty
- **Strategies**: Adaptive, Differentiator, Best-Cost
- **Behavior**: Aggressive, high adaptation
- **Adaptation**: Counter-plays player strategy in real-time

### Adaptive Strategy (Hard)
- **Analysis**: Studies player's last move
- **Counter-Strategy**:
  - If player prices high → undercut with decent quality
  - If player prices low → go premium to differentiate
  - If player moderate → match and compete on other factors
- **End-Game**: Aggressive push in final rounds
- **Investment**: Higher R&D, marketing, workforce

---

## 🔧 Technical Flow

### Authentication Flow
```
iOS App → POST /api/auth/login → JWT (HS256, 24h) → Keychain
         POST /api/auth/register
         Apple Sign-In → JWKS verification
         Google Sign-In → OAuth2 token exchange
```

### Session Flow
```
Professor: POST /api/sessions → BIZ-XXXXXX code
Student:   POST /api/sessions/{code}/join → Team assignment
Professor: POST /api/sessions/{code}/start → Simulation begins
Student:   POST /api/sessions/{code}/submit_decision → Per round
Professor: POST /api/sessions/{code}/process_round → Calculate results
WebSocket: ws://host/ws/{code} → Real-time updates
Professor: POST /api/sessions/{code}/end → Final results
```

### Real-Time Updates
```
WebSocket Connection:
- JWT passed as query parameter
- Session-based rooms
- Heartbeat every 30s
- Auto-reconnect on disconnect
- Messages: round_complete, announcement, status_update
```

---

## 📱 Platform Support

### iOS App
- **Minimum**: iOS 17.0
- **Target**: iOS 18.0
- **Devices**: iPhone 15/16/17 Pro series
- **Architecture**: SwiftUI + Combine
- **Concurrency**: Swift 6 fully compliant
- **Offline**: SyncService with offline-first queue

### Web Dashboard
- **Browser**: Chrome, Safari, Firefox, Edge
- **Features**: Session management, monitoring, grade export
- **Real-Time**: WebSocket updates
- **Responsive**: Works on tablets

---

## 🎯 Learning Objectives

### Business Concepts Covered
1. **Pricing Strategy**: Wholesale vs internet vs private label
2. **Production Management**: Capacity, overtime, quality
3. **Marketing Mix**: Advertising, celebrity, retail, digital
4. **R&D Investment**: TQM, styling, product quality
5. **Financial Management**: Loans, dividends, share buyback
6. **Inventory Control**: Stock levels, fulfillment methods

### Skills Developed
- Strategic thinking and analysis
- Data-driven decision making
- Competitive analysis
- Financial literacy
- Team collaboration
- Market adaptation

---

## 🔒 Security & Privacy

- JWT tokens stored in iOS Keychain (encrypted)
- No PII stored beyond student ID and name
- All data encrypted in transit (HTTPS)
- Session codes are 10-character random strings
- Tokens expire after 24 hours
- Professor dashboard requires role-based access

---

## 📊 Data Export Formats

### CSV Grade Export
```
Student ID,Name,Team,Round,Revenue,Profit,Market Share,Equity,Investor Score
S12345678,John Smith,Team Alpha,1,125000,15000,24.5,515000,72.3
```

### PDF Report
- Session header with code and date
- Team performance summary
- Round-by-round results table
- Cumulative investment breakdown
- Generated via UIGraphicsPDFRenderer

---

## 🚀 Quick Start Checklist

### For Professors
- [ ] Create session with desired parameters
- [ ] Share session code with students
- [ ] Monitor submissions in real-time
- [ ] Process rounds after deadline
- [ ] Send announcements as needed
- [ ] Export grades at end
- [ ] View analytics for insights

### For Students
- [ ] Register with student ID
- [ ] Join session with code
- [ ] Make decisions each round
- [ ] Submit before deadline
- [ ] Review results and leaderboard
- [ ] Use AI Coach for guidance
- [ ] Export final results

---

*Document created: 2026-06-09*  
*Last updated: 2026-06-09*  
*BizSimAI v1.0 — Business Simulation Platform for MBA Classrooms*
