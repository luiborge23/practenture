package com.practenture.android

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.credentials.ClearCredentialStateRequest
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialException
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.google.android.libraries.identity.googleid.GoogleIdTokenParsingException
import com.practenture.android.data.PractentureRepository
import com.practenture.android.network.PlayerDecision
import kotlinx.coroutines.*

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences("practenture", MODE_PRIVATE)
        setContent { 
            MaterialTheme { 
                val prefsState = remember { prefs }
                practentureApp(prefsState)
            }
        }
    }
}

@Composable
private fun practentureApp(prefs: android.content.SharedPreferences) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()
    val credentialManager = remember(context) { CredentialManager.create(context) }
    var token by remember { mutableStateOf(prefs.getString("token", "") ?: "") }
    var role by remember { mutableStateOf(prefs.getString("role", "") ?: "") }
    var userId by remember { mutableStateOf(prefs.getString("userId", "") ?: "") }
    if (token.isBlank()) LoginScreen { auth ->
        prefs.edit().putString("token", auth.accessToken).putString("role", auth.role).putString("userId", auth.userId).apply()
        token = auth.accessToken
        role = auth.role
        userId = auth.userId
    } else SessionScreen(token, role, userId, prefs) {
        prefs.edit().clear().apply()
        token = ""
        role = ""
        userId = ""
        scope.launch {
            try {
                credentialManager.clearCredentialState(ClearCredentialStateRequest())
            } catch (_: Exception) {
                // Local session state is authoritative for logout; provider cleanup
                // is best-effort so an unavailable provider cannot trap the user.
            }
        }
    }
}

@Composable
private fun LoginScreen(onLogin: (com.practenture.android.network.LoginResponse) -> Unit) {
    val scope = rememberCoroutineScope()
    val repo = remember { PractentureRepository.create() }
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("Sign in with your Practenture account") }
    var busy by remember { mutableStateOf(false) }
    
    val context = androidx.compose.ui.platform.LocalContext.current
    val credentialManager = remember(context) { CredentialManager.create(context) }
    val googleServerClientId = com.practenture.android.BuildConfig.GOOGLE_SERVER_CLIENT_ID
    
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("Practenture", style = MaterialTheme.typography.headlineLarge)
        Text("Backend-authoritative Android client")
        Text(com.practenture.android.BuildConfig.PRACTENTURE_BASE_URL, style = MaterialTheme.typography.bodySmall)
        
        OutlinedTextField(username, { username = it }, label = { Text("Username") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(password, { password = it }, label = { Text("Password") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
        
        Button(enabled = !busy && username.isNotBlank() && password.isNotBlank(), onClick = {
            busy = true
            scope.launch {
                try {
                    onLogin(repo.login(username.trim(), password))
                    message = "Signed in"
                } catch (e: Exception) {
                    message = "Login failed: ${e.message}"
                }
                busy = false
            }
        }, modifier = Modifier.fillMaxWidth()) { 
            Text(if (busy) "Signing in…" else "Sign in") 
        }
        
        OutlinedButton(enabled = !busy, onClick = {
            scope.launch {
                message = try { 
                    if (repo.health()) "Backend online" else "Backend unavailable" 
                } catch (e: Exception) { 
                    "Backend error: ${e.message}" 
                }
            }
        }, modifier = Modifier.fillMaxWidth()) { 
            Text("Check backend") 
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
                    onLogin(repo.loginWithGoogle(googleCredential.idToken))
                    "Signed in with Google"
                } catch (_: GoogleIdTokenParsingException) {
                    "Google sign-in returned an invalid credential"
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
                "Google sign-in requires PRACTENTURE_GOOGLE_SERVER_CLIENT_ID.",
                style = MaterialTheme.typography.bodySmall,
            )
        }
        
        Text(message)
    }
}

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}

