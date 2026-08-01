package com.practenture.android

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.view.WindowCompat
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.edit
import androidx.credentials.ClearCredentialStateRequest
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.NoCredentialException
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.google.android.libraries.identity.googleid.GoogleIdTokenParsingException
import com.practenture.android.data.PractentureRepository
import com.practenture.android.network.PlayerDecision
import com.practenture.android.security.SecureTokenStore
import com.practenture.android.security.TokenStore
import kotlinx.coroutines.*
import retrofit2.HttpException
import java.io.IOException
import java.util.UUID

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = true
            isAppearanceLightNavigationBars = true
        }
        val prefs = getSharedPreferences("practenture", Context.MODE_PRIVATE)
        val tokenStore = SecureTokenStore(applicationContext)
        prefs.getString("token", null)?.takeIf { it.isNotBlank() }?.let { legacyToken ->
            if (tokenStore.accessToken.isNullOrBlank()) tokenStore.accessToken = legacyToken
            prefs.edit { remove("token") }
        }
        setContent { 
            MaterialTheme { 
                val prefsState = remember { prefs }
                val secureTokens = remember { tokenStore }
                PractentureApp(prefsState, secureTokens)
            }
        }
    }
}

@Composable
private fun PractentureApp(prefs: android.content.SharedPreferences, tokenStore: TokenStore) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()
    val credentialManager = remember(context) { CredentialManager.create(context) }
    var token by remember { mutableStateOf(tokenStore.accessToken.orEmpty()) }
    var role by remember { mutableStateOf(prefs.getString("role", "") ?: "") }
    var userId by remember { mutableStateOf(prefs.getString("userId", "") ?: "") }
    var mustChangePassword by remember { mutableStateOf(prefs.getBoolean("mustChangePassword", false)) }
    val logout: () -> Unit = {
        tokenStore.clear()
        prefs.edit { clear() }
        token = ""
        role = ""
        userId = ""
        mustChangePassword = false
        scope.launch {
            try {
                credentialManager.clearCredentialState(ClearCredentialStateRequest())
            } catch (_: Exception) {
                // Local session state is authoritative for logout; provider cleanup
                // is best-effort so an unavailable provider cannot trap the user.
            }
        }
    }
    if (token.isBlank()) LoginScreen { auth ->
        tokenStore.accessToken = auth.accessToken
        tokenStore.refreshToken = auth.refreshToken
        prefs.edit {
            putString("role", auth.role)
            putString("userId", auth.userId)
            putBoolean("mustChangePassword", auth.mustChangePassword)
        }
        token = auth.accessToken
        role = auth.role
        userId = auth.userId
        mustChangePassword = auth.mustChangePassword
    } else if (mustChangePassword) PasswordChangeScreen(
        tokenStore = tokenStore,
        onChanged = {
            logout()
        },
        onLogout = logout,
    ) else SessionScreen(tokenStore, role, userId, prefs, logout)
}

@Composable
private fun LoginScreen(onLogin: (com.practenture.android.network.LoginResponse) -> Unit) {
    val scope = rememberCoroutineScope()
    val repo = remember { PractentureRepository.create() }
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var mfaCode by remember { mutableStateOf("") }
    var professorCode by remember { mutableStateOf("") }
    var mfaRequired by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("Sign in with your Practenture account") }
    var busy by remember { mutableStateOf(false) }
    
    val context = androidx.compose.ui.platform.LocalContext.current
    val credentialManager = remember(context) { CredentialManager.create(context) }
    val googleServerClientId = com.practenture.android.BuildConfig.GOOGLE_SERVER_CLIENT_ID
    
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("Practenture", style = MaterialTheme.typography.headlineLarge)
        Text("Build the business. Own the decisions.")
        
        OutlinedTextField(username, { username = it }, label = { Text("Username") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(password, { password = it }, label = { Text("Password") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
        if (mfaRequired) {
            OutlinedTextField(
                mfaCode,
                { value ->
                    mfaCode = value.uppercase()
                        .filter { it.isLetterOrDigit() || it == '-' }
                        .take(32)
                },
                label = { Text("Authenticator or recovery code") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        
        Button(enabled = !busy && username.isNotBlank() && password.isNotBlank(), onClick = {
            busy = true
            scope.launch {
                try {
                    val auth = repo.login(
                        username.trim(),
                        password,
                        mfaCode.trim().ifBlank { null },
                    )
                    if (auth.mfaRequired) {
                        mfaRequired = true
                        message = "Enter your authenticator or recovery code"
                    } else {
                        onLogin(auth)
                        message = "Signed in"
                    }
                } catch (e: Exception) {
                    message = friendlyFailure("Sign in", e)
                }
                busy = false
            }
        }, modifier = Modifier.fillMaxWidth()) { 
            Text(if (busy) "Signing in…" else if (mfaRequired) "Verify and sign in" else "Sign in")
        }
        
        Button(enabled = !busy && googleServerClientId.isNotBlank(), onClick = {
            val activity = context.findActivity()
            if (activity == null) {
                message = "Google sign-in is unavailable"
                return@Button
            }
            busy = true
            scope.launch {
                message = try {
                    val option = GetSignInWithGoogleOption.Builder(googleServerClientId).build()
                    val request = GetCredentialRequest.Builder()
                        .addCredentialOption(option)
                        .build()
                    val response = credentialManager.getCredential(activity, request)
                    val credential = response.credential
                    if (
                        credential !is CustomCredential ||
                        credential.type != GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL
                    ) {
                        throw IllegalStateException("Unexpected credential type")
                    }
                    val googleCredential = GoogleIdTokenCredential.createFrom(credential.data)
                    val auth = repo.loginWithGoogle(
                        googleCredential.idToken,
                        professorCode.trim().ifBlank { null },
                    )
                    if (auth.professorCodeRequired) {
                        "A Professor invitation code is required for this Google account."
                    } else if (auth.accessToken.isBlank()) {
                        "Google sign-in could not establish a session."
                    } else {
                        onLogin(auth)
                        "Signed in with Google"
                    }
                } catch (_: GoogleIdTokenParsingException) {
                    "Google sign-in returned an invalid credential"
                } catch (_: NoCredentialException) {
                    "No eligible Google account is available"
                } catch (_: GetCredentialException) {
                    "Google sign-in was cancelled or unavailable"
                } catch (_: Exception) {
                    "Google sign-in failed"
                }
                busy = false
            }
        }, modifier = Modifier.fillMaxWidth()) {
            Text(if (busy) "Signing in…" else "Sign in with Google")
        }
        if (googleServerClientId.isBlank()) {
            Text(
                "Google sign-in is currently unavailable.",
                style = MaterialTheme.typography.bodySmall,
            )
        } else {
            OutlinedTextField(
                professorCode,
                { professorCode = it.uppercase() },
                label = { Text("Professor invitation code (required for new Professors)") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        
        Text(message)
    }
}

@Composable
private fun PasswordChangeScreen(
    tokenStore: TokenStore,
    onChanged: () -> Unit,
    onLogout: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val repo = remember(tokenStore) { PractentureRepository.create(tokenStore) }
    var currentPassword by remember { mutableStateOf("") }
    var newPassword by remember { mutableStateOf("") }
    var confirmation by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("Your account requires a new password before continuing.") }
    var busy by remember { mutableStateOf(false) }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text("Set a new password", style = MaterialTheme.typography.headlineLarge)
        Text(message)
        OutlinedTextField(
            currentPassword,
            { currentPassword = it },
            label = { Text("Current password") },
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            newPassword,
            { newPassword = it },
            label = { Text("New password") },
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            confirmation,
            { confirmation = it },
            label = { Text("Confirm new password") },
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        Button(
            enabled = !busy && currentPassword.isNotBlank() &&
                newPassword.isNotBlank() && newPassword == confirmation,
            onClick = {
                busy = true
                scope.launch {
                    message = try {
                        repo.changePassword(currentPassword, newPassword)
                        onChanged()
                        "Password changed"
                    } catch (error: Exception) {
                        friendlyFailure("Password change", error)
                    }
                    busy = false
                }
            },
            modifier = Modifier.fillMaxWidth(),
        ) { Text(if (busy) "Changing password…" else "Change password") }
        OutlinedButton(
            enabled = !busy,
            onClick = onLogout,
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Sign out") }
    }
}

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}

@Composable
private fun SessionScreen(tokenStore: TokenStore, role: String, userId: String, prefs: android.content.SharedPreferences, onLogout: () -> Unit) {
    val scope = rememberCoroutineScope()
    val repo = remember(tokenStore) { PractentureRepository.create(tokenStore) }
    var code by remember { mutableStateOf(prefs.getString("sessionCode", "") ?: "") }
    var teamName by remember { mutableStateOf(prefs.getString("teamName", "") ?: "") }
    var teamId by remember { mutableStateOf(prefs.getString("teamId", "") ?: "") }
    var round by remember { mutableIntStateOf(prefs.getInt("round", 1)) }
    var wholesale by remember { mutableStateOf("80") }
    var internet by remember { mutableStateOf("90") }
    var amazon by remember { mutableStateOf("85") }
    var privateLabelPrice by remember { mutableStateOf("45") }
    var privateLabelUnits by remember { mutableStateOf("50") }
    var amazonAds by remember { mutableStateOf("0") }
    var materialsQuality by remember { mutableStateOf("standard") }
    var styling by remember { mutableStateOf("3000") }
    var modelsOffered by remember { mutableStateOf("3") }
    var tqm by remember { mutableStateOf("2000") }
    var production by remember { mutableStateOf("200") }
    var advertising by remember { mutableStateOf("8000") }
    var celebrity by remember { mutableStateOf("none") }
    var retailOutlets by remember { mutableStateOf("20") }
    var mailInRebate by remember { mutableStateOf("0") }
    var deliveryTime by remember { mutableStateOf("standard") }
    var freeShipping by remember { mutableStateOf("100") }
    var tiktok by remember { mutableStateOf("0") }
    var instagram by remember { mutableStateOf("0") }
    var youtube by remember { mutableStateOf("0") }
    var influencer by remember { mutableStateOf("none") }
    var baseWage by remember { mutableStateOf("25000") }
    var incentivePay by remember { mutableStateOf("0.5") }
    var trainingHours by remember { mutableStateOf("20") }
    var bestPractices by remember { mutableStateOf("1000") }
    var overtime by remember { mutableStateOf("0") }
    var csr by remember { mutableStateOf("2000") }
    var dividends by remember { mutableStateOf("0.5") }
    var newLoan by remember { mutableStateOf("0") }
    var sharesBuyback by remember { mutableStateOf("0") }
    var sharesIssued by remember { mutableStateOf("0") }
    var fulfillment by remember { mutableStateOf("fbm") }
    var sessionName by remember { mutableStateOf("Business Strategy Lab") }
    var sessionRounds by remember { mutableStateOf("8") }
    var aiCompetitors by remember { mutableStateOf("3") }
    var maxHumanTeams by remember { mutableStateOf("20") }
    var createIdempotencyKey by remember { mutableStateOf(UUID.randomUUID().toString()) }
    var announcement by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("Ready") }
    var busy by remember { mutableStateOf(false) }
    
    fun runAction(block: suspend () -> String) {
        busy = true
        scope.launch {
            message = try {
                block()
            } catch (e: Exception) {
                if (
                    e is HttpException && e.code() == 401 &&
                    tokenStore.refreshToken.isNullOrBlank()
                ) {
                    onLogout()
                }
                friendlyFailure("Request", e)
            }
            busy = false
        }
    }
    
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column { 
                Text("Practenture", style = MaterialTheme.typography.headlineMedium)
                Text("$role · $userId", style = MaterialTheme.typography.bodySmall)
            }
            TextButton(onClick = onLogout) { Text("Logout") }
        }
        
        OutlinedTextField(code, { code = it.uppercase() }, label = { Text("Session code") }, modifier = Modifier.fillMaxWidth())

        if (role.lowercase() in setOf("professor", "owner")) {
            Text("Professor command center", style = MaterialTheme.typography.titleLarge)
            OutlinedButton(enabled = !busy, onClick = { runAction {
                val sessions = repo.dashboardSessions().sessions
                if (sessions.isNotEmpty()) {
                    code = sessions.first().code
                    prefs.edit { putString("sessionCode", code) }
                }
                sessions.joinToString("\n") {
                    "${it.code} · ${it.name} · ${it.state} · ${it.currentRound}/${it.totalRounds}"
                }.ifBlank { "No sessions yet" }
            } }, modifier = Modifier.fillMaxWidth()) { Text("Load my sessions") }

            OutlinedTextField(sessionName, { sessionName = it }, label = { Text("New session name") }, modifier = Modifier.fillMaxWidth())
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                DecisionField("Rounds", sessionRounds, Modifier.weight(1f)) { sessionRounds = it }
                DecisionField("AI teams", aiCompetitors, Modifier.weight(1f)) { aiCompetitors = it }
                DecisionField("Human teams", maxHumanTeams, Modifier.weight(1f)) { maxHumanTeams = it }
            }
            Button(
                enabled = !busy && sessionName.isNotBlank() &&
                    sessionRounds.toIntOrNull() in 1..50 &&
                    aiCompetitors.toIntOrNull() in 0..20 &&
                    maxHumanTeams.toIntOrNull() in 1..100,
                onClick = { runAction {
                    val created = repo.createSession(
                        sessionName.trim(),
                        sessionRounds.toInt(),
                        aiCompetitors.toInt(),
                        maxHumanTeams.toInt(),
                        createIdempotencyKey,
                    )
                    code = created.code
                    prefs.edit { putString("sessionCode", code) }
                    createIdempotencyKey = UUID.randomUUID().toString()
                    "Created ${created.code}; students can now join"
                } },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Create session") }

            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(enabled = !busy && code.isNotBlank(), onClick = { runAction {
                    val started = repo.startSession(code)
                    round = 1
                    "Started ${started.code}"
                } }, modifier = Modifier.weight(1f)) { Text("Start") }
                OutlinedButton(enabled = !busy && code.isNotBlank(), onClick = { runAction {
                    repo.endSession(code)
                    "Ended $code"
                } }, modifier = Modifier.weight(1f)) { Text("End") }
            }
        }
        
        if (role.lowercase() == "student") {
            OutlinedTextField(teamName, { teamName = it }, label = { Text("Team name") }, modifier = Modifier.fillMaxWidth())
            Button(enabled = !busy && code.isNotBlank() && teamName.isNotBlank(), onClick = { runAction {
                val joined = repo.join(code, teamName.trim(), userId)
                teamId = joined.teamId
                teamName = joined.teamName
                round = joined.round
                prefs.edit {
                    putString("sessionCode", code)
                    putString("teamName", teamName)
                    putString("teamId", teamId)
                    putInt("round", round)
                }
                "Joined ${joined.teamName} · round ${joined.round} · ${joined.state}"
            } }, modifier = Modifier.fillMaxWidth()) { 
                Text(if (teamId.isBlank()) "Join session" else "Rejoin session") 
            }
        }
        
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(enabled = !busy && code.isNotBlank(), onClick = { runAction {
                val s = repo.status(code)
                round = s.currentRound
                prefs.edit { putInt("round", round) }
                "${s.state} · round ${s.currentRound}/${s.totalRounds} · ${s.teamsSubmitted}/${s.totalTeams} submitted"
            } }, modifier = Modifier.weight(1f)) { Text("Refresh") }
            OutlinedButton(enabled = !busy && code.isNotBlank(), onClick = { runAction {
                val l = repo.leaderboard(code)
                l.leaderboard.joinToString("\n") { "#${it.rank ?: "–"} ${it.teamName}: ${"%.1f".format(it.totalScore)}" }.ifBlank { "No leaderboard results yet" }
            } }, modifier = Modifier.weight(1f)) { Text("Leaderboard") }
        }
        
        if (role.lowercase() == "student" && teamId.isNotBlank()) {
            Text("Round $round decision", style = MaterialTheme.typography.titleLarge)
            Text("Pricing", style = MaterialTheme.typography.titleMedium)
            DecisionField("Wholesale price", wholesale) { wholesale = it }
            DecisionField("Internet price", internet) { internet = it }
            DecisionField("Amazon price", amazon) { amazon = it }
            DecisionField("Private-label bid price", privateLabelPrice) { privateLabelPrice = it }
            DecisionField("Private-label maximum units", privateLabelUnits) { privateLabelUnits = it }
            DecisionField("Amazon advertising budget", amazonAds) { amazonAds = it }
            Text("Product and quality", style = MaterialTheme.typography.titleMedium)
            DecisionField("Materials quality (standard/superior)", materialsQuality) { materialsQuality = it.lowercase() }
            DecisionField("Styling budget", styling) { styling = it }
            DecisionField("Models offered", modelsOffered) { modelsOffered = it }
            DecisionField("TQM investment", tqm) { tqm = it }
            Text("Marketing and distribution", style = MaterialTheme.typography.titleMedium)
            DecisionField("Advertising budget", advertising) { advertising = it }
            DecisionField("Celebrity endorsement (none/local/national/global)", celebrity) { celebrity = it.lowercase() }
            DecisionField("Retail outlets", retailOutlets) { retailOutlets = it }
            DecisionField("Mail-in rebate", mailInRebate) { mailInRebate = it }
            DecisionField("Delivery time (standard/rush)", deliveryTime) { deliveryTime = it.lowercase() }
            DecisionField("Free-shipping threshold", freeShipping) { freeShipping = it }
            DecisionField("TikTok budget", tiktok) { tiktok = it }
            DecisionField("Instagram budget", instagram) { instagram = it }
            DecisionField("YouTube budget", youtube) { youtube = it }
            DecisionField("Influencer tier (none/nano/micro/macro/mega)", influencer) { influencer = it.lowercase() }
            Text("Workforce and production", style = MaterialTheme.typography.titleMedium)
            DecisionField("Base wage", baseWage) { baseWage = it }
            DecisionField("Incentive pay", incentivePay) { incentivePay = it }
            DecisionField("Training hours", trainingHours) { trainingHours = it }
            DecisionField("Best-practices investment", bestPractices) { bestPractices = it }
            DecisionField("Production quantity", production) { production = it }
            DecisionField("Overtime percent", overtime) { overtime = it }
            Text("Finance and responsibility", style = MaterialTheme.typography.titleMedium)
            DecisionField("CSR investment", csr) { csr = it }
            DecisionField("Dividends per share", dividends) { dividends = it }
            DecisionField("New loan amount", newLoan) { newLoan = it }
            DecisionField("Shares buyback", sharesBuyback) { sharesBuyback = it }
            DecisionField("Shares issued", sharesIssued) { sharesIssued = it }
            DecisionField("Amazon fulfillment (fbm/fba)", fulfillment) { fulfillment = it.lowercase() }
            Button(enabled = !busy, onClick = { runAction {
                val d = PlayerDecision(
                    wholesalePrice = wholesale.requireDouble("Wholesale price"),
                    internetPrice = internet.requireDouble("Internet price"),
                    amazonPrice = amazon.requireDouble("Amazon price"),
                    privateLabelBidPrice = privateLabelPrice.requireDouble("Private-label price"),
                    privateLabelMaxUnits = privateLabelUnits.requireInt("Private-label units"),
                    amazonAdBudget = amazonAds.requireDouble("Amazon advertising"),
                    materialsQuality = materialsQuality.requireChoice("Materials quality", setOf("standard", "superior")),
                    stylingBudget = styling.requireDouble("Styling budget"),
                    modelsOffered = modelsOffered.requireInt("Models offered"),
                    tqmInvestment = tqm.requireDouble("TQM investment"),
                    advertisingBudget = advertising.requireDouble("Advertising budget"),
                    celebrityEndorsement = celebrity.requireChoice("Celebrity endorsement", setOf("none", "local", "national", "global")),
                    retailOutlets = retailOutlets.requireInt("Retail outlets"),
                    mailInRebate = mailInRebate.requireDouble("Mail-in rebate"),
                    deliveryTime = deliveryTime.requireChoice("Delivery time", setOf("standard", "rush")),
                    freeShippingThreshold = freeShipping.requireDouble("Free-shipping threshold"),
                    tiktokBudget = tiktok.requireDouble("TikTok budget"),
                    instagramBudget = instagram.requireDouble("Instagram budget"),
                    youtubeBudget = youtube.requireDouble("YouTube budget"),
                    influencerTier = influencer.requireChoice("Influencer tier", setOf("none", "nano", "micro", "macro", "mega")),
                    baseWage = baseWage.requireDouble("Base wage"),
                    incentivePay = incentivePay.requireDouble("Incentive pay"),
                    trainingHours = trainingHours.requireDouble("Training hours"),
                    bestPracticesInvestment = bestPractices.requireDouble("Best-practices investment"),
                    productionQuantity = production.requireInt("Production quantity"),
                    overtimePercent = overtime.requireDouble("Overtime percent"),
                    csrInvestment = csr.requireDouble("CSR investment"),
                    dividendsPerShare = dividends.requireDouble("Dividends per share"),
                    newLoanAmount = newLoan.requireDouble("New loan amount"),
                    sharesBuyback = sharesBuyback.requireInt("Shares buyback"),
                    sharesIssued = sharesIssued.requireInt("Shares issued"),
                    fulfillmentMethod = fulfillment.requireChoice("Fulfillment", setOf("fbm", "fba")),
                )
                val response = repo.submit(code, round, teamId, d)
                if (!response.isSuccessful) error("submission HTTP ${response.code()}")
                "Decision accepted for $teamId · round $round"
            } }, modifier = Modifier.fillMaxWidth()) { Text("Submit decision") }
        }
        
        if (role.lowercase() in setOf("professor", "owner")) {
            Button(enabled = !busy && code.isNotBlank(), onClick = { runAction {
                val processed = repo.processRoundAsProfessor(code)
                "Processed round ${processed.round}; ${processed.results.size} team results"
            } }, modifier = Modifier.fillMaxWidth()) { Text("Process round atomically") }
            OutlinedTextField(
                announcement,
                { announcement = it },
                label = { Text("Announcement") },
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                enabled = !busy && code.isNotBlank() && announcement.isNotBlank(),
                onClick = { runAction {
                    repo.announce(code, announcement.trim(), userId)
                    announcement = ""
                    "Announcement sent"
                } },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Send announcement") }
        }

        OutlinedButton(enabled = !busy && code.isNotBlank(), onClick = { runAction {
            repo.announcements(code).joinToString("\n") {
                "${it.authorName}: ${it.message}"
            }.ifBlank { "No announcements" }
        } }, modifier = Modifier.fillMaxWidth()) { Text("View announcements") }
        
        OutlinedButton(enabled = !busy && code.isNotBlank(), onClick = { runAction {
            repo.results(code).toString().take(1200)
        } }, modifier = Modifier.fillMaxWidth()) { Text("View results") }
        
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        Card(Modifier.fillMaxWidth()) { Text(message, Modifier.padding(14.dp)) }
        Text("Online rounds are computed only by FastAPI. Android never runs simulation formulas or advances a round locally.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun DecisionField(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    onValueChange: (String) -> Unit,
) = OutlinedTextField(value, onValueChange, label = { Text(label) }, singleLine = true, modifier = modifier.fillMaxWidth())

private fun String.requireDouble(label: String): Double =
    toDoubleOrNull() ?: error("$label must be a number")

private fun String.requireInt(label: String): Int =
    toIntOrNull() ?: error("$label must be a whole number")

private fun String.requireChoice(label: String, choices: Set<String>): String =
    lowercase().takeIf(choices::contains)
        ?: error("$label must be one of ${choices.joinToString()}")

private fun friendlyFailure(action: String, error: Exception): String = when (error) {
    is HttpException -> when (error.code()) {
        400 -> "$action was rejected. Check the entered values."
        401 -> "Your session expired. Sign in again."
        403 -> "You do not have permission for this action."
        404 -> "The requested Practenture resource was not found."
        409 -> "$action conflicts with the current session state. Refresh and try again."
        429 -> "Too many attempts. Wait and try again."
        else -> "$action failed because the server returned ${error.code()}."
    }
    is IOException -> "$action could not reach Practenture. Check your connection and try again."
    is IllegalArgumentException, is IllegalStateException ->
        error.message ?: "$action could not be completed."
    else -> "$action could not be completed. Try again."
}