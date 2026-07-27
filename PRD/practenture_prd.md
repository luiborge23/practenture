# Practenture Product Requirements Document (PRD)

## Executive Summary

Practenture is a real-time adaptive business simulation platform designed to teach strategic business decision-making through immersive, interactive gameplay. Unlike traditional batch-processed simulations, Practenture leverages WebSocket technology to provide immediate feedback on competitive moves, creating a dynamic learning environment that mirrors real-world market conditions. The platform serves both professors (as facilitators and coaches) and students (as competing business teams), with AI-powered adaptation to adjust difficulty and provide personalized learning paths based on performance.

**Core Innovation:** True real-time processing where individual team decisions instantly affect the competitive landscape, enabling teachable moments through immediate cause-and-effect observation.

## TLDR

**What:** Real-time business simulation game for education
**Why:** Traditional simulations are too slow and lack adaptive teaching capabilities
**How:** WebSocket-based architecture with AI adaptation and professor coaching tools
**Key Differentiator:** Immediate feedback loops vs. round-based processing in competitors
**Target Users:** Business professors and students (high school to MBA level)
**Success Metrics:** Engagement time, decision quality improvement, professor satisfaction

## What

Practenture is a web-based business simulation platform where student teams compete as companies in a shared market. Each team makes functional area decisions (marketing, production, finance, R&D) that are processed in real-time, affecting market conditions, competitor positioning, and financial results immediately.

### Core Components:
1. **Student Interface:** Team dashboard for making decisions and viewing results
2. **Professor Console:** Real-time monitoring, intervention tools, and class management
3. **Simulation Engine:** Deterministic yet adaptive business model processing decisions instantly
4. **Analytics Engine:** Performance tracking and personalized feedback generation
5. **Adaptive System:** AI-powered difficulty adjustment and scenario generation

## Why

### Problems with Current Solutions:
- **Latency Learning Gap:** Traditional 8-15 minute round delays disconnect actions from consequences
- **One-Size-Fits-All:** Fixed difficulty doesn't accommodate diverse skill levels in classrooms
- **Professor as Administrator:** Instructors spend time on setup/logistics rather than teaching
- **Limited Realism:** Batch processing prevents observation of market dynamics and competitor reactions
- **Assessment Lag:** Feedback comes days later when learning moments have passed

### Educational Value Proposition:
Practenture transforms business education by:
1. **Closing the Feedback Loop:** Decisions → Immediate market response → Learning → Better decisions
2. **Enabling Teachable Moments:** Professors can pause, highlight, and discuss emerging patterns
3. **Personalizing Learning:** Adaptive challenges keep all students in their optimal learning zone
4. **Developing Strategic Thinking:** Real-time competition fosters anticipation and reaction skills
5. **Providing Actionable Data:** Both professors and students get metrics for improvement

## How

### Technical Implementation:
1. **Real-Time Processing:** WebSocket connections broadcast decisions to all clients instantly
2. **Deterministic Engine:** Pure Python simulation ensures consistency across platforms
3. **Adaptive Algorithms:** ML models analyze team performance to adjust market volatility and competitor aggression
4. **Professor Tools:** Real-time anomaly detection and intervention suggestions
5. **Assessment Framework:** Competency mapping to AACSB/ABET standards with evidence generation

### Pedagogical Approach:
- **Constructivist Learning:** Students build knowledge through experimentation and reflection
- **Competitive Motivation:** Team vs. team dynamics increase engagement and effort
- **Reflective Practice:** Immediate results encourage hypothesis testing and strategy iteration
- **Coached Discovery:** Professor interventions guide rather than direct learning

## Solution Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│   iOS/Android   │    │   Web Browser    │    │   Professor Desk   │
│   Student App   │    │   Student Portal │    │   Console &      │
│                 │    │                  │    │   Analytics Dash   │
└─────────┬───────┘    └─────────┬────────┘    └──────────┬────────┘
          │                      │                          │
          ▼                      ▼                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       API Gateway (FastAPI)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  │
│  │  Auth Svc    │  │  Session Svc │  │  Sim Engine  │  │ Analytics│  │
│  │ (JWT)        │  │ (SQLite)     │  │ (Deterministic)│  │ (ML)     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────┘  │
└─────────┬───────────────────────┬─────────────────────────┬────────┘
          │                       │                         │
          ▼                       ▼                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│   WebSocket     │    │   Redis Cache    │    │   PostgreSQL       │
│   (Real-time)   │    │ (Leaderboard,    │    │ (Persistence,      │
│   Connections   │    │  Hot Data)       │    │  Analytics)        │
└─────────────────┘    └──────────────────┘    └────────────────────┘
```

### Key Technical Decisions:
1. **FastAPI Backend:** Async Python for high concurrency with WebSocket support
2. **SQLite Development → PostgreSQL Production:** Simple startup, scalable deployment
3. **Redis Caching:** For real-time leaderboards and frequently accessed data
4. **WebSocket Primary:** Real-time as main interaction model, HTTP for initial setup
5. **Deterministic Simulation:** Ensures reproducibility for grading and fairness
6. **ML Adaptation Layer:** Python/scikit-learn for performance analysis and difficulty adjustment

## Features

### Professor Features:
- **Session Management:** Create, configure, start/end sessions with one click
- **Real-Time Dashboard:** Live view of all team decisions, market positions, and performance
- **Intervention Tools:** Pause simulation, highlight trends, send targeted announcements
- **Adaptive Controls:** Adjust market volatility, competitor intelligence, and complexity
- **Assessment Generation:** Auto-generated competency reports and improvement suggestions
- **LMS Integration:** LTI launch and grade passback capabilities

### Student/Team Features:
- **Team Dashboard:** Unified view of financials, market share, and competitor moves
- **Functional Decision Areas:** Marketing, Production, Finance, R&D with realistic constraints
- **Real-Time Competitor Intelligence:** See rivals' moves as they happen (with appropriate delays)
- **Instant Feedback:** Immediate impact of decisions on financial statements and market position
- **Strategy Testing:** Ability to run "what-if" scenarios before committing decisions
- **Post-Round Analysis:** Detailed breakdown of what drove results and competitor actions

### Simulation Features:
- **Real-Time Market Clearing:** Prices and quantities adjust instantly to supply/demand
- **Dynamic Competitor Reactions:** AI competitors adapt to collective market behavior
- **External Shocks:** Programmable market events (recessions, booms, supply chain issues)
- **Industry Templates:** Plug-and-play models for different sectors (retail, tech, manufacturing)
- **Scalable Complexity:** From 4-quarter high school game to 8-round MBA competition

### Technical Features:
- **Cross-Platform:** iOS, Android, and web clients from same API
- **Offline Capability:** Local caching with sync when connection restored
- **Data Export:** CSV/JSON export of all session data for research purposes
- **Audit Trail:** Complete logging of all decisions and simulation states
- **Extensible Architecture:** Microservices-ready design for future enhancements

## Competitive Benchmarking

| Feature                        | Practenture         | Capstone         | Marketplace Sim  | Cesim Global     | Hubro            |
|--------------------------------|------------------|------------------|------------------|------------------|------------------|
| **Processing Speed**           | Real-time        | 15-min rounds    | 5-min rounds     | 10-min rounds    | 8-min rounds     |
| **Professor Tools**            | Advanced (Real-time intervention, adaptive) | Basic (Setup only) | Basic | Moderate | Good (Dashboard) |
| **Adaptive Difficulty**        | Yes (AI-powered) | No               | Limited          | No               | Yes (Pre-set levels) |
| **Industry Customization**     | Yes (Templates)  | No               | No               | Yes (Multiple)   | Limited          |
| **Mobile Experience**          | Native iOS/Android | Web-only        | Web/Mobile       | Web-only         | Web-only         |
| **Assessment Integration**     | LMS/LTI, Competency mapping | Basic grading | Basic | Moderate | Good |
| **Real-World Data Integration**| Planned (Phase 2)| No               | Social media API | Currency rates   | No               |
| **Collaboration Features**     | Team roles, negotiation | Individual | Team pitch | Limited | Team decisions |
| **Learning Analytics**         | Comprehensive (Skills mapping) | Basic | Moderate | Basic | Good |
| **Setup Complexity**           | Low (Professor console) | Moderate | Low | Moderate | Low |
| **Cost Structure**             | Institutional license | Per-student | Per-student | Per-student | Per-student |
| **Strength**                   | Real-time feedback, Professor as coach | Academic rigor, Deep finance | Entrepreneurship focus, Modern UX | International business, Multilingual | Sustainability, Progressive difficulty |
| **Weakness**                   | Newer platform (building content) | Slow feedback, Dated UI | Less operations depth | Complex for beginners | Limited customization |
| **Best For**                   | Strategic thinking development, Immediate feedback learning | Finance-heavy courses, Deep analysis | Entrepreneurship programs, Innovation courses | International business, Advanced courses | Sustainability focus, Scaffolded learning |

### Competitive Advantçoses Summary:
1. **Real-Time Processing Engine** - 10-60x faster feedback loop than competitors
2. **Professor-Centric Design** - Shifts instructor role from administrator to coach
3. **Adaptive Learning System** - Personalized challenge level maintains engagement
4. **Industry Flexibility** - Configurable simulations for different business contexts
5. **Assessment Integration** - Direct mapping to accreditation standards with evidence

## User Journey

### Professor Journey:
1. **Pre-Class Preparation (5 mins):**
   - Log into professor console
   - Select/create session with desired parameters (duration, complexity, industry)
   - Generate unique session code
   - Optional: Upload custom market conditions or learning objectives

2. **Class Launch (2 mins):**
   - Display session code and joining instructions
   - Monitor real-time student team formation
   - Confirm all teams are ready

3. **Active Facilitation (30-50 mins):**
   - Watch live decision-making patterns emerge
   - Identify teachable moments (convergent strategies, market failures, innovations)
   - Use pause/highlight tools to discuss emerging patterns
   - Send targeted announcements to struggling or leading teams
   - Adjust difficulty in real-time based on class performance

4. **Debrief & Assessment (10-15 mins):**
   - Review session analytics and performance trends
   - Highlight key learning moments from the simulation
   - Generate automated competency reports
   - Export data for further analysis or research purposes

5. **Post-Class Follow-Up:**
   - Review longitudinal performance across multiple sessions
   - Identify persistent skill gaps for remediation
   - Prepare next session with adjusted parameters based on learning outcomes

### Student/Team Journey:
1. **Onboarding (3-5 mins):**
   - Download app or access web portal
   - Enter session code provided by professor
   - Create team name and assign roles (CEO, CMO, CFO, COO optional)
   - Complete brief tutorial on interface and decision areas

2. **Strategy Development (Ongoing):**
   - Review current financial statements and market position
   - Analyze competitor moves visible in real-time feed
   - Formulate hypotheses about market reactions
   - Develop functional area strategies within budget constraints
   - Use "test decision" feature to simulate outcomes before committing

3. **Decision Execution (Per Round):**
   - Submit decisions in marketing, production, finance, and R&D areas
   - Observe immediate market reactions to own and competitor decisions
   - Experience consequences through updated financials and market share
   - Adjust strategy based on observed outcomes

4. **Learning & Adaptation:**
   - Participate in professor-facilitated discussions of market dynamics
   - Receive personalized feedback on decision quality
   - Observe how different strategies perform in same market conditions
   - Iterate approach based on what's working/not working
   - Develop anticipation skills for predicting competitor reactions

5. **Reflection & Transfer:**
   - Connect simulation experiences to real-world business concepts
   - Identify transferable skills (market analysis, strategic thinking, financial literacy)
   - Prepare for post-simulation assessment or presentation
   - Apply learning to case studies or real business problems

## How to Use the App for the Game

### For Students (Getting Started):
1. **Access:** Open Practenture app (iOS/Android) or visit web portal
2. **Join Session:** Enter the 10-character session code (format: BIZ-XXXXXX) provided by your professor
3. **Create Team:** Choose team name and optionally select role specialization
4. **Complete Tutorial:** Walk through the 3-minute interactive guide covering:
   - Navigation between functional areas (Marketing, Ops, Finance, R&D)
   - Reading financial statements and market data
   - Submitting decisions and viewing results
   - Understanding the real-time nature of the simulation
5. **First Round:**
   - Review starting conditions and available budget
   - Analyze any visible competitor moves or market data
   - Make initial functional area decisions
   - Submit and observe immediate market response
6. **Subsequent Rounds:**
   - Review results from previous round (P&L, market share, stock price if applicable)
   - Analyze competitor strategies that proved effective
   - Refine approach based on learning and professor feedback
   - Submit new decisions and continue the adaptation cycle

### For Professors (Getting Started):
1. **Setup:**
   - Log into professor console at professor.practenture.com
   - Click "Create New Session"
   - Configure parameters:
     - Duration: Number of rounds (4-12 typical)
     - Complexity level: High School / Undergraduate / MBA
     - Industry focus: Generic / Retail / Tech / Manufacturing / Healthcare
     - Random events: Enable/disable market shocks
   - Save and note the generated session code

2. **In-Class Facilitation:**
   - Project the session code for students to join
   - Monitor the "Live Overview" tab showing:
     - Number of teams joined
     - Average decision submission time
     - Market volatility indicators
     - Leaderboard (anonymized if preferred)
   - Use tabs to dive deeper:
     - **Team View:** See individual team financials and strategies
     - **Market View:** Supply/demand curves, price movements, competitor positioning
     - **Analytics:** Decision quality metrics, learning progression, anomaly detection
   - Intervention Tools:
     - **Pause:** Freeze simulation for discussion
     - **Highlight:** Flag interesting decisions or patterns for class attention
     - **Announce:** Send messages to all teams, specific teams, or individuals
     - **Adjust:** Modify difficulty parameters on-the-fly

3. **Assessment & Debrief:**
   - Use "Session Summary" tab for post-game analysis
   - Review key metrics:
     - Decision consistency and improvement over time
     - Strategic alignment with winning approaches
     - Financial literacy demonstration
     - Competitive reaction speed and accuracy
   - Generate competency reports aligned with AACSB/ABET standards
   - Export raw data for research or further analysis
   - Prepare next session based on identified learning needs

### Technical Requirements:
- **Students:** iOS 13+ / Android 8+ or modern web browser (Chrome, Safari, Firefox, Edge)
- **Professors:** Modern web browser with access to professor console
- **Network:** Standard broadband connection (simulation uses ~50kbps per active client)
- **Access:** No special ports or firewall changes required (uses standard HTTPS/WSS)

### Best Practices:
1. **For Professors:**
   - Start with a practice round to familiarize students with interface
   - Use pause feature strategically - not too frequently to disrupt flow
   - Focus debrief on strategic thinking, not just financial outcomes
   - Encourage teams to articulate their reasoning behind decisions
   - Leverage real-time examples to teach concepts like first-mover advantage, reaction timing, etc.

2. **For Students:**
   - Treat early rounds as experimentation - try different approaches
   - Pay attention to both your results and what competitors are doing
   - Use the "why did this happen?" question to drive learning
   - Communicate effectively within your team about strategy changes
   - Remember that in business simulation, as in real business, adaptation beats rigid planning

### Sample Session Timeline (50-minute class):
- 0-5 min: Setup, team formation, tutorial completion
- 5-45 min: Gameplay with professor facilitation (approximately 6-8 rounds)
- 45-50 min: Quick debrief on key observations and learning points
- Optional: Extended debrief in next class session or as assignment