@Composable
private fun SessionScreen(token: String, role: String, userId: String, prefs: android.content.SharedPreferences, onLogout: () -> Unit) {
    val scope = rememberCoroutineScope()
    val repo = remember(token) { PractentureRepository.create(token) }
    var code by remember { mutableStateOf(prefs.getString("sessionCode", "") ?: "") }
    var teamName by remember { mutableStateOf(prefs.getString("teamName", "") ?: "") }
    var teamId by remember { mutableStateOf(prefs.getString("teamId", "") ?: "") }
    var round by remember { mutableIntStateOf(prefs.getInt("round", 1)) }
    var wholesale by remember { mutableStateOf("80") }
    var internet by remember { mutableStateOf("90") }
    var amazon by remember { mutableStateOf("85") }
    var production by remember { mutableStateOf("200") }
    var advertising by remember { mutableStateOf("8000") }
    var message by remember { mutableStateOf("Ready") }
    var busy by remember { mutableStateOf(false) }
    
    fun runAction(block: suspend () -> String) {
        busy = true
        scope.launch {
            message = try { block() } catch (e: Exception) { "Error: ${e.message}" }
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
        
        if (role.lowercase() == "student") {
            OutlinedTextField(teamName, { teamName = it }, label = { Text("Team name") }, modifier = Modifier.fillMaxWidth())
            Button(enabled = !busy && code.isNotBlank() && teamName.isNotBlank(), onClick = { runAction {
                val joined = repo.join(code, teamName.trim(), userId)
                teamId = joined.teamId
                teamName = joined.teamName
                round = joined.round
                prefs.edit().putString("sessionCode", code).putString("teamName", teamName).putString("teamId", teamId).putInt("round", round).apply()
                "Joined ${joined.teamName} · round ${joined.round} · ${joined.state}"
            } }, modifier = Modifier.fillMaxWidth()) { 
                Text(if (teamId.isBlank()) "Join session" else "Rejoin session") 
            }
        }
        
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(enabled = !busy && code.isNotBlank(), onClick = { runAction {
                val s = repo.status(code)
                round = s.currentRound
                prefs.edit().putInt("round", round).apply()
                "${s.state} · round ${s.currentRound}/${s.totalRounds} · ${s.teamsSubmitted}/${s.totalTeams} submitted"
            } }, modifier = Modifier.weight(1f)) { Text("Refresh") }
            OutlinedButton(enabled = !busy && code.isNotBlank(), onClick = { runAction {
                val l = repo.leaderboard(code)
                l.leaderboard.joinToString("\n") { "#${it.rank ?: "–"} ${it.teamName}: ${"%.1f".format(it.totalScore)}" }.ifBlank { "No leaderboard results yet" }
            } }, modifier = Modifier.weight(1f)) { Text("Leaderboard") }
        }
        
        if (role.lowercase() == "student" && teamId.isNotBlank()) {
            Text("Round $round decision", style = MaterialTheme.typography.titleLarge)
            DecisionField("Wholesale price", wholesale) { wholesale = it }
            DecisionField("Internet price", internet) { internet = it }
            DecisionField("Amazon price", amazon) { amazon = it }
            DecisionField("Production quantity", production) { production = it }
            DecisionField("Advertising budget", advertising) { advertising = it }
            Button(enabled = !busy, onClick = { runAction {
                val d = PlayerDecision(
                    wholesalePrice = wholesale.toDoubleOrNull() ?: 80.0,
                    internetPrice = internet.toDoubleOrNull() ?: 90.0,
                    amazonPrice = amazon.toDoubleOrNull() ?: 85.0,
                    productionQuantity = production.toIntOrNull() ?: 200,
                    advertisingBudget = advertising.toDoubleOrNull() ?: 8000.0
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
        }
        
        OutlinedButton(enabled = !busy && code.isNotBlank(), onClick = { runAction {
            repo.results(code).toString().take(1200)
        } }, modifier = Modifier.fillMaxWidth()) { Text("View results") }
        
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        Card(Modifier.fillMaxWidth()) { Text(message, Modifier.padding(14.dp)) }
        Text("Online rounds are computed only by FastAPI. Android never runs simulation formulas or advances a round locally.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun DecisionField(label: String, value: String, onValueChange: (String) -> Unit) =
    OutlinedTextField(value, onValueChange, label = { Text(label) }, singleLine = true, modifier = Modifier.fillMaxWidth())