# UI/UX String Audit — BizSimAI iOS

**Date:** 2026-07-16  
**Scope:** All files in `Views/Components/DecisionInput/`, `DecisionInputViewModel.swift`, `TeamDashboardView.swift`, `PerformanceHistoryView.swift`, `AboutView.swift`, and all files in `Views/Professor/`.  
**Method:** Line-by-line review of every user-facing string (labels, tab names, button text, section headers, navigation titles, alert messages, tooltips, descriptions).

---

## Summary

| Severity | Count |
|----------|-------|
| 🔴 High (user-facing confusion or inconsistency) | 14 |
| 🟡 Medium (minor inconsistency or polish issue) | 12 |
| 🟢 Low (style, missing feature, or stale doc) | 7 |
| **Total** | **33** |

---

## 1. Tab Label vs. Section Title Mismatch (🔴 High)

The `DecisionCategory` enum raw values are used as tab labels in `DecisionInputCategoryPicker`. They do not match the section titles displayed when the tab is selected.

| # | File | Line | Tab Label (rawValue) | Section Title (shown) | Issue | Suggested Fix |
|---|------|------|---------------------|----------------------|-------|---------------|
| 1 | `DecisionInputViewModel.swift` | 8 | `"Product"` | `"Product Design (S/Q Rating)"` (ProductDesignSectionView L18) | Tab says "Product" but section says "Product Design (S/Q Rating)". User may not know "Product" means design/S/Q. | Change rawValue to `"Product Design"` or shorten section to `"Product"`. |
| 2 | `DecisionInputViewModel.swift` | 9 | `"Marketing"` | `"Marketing & Distribution"` (MarketingSectionView L19) | Tab is abbreviated; section adds "& Distribution". | Align: use `"Marketing"` for both, or `"Marketing & Distribution"` for both. |
| 3 | `DecisionInputViewModel.swift` | 11 | `"Social"` | `"Social Media Marketing"` (SocialMediaSectionView L18) | Tab is heavily abbreviated; section is fully spelled out. | Change rawValue to `"Social Media"`. |
| 4 | `DecisionInputViewModel.swift` | 14 | `"CSR"` | `"Corporate Citizenship"` (CSRSectionView L17) | Tab uses acronym; section uses full term. Students may not know CSR = Corporate Social Responsibility. | Change rawValue to `"Citizenship"` or align section to `"CSR & Citizenship"`. |
| 5 | `DecisionInputViewModel.swift` | 7 | `"Pricing"` | `"Pricing & Sales"` (PricingSectionView L18) | Tab omits "& Sales". | Align both to `"Pricing"` or `"Pricing & Sales"`. |

---

## 2. Amazon Tab Shows Duplicate Content (🔴 High)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 6 | `DecisionInputView.swift` | 36 | `case .amazon: PricingSectionView(viewModel: viewModel)` | Selecting the "Amazon" tab shows the **exact same** `PricingSectionView` as the "Pricing" tab — wholesale, internet, private label, AND Amazon pricing. The user sees identical content under two different tabs. The comment says "Amazon pricing handled in PricingSection" but this is poor UX. | Create a dedicated `AmazonSectionView` that only shows the Amazon-specific portion (price, fulfillment, ad budget, economics preview), OR remove the "Amazon" tab entirely and merge it into "Pricing". |

---

## 3. Abbreviated Tab Labels (🟡 Medium)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 7 | `DecisionInputViewModel.swift` | 11 | `case socialMedia = "Social"` | Abbreviated from "Social Media Marketing". Inconsistent with section title and AboutView card title "Social Media & Influencers". | Change to `"Social Media"`. |
| 8 | `DecisionInputViewModel.swift` | 14 | `case csr = "CSR"` | Acronym may be unclear to students unfamiliar with business terminology. The section title is "Corporate Citizenship" and the AboutView card says "CSR & Image". | Change to `"Citizenship"` or `"CSR"`. Pick one and use consistently. |
| 9 | `ProfessorTabView.swift` | 17 | `case announcements = "Announce"` | Abbreviated from "Announcements". The AboutView (L245) and toolbar button (TeamDashboardView L141) both use "Announcements". | Change to `"Announcements"`. |

---

## 4. Inconsistent Naming Across Views (🔴 High)

### 4a. "Leaderboard" vs "Rankings"

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 10 | `TeamDashboardView.swift` | 135 | `Label("Leaderboard", systemImage: "trophy")` | Toolbar button says "Leaderboard". | — |
| 10 | `TeamDashboardView.swift` | 416 | `quickActionButton(title: "Rankings", icon: "trophy", color: .orange)` | Quick action button says "Rankings" for the **same** action (`showLeaderboard = true`). | Change to `"Leaderboard"` for consistency. |
| 10 | `ProfessorLeaderboardView.swift` | 93 | `.navigationTitle("Leaderboard")` | Nav title says "Leaderboard". | Consistent with toolbar, but not with quick action button. |
| 10 | `ProfessorLeaderboardView.swift` | 147 | `Text("Team Rankings")` | Section header says "Team Rankings" — a third term for the same concept. | Change to `"Leaderboard"` or `"Team Leaderboard"`. |

### 4b. "Monitor" tab vs "Active Session" title

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 11 | `ProfessorTabView.swift` | 15 | `case activeSession = "Monitor"` | Tab label says "Monitor". | — |
| 11 | `ProfessorTabView.swift` | 151 | `.navigationTitle("Active Session")` | The no-active-session fallback view has nav title "Active Session". Two different terms for the same tab. | Change tab rawValue to `"Monitor"` and nav title to `"Monitor"`, OR change tab to `"Active Session"`. |

### 4c. Scorecard metric labels vs. metrics grid titles

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 12 | `TeamDashboardView.swift` | 271 | `scorecardMetric(label: "S/Q", ...)` | Scorecard uses "S/Q" but metrics grid (L333) uses "S/Q Rating" for the same data. | Standardize to `"S/Q Rating"` in both, or `"S/Q"` in both. |
| 12 | `TeamDashboardView.swift` | 333 | `MetricCard(title: "S/Q Rating", ...)` | — | — |
| 12 | `TeamDashboardView.swift` | 279 | `scorecardMetric(label: "Cash", ...)` | Scorecard uses "Cash" but metrics grid (L325) uses "Cash Balance" for the same data. | Standardize to `"Cash"` or `"Cash Balance"` in both. |
| 12 | `TeamDashboardView.swift` | 325 | `MetricCard.currency(title: "Cash Balance", ...)` | — | — |
| 12 | `TeamDashboardView.swift` | 264 | `Text("Score: \(...)/100")` | Scorecard shows "Score: X/100" but metrics grid (L337) shows "Investor Score" for the same data. | Use `"Investor Score"` in the scorecard header (already says "Investor Scorecard" at L261). |
| 12 | `TeamDashboardView.swift` | 337 | `MetricCard(title: "Investor Score", ...)` | — | — |

---

## 5. AboutView vs. DecisionInput Terminology Mismatch (🔴 High)

The AboutView "Decision Guide" card titles don't match the tab labels or section titles in DecisionInput.

| # | File | Line | AboutView Card Title | DecisionInput Tab | DecisionInput Section Title | Issue |
|---|------|------|---------------------|-------------------|---------------------------|-------|
| 13 | `AboutView.swift` | 94 | `"Pricing (4 Channels)"` | `"Pricing"` | `"Pricing & Sales"` | Three different names for the same concept. AboutView says "4 Channels" but Amazon has its own separate card (L101) and its own tab. |
| 13 | `AboutView.swift` | 101 | `"Amazon Marketplace"` | `"Amazon"` | *(shows PricingSectionView)* | AboutView has a dedicated Amazon card, but the Amazon tab shows all pricing. |
| 13 | `AboutView.swift` | 108 | `"Product Design"` | `"Product"` | `"Product Design (S/Q Rating)"` | Three different names. |
| 13 | `AboutView.swift` | 115 | `"Marketing & Demand"` | `"Marketing"` | `"Marketing & Distribution"` | Three different names. "Demand" vs "Distribution" convey different concepts. |
| 13 | `AboutView.swift` | 122 | `"Social Media & Influencers"` | `"Social"` | `"Social Media Marketing"` | Three different names. |
| 13 | `AboutView.swift` | 129 | `"Workforce"` | `"Workforce"` | `"Workforce Compensation"` | Two names; minor. |
| 13 | `AboutView.swift` | 143 | `"CSR & Image"` | `"CSR"` | `"Corporate Citizenship"` | Three different names. |
| 13 | `AboutView.swift` | 150 | `"Finance"` | `"Finance"` | `"Finance"` | ✅ Consistent. |
| 13 | `AboutView.swift` | 136 | `"Production"` | `"Production"` | `"Production"` | ✅ Consistent. |

**Suggested Fix:** Create a single canonical name for each category and use it everywhere (tab label, section title, AboutView card title). Recommended canonical names:

| Category | Canonical Name |
|----------|---------------|
| Pricing | `Pricing & Sales` |
| Product | `Product Design` |
| Marketing | `Marketing & Distribution` |
| Amazon | `Amazon Marketplace` |
| Social Media | `Social Media & Influencers` |
| Workforce | `Workforce` |
| Production | `Production` |
| CSR | `CSR & Image` |
| Finance | `Finance` |

---

## 6. App Name Inconsistency (🟡 Medium)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 14 | `AboutView.swift` | 22 | `"About BizSim AI"` | App name with space: "BizSim AI". | Pick one: "BizSim AI" (with space) or "BizSimAI" (no space). The Xcode project name and file headers use "BizSimAI" (no space). If the user-facing brand is "BizSim AI", update all internal references; otherwise, remove the space. |
| 14 | `AboutView.swift` | 37 | `Text("BizSim AI")` | Same inconsistency. | — |
| 14 | `AboutView.swift` | 69 | `"BizSim AI is a marketplace simulation..."` | Same inconsistency. | — |
| 14 | `AboutView.swift` | 270 | `"AI Coaching powered by Claude"` | Uses "AI" separately. Not directly inconsistent but worth noting the brand name should be standardized. | — |

---

## 7. Column Header Abbreviation Inconsistency (🟡 Medium)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 15 | `ProfessorLeaderboardView.swift` | 227 | `columnHeader("Mkt Share", width: 90)` | Column header abbreviates "Market Share" to "Mkt Share", but the sort enum (L17) and picker (L177) use the full "Market Share". | Change to `"Market Share"` (widen column from 90 to 110) or accept the abbreviation and update the enum/picker to match. |

---

## 8. Stale Documentation Comment (🟢 Low)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 16 | `DecisionInputViewModel.swift` | 37–38 | `/// Manages 7 decision categories: Pricing, Product Design, Marketing, Workforce, Production, CSR, and Finance...` | Says "7 decision categories" but the enum (L6–16) defines **9** categories (Pricing, Product, Marketing, Amazon, Social, Workforce, Production, CSR, Finance). Missing: Amazon, Social Media. | Update to: `Manages 9 decision categories: Pricing, Product Design, Marketing, Amazon, Social Media, Workforce, Production, CSR, and Finance.` |

---

## 9. Odd/Confusing Description Text (🟡 Medium)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 17 | `SocialMediaSectionView.swift` | 46 | `"Trust & credibility. Builds long-term brand perception and S/Q awareness."` | "S/Q awareness" is not a meaningful term — S/Q is a rating, not something customers are "aware" of. | Change to `"Trust & credibility. Builds long-term brand perception and product awareness."` |
| 18 | `AboutView.swift` | 94–97 | Card title `"Pricing (4 Channels)"` with description mentioning all 4 channels including Amazon, followed by a separate card (L101) titled `"Amazon Marketplace"` | The Pricing card says it covers "wholesale, Amazon, internet, and private-label prices" but then a separate card describes Amazon in detail. This is redundant and implies Amazon is both a sub-item of Pricing and a standalone category. | Remove Amazon mention from the Pricing card description, or remove the separate Amazon card. Choose one structure. |
| 19 | `AboutView.swift` | 69 | `"...strategic decisions across pricing, production, marketing, workforce, and finance."` | Lists 5 categories but the app has 9 tabs (missing: Amazon, Social Media, CSR, Product Design). | Update to: `"...strategic decisions across pricing, product design, marketing, Amazon, social media, workforce, production, CSR, and finance."` |

---

## 10. Inconsistent "History" Labeling (🟡 Medium)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 20 | `TeamDashboardView.swift` | 132 | `Label("History", systemImage: "chart.xyaxis.line")` | Toolbar button says "History". | — |
| 20 | `TeamDashboardView.swift` | 413 | `quickActionButton(title: "History", ...)` | Quick action button also says "History". | Consistent with toolbar. ✅ |
| 20 | `PerformanceHistoryView.swift` | 22 | `.navigationTitle("Performance History")` | The view title is "Performance History" but the buttons that open it say just "History". | Minor — acceptable as shorthand. Consider `"Performance History"` on the button for clarity, or leave as-is. |

---

## 11. Missing Localization (🟢 Low)

| # | File | Lines | Issue | Suggested Fix |
|---|------|-------|-------|---------------|
| 21 | All files | All user-facing strings | The project has `.lproj` directories for 7 languages (en, es, pt-BR, fr, de, ja, zh-Hans) but **zero** strings use `NSLocalizedString`, `String(localized:)`, or a String Catalog. Every string is hardcoded in English. | This is a known architecture gap. If localization is intended, all user-facing strings should be migrated to `String(localized:)` or a `.xcstrings` catalog. Flag as a future task. |

---

## 12. Missing Accessibility Labels (🟢 Low)

| # | File | Lines | Issue | Suggested Fix |
|---|------|-------|-------|---------------|
| 22 | `DecisionInputCategoryPicker.swift` | 18–35 | Category picker buttons have no `.accessibilityLabel`. The icon (SF Symbol name like "tag") is rendered as text but is not meaningful to VoiceOver. | Add `.accessibilityLabel(category.rawValue)` to each button. |
| 23 | `ProfessorLeaderboardView.swift` | 184–191 | Sort direction toggle button has no accessibility label — only an arrow icon. | Add `.accessibilityLabel(sortAscending ? "Sort Ascending" : "Sort Descending")`. |
| 24 | `TeamDashboardView.swift` | 243–248 | Round progress capsules have no accessibility label describing round state. | Add `.accessibilityLabel("Round \(round) \(round <= backendCurrentRound ? "complete" : "pending")")`. |

---

## 13. ProfessorLeaderboardView "Live" Badge Always Shows (🟡 Medium)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 25 | `ProfessorLeaderboardView.swift` | 158 | `StatusBadge(text: "Live", color: .green, icon: "circle.fill", size: .regular)` | The "Live" badge is hardcoded and always shows green, regardless of whether the session is actually live or connected to a backend. This is misleading for offline/demo sessions. | Conditionally show "Live" (green) when `isBackendSession && isOnline`, otherwise show "Offline" (gray) or hide the badge. |

---

## 14. Duplicate "History" Button (🟢 Low)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 26 | `TeamDashboardView.swift` | 131–133 & 413–415 | Toolbar: `Label("History", ...)` and Quick Action: `quickActionButton(title: "History", ...)` | Both the toolbar and the quick action section have a "History" button that does the same thing (`showHistory = true`). This is redundant UI. | Remove one or differentiate (e.g., remove from toolbar and keep as quick action, or vice versa). |

---

## 15. Alert Message Clarity (🟡 Medium)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 27 | `DecisionInputView.swift` | 74 | `"Your decisions will be restored to the values from when you opened this screen."` | "Opened this screen" is informal. Also "this screen" is ambiguous — could refer to the DecisionInputView or the overall app. | Change to: `"Your decisions will be restored to the values from when you opened this decision form."` |
| 28 | `DecisionInputViewModel.swift` | 451 | `"Your backend team could not be identified. Please leave and join the session again."` | "Backend team" is a technical term that students won't understand. "Leave and join" is also vague. | Change to: `"Your team could not be found on the server. Please leave the session and rejoin with your session code."` |
| 29 | `DecisionInputViewModel.swift` | 543 | `"Decision was not submitted: \(UserFriendlyError.message(for: error))"` | "Decision was not submitted" is passive voice and slightly awkward. | Change to: `"Failed to submit decisions: \(UserFriendlyError.message(for: error))"` |

---

## 16. Inconsistent Button Style/Placement (🟡 Medium)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 30 | `TeamDashboardView.swift` | 127–146 | Toolbar has 6 buttons: Leave Session, History, Leaderboard, AI Coach, Announcements, Export PDF | On iPhone, 6 toolbar buttons may overflow and become hard to tap. "Leave Session" and "Export PDF" are destructive/secondary actions mixed with navigation actions. | Consider grouping: primary navigation in toolbar (History, Leaderboard, AI Coach, Announcements), and secondary actions (Leave Session, Export PDF) in a menu or settings. |

---

## 17. Unused Sample Data Function (🟢 Low)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 31 | `PerformanceHistoryView.swift` | 286–312 | `private func loadSampleData()` | Dead code — function is never called. Contains hardcoded sample data that could confuse future developers. | Remove the function or mark it `#if DEBUG`. |

---

## 18. NSLog Debug Statements Left in Production Code (🟢 Low)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 32 | `TeamDashboardView.swift` | 98–110 | 13 `NSLog` statements in `.onAppear` | These are debug logging statements that should use `os.Logger` (as done in ProfessorLeaderboardView) or be removed for production. They clutter the console and may leak internal state info. | Replace with `Logger.debug` calls or remove entirely. |

---

## 19. "Satisfaction" Column in Professor Leaderboard (🟡 Medium)

| # | File | Line | Current Text | Issue | Suggested Fix |
|---|------|------|-------------|-------|---------------|
| 33 | `ProfessorLeaderboardView.swift` | 18, 228 | `case satisfaction = "Satisfaction"` / `columnHeader("Satisfaction", ...)` | The column is labeled "Satisfaction" (implying customer satisfaction) but the Investor Scorecard (the primary scoring mechanism) does not include satisfaction as a metric. This may confuse professors who expect to see scorecard-relevant metrics. | Either rename to `"Cust. Sat."` with a tooltip, or replace with an Investor Score column that aligns with the scorecard. Alternatively, add Investor Score as an additional column. |

---

## Consolidated Recommendations

### Quick Wins (High Impact, Low Effort)
1. **Fix tab labels** — Change `"Social"` → `"Social Media"`, `"Announce"` → `"Announcements"` in ProfessorTabView. Align all tab labels with their section titles.
2. **Fix "Rankings" → "Leaderboard"** in TeamDashboardView quick action button (L416).
3. **Fix "Monitor" vs "Active Session"** — pick one term and use it in both the tab and nav title.
4. **Fix "Mkt Share" → "Market Share"** in ProfessorLeaderboardView column header.
5. **Update stale comment** in DecisionInputViewModel L37–38 from "7" to "9" categories.
6. **Fix "S/Q awareness"** → "product awareness" in SocialMediaSectionView L46.

### Medium Effort
7. **Resolve Amazon tab duplication** — Either create a dedicated Amazon-only section view or remove the Amazon tab and keep Amazon content within the Pricing section.
8. **Standardize all category names** across AboutView, DecisionInput tabs, and section headers using the canonical name table above.
9. **Fix the "Live" badge** in ProfessorLeaderboardView to reflect actual connection state.
10. **Fix user-facing error messages** — Replace "backend team" with plain language students understand.

### Long-Term
11. **Implement localization** — Migrate all user-facing strings to `String(localized:)` or a String Catalog, leveraging the existing `.lproj` infrastructure.
12. **Add accessibility labels** to interactive elements missing them.
13. **Replace NSLog with os.Logger** for production logging.
