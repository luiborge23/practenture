// MARK: - i18n Localization System (Phase 8)

import Foundation

// MARK: - Localization Manager

enum I18N {
    
    private static let userDefaults = UserDefaults.standard
    private static let defaultLocale = Locale(identifier: "en")
    
    /// Current active locale
    static var currentLocale: Locale {
        get {
            if let localeId = userDefaults.string(forKey: "practenture_locale") {
                return Locale(identifier: localeId)
            }
            return defaultLocale
        }
        set {
            userDefaults.set(newValue.identifier, forKey: "practenture_locale")
            NotificationCenter.default.post(name: I18N.localeDidChangeNotification, object: nil)
        }
    }
    
    static let localeDidChangeNotification = Notification.Name("I18N.localeDidChange")
    
    /// Supported locales
    static let supportedLocales: [Locale] = [
        Locale(identifier: "en"),   // English
        Locale(identifier: "es"),   // Spanish
        Locale(identifier: "fr"),   // French
        Locale(identifier: "de"),   // German
        Locale(identifier: "ja"),   // Japanese
        Locale(identifier: "zh-Hans"), // Chinese (Simplified)
        Locale(identifier: "ko"),   // Korean
        Locale(identifier: "pt")    // Portuguese
    ]
    
    /// Localized string with fallback
    static func localize(_ key: String) -> String {
        return NSLocalizedString(key, comment: "")
    }
    
    /// Available languages for display in settings
    static var availableLanguages: [(code: String, name: String, nativeName: String)] {
        return [
            ("en", "English", "English"),
            ("es", "Spanish", "Español"),
            ("fr", "French", "Français"),
            ("de", "German", "Deutsch"),
            ("ja", "Japanese", "日本語"),
            ("zh-Hans", "Chinese (Simplified)", "简体中文"),
            ("ko", "Korean", "한국어"),
            ("pt", "Portuguese", "Português")
        ]
    }
}

// MARK: - Localizable Keys

enum L10n {
    
    // MARK: - Login
    static let loginTitle = I18N.localize("login.title")
    static let professorLogin = I18N.localize("login.professor")
    static let studentLogin = I18N.localize("login.student")
    static let studentRegister = I18N.localize("login.register")
    static let usernamePlaceholder = I18N.localize("login.username")
    static let passwordPlaceholder = I18N.localize("login.password")
    static let studentIdPlaceholder = I18N.localize("login.studentId")
    static let fullNamePlaceholder = I18N.localize("login.fullName")
    static let teamNamePlaceholder = I18N.localize("login.teamName")
    
    // MARK: - Session
    static let enterSessionCode = I18N.localize("session.enterCode")
    static let sessionCodePlaceholder = I18N.localize("session.codePlaceholder")
    static let joinSession = I18N.localize("session.join")
    static let creatingSession = I18N.localize("session.creating")
    static let sessionCreated = I18N.localize("session.created")
    static let sessionCode = I18N.localize("session.code")
    static let totalRounds = I18N.localize("session.rounds")
    static let startSimulation = I18N.localize("session.start")
    static let endSimulation = I18N.localize("session.end")
    
    // MARK: - Dashboard
    static let teamDashboard = I18N.localize("dashboard.team")
    static let marketInfo = I18N.localize("dashboard.market")
    static let competitors = I18N.localize("dashboard.competitors")
    static let currentRound = I18N.localize("dashboard.round")
    static let yourTeam = I18N.localize("dashboard.yourTeam")
    
    // MARK: - Decisions
    static let pricing = I18N.localize("decisions.pricing")
    static let production = I18N.localize("decisions.production")
    static let marketing = I18N.localize("decisions.marketing")
    static let rd = I18N.localize("decisions.rd")
    static let financing = I18N.localize("decisions.financing")
    static let inventory = I18N.localize("decisions.inventory")
    static let submitDecision = I18N.localize("decisions.submit")
    static let decisionSubmitted = I18N.localize("decisions.submitted")
    
    // MARK: - Leaderboard
    static let leaderboardTitle = I18N.localize("leaderboard.title")
    static let rankLabel = I18N.localize("leaderboard.rank")
    static let equityLabel = I18N.localize("leaderboard.equity")
    static let profitLabel = I18N.localize("leaderboard.profit")
    static let marketShareLabel = I18N.localize("leaderboard.marketShare")
    static let sqRatingLabel = I18N.localize("leaderboard.sqRating")
    static let creditRatingLabel = I18N.localize("leaderboard.creditRating")
    static let investorScoreLabel = I18N.localize("leaderboard.investorScore")
    
    // MARK: - Settings
    static let settings = I18N.localize("settings.title")
    static let language = I18N.localize("settings.language")
    static let about = I18N.localize("settings.about")
    static let logout = I18N.localize("settings.logout")
    static let selectedLanguage = I18N.localize("settings.selectedLanguage")
    
    // MARK: - Common
    static let loading = I18N.localize("common.loading")
    static let error = I18N.localize("common.error")
    static let cancel = I18N.localize("common.cancel")
    static let confirm = I18N.localize("common.confirm")
    static let save = I18N.localize("common.save")
    static let delete = I18N.localize("common.delete")
    static let edit = I18N.localize("common.edit")
    static let retry = I18N.localize("common.retry")
    
    // MARK: - AI Coach
    static let aiCoach = I18N.localize("aiCoach.title")
    static let aiCoachTip = I18N.localize("aiCoach.tip")
    static let aiCoachHint = I18N.localize("aiCoach.hint")
    
    // MARK: - Round Results
    static let roundResultsTitle = I18N.localize("roundResults.title")
    static let roundComplete = I18N.localize("roundResults.complete")
    static let revenueLabel = I18N.localize("roundResults.revenue")
    static let profitLabelResult = I18N.localize("roundResults.profit")
    static let netIncomeLabel = I18N.localize("roundResults.netIncome")
    
    // MARK: - Announcements
    static let announcements = I18N.localize("announcements.title")
    static let sendAnnouncement = I18N.localize("announcements.send")
    static let announcementSent = I18N.localize("announcements.sent")
}

// MARK: - Localizable String Extensions

extension String {
    /// Localized string using L10n keys
    func localized() -> String {
        return I18N.localize(self)
    }
    
    /// Localized string with format arguments
    func localized(_ args: CVarArg...) -> String {
        return String(format: I18N.localize(self), arguments: args)
    }
}
