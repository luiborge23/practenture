package com.bizsimai.android

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
import com.bizsimai.android.data.BizSimRepository
import com.bizsimai.android.network.PlayerDecision
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences("bizsimai", MODE_PRIVATE)
        setContent { MaterialTheme { BizSimApp(prefs) } }
    }
}

@Composable
private fun BizSimApp(prefs: android.content.SharedPreferences) {
    var token by remember { mutableStateOf(prefs.getString("token", "") ?: "") }
    var role by remember { mutableStateOf(prefs.getString("role", "") ?: "") }
    var userId by remember { mutableStateOf(prefs.getString("userId", "") ?: "") }
    if (token.isBlank()) LoginScreen { auth ->
        token = auth.accessToken; role = auth.role; userId = auth.userId
        prefs.edit().putString("token", token).putString("role", role).putString("userId", userId).apply()
    } else SessionScreen(token, role, userId, prefs) {
        prefs.edit().clear().apply(); token = ""; role = ""; userId = ""
    }
}

@Composable
private fun LoginScreen(onLogin: (com.bizsimai.android.network.LoginResponse) -> Unit) {
    val scope = rememberCoroutineScope(); val repo = remember { BizSimRepository.create() }
    var username by remember { mutableStateOf("") }; var password by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("Sign in with your BizSimAI account") }; var busy by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("BizSimAI", style = MaterialTheme.typography.headlineLarge)
        Text("Backend-authoritative Android client")
        Text(BuildConfig.BIZSIMAI_BASE_URL, style = MaterialTheme.typography.bodySmall)
        OutlinedTextField(username, { username = it }, label = { Text("Username") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(password, { password = it }, label = { Text("Password") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
        Button(enabled = !busy && username.isNotBlank() && password.isNotBlank(), onClick = {
            busy = true; scope.launch {
                try { onLogin(repo.login(username.trim(), password)); message = "Signed in" }
                catch (e: Exception) { message = "Login failed: ${e.message}" }
                busy = false
            }
        }, modifier = Modifier.fillMaxWidth()) { Text(if (busy) "Signing in…" else "Sign in") }
        OutlinedButton(enabled = !busy, onClick = { scope.launch {
            message = try { if (repo.health()) "Backend online" else "Backend unavailable" } catch (e: Exception) { "Backend error: ${e.message}" }
        } }, modifier = Modifier.fillMaxWidth()) { Text("Check backend") }
        Text(message)
    }
}

@Composable
private fun SessionScreen(token: String, role: String, userId: String, prefs: android.content.SharedPreferences, onLogout: () -> Unit) {
    val scope = rememberCoroutineScope(); val repo = remember(token) { BizSimRepository.create(token) }
    var code by remember { mutableStateOf(prefs.getString("sessionCode", "") ?: "") }
    var teamName by remember { mutableStateOf(prefs.getString("teamName", "") ?: "") }
    var teamId by remember { mutableStateOf(prefs.getString("teamId", "") ?: "") }
    var round by remember { mutableIntStateOf(prefs.getInt("round", 1)) }
    var wholesale by remember { mutableStateOf("80") }; var internet by remember { mutableStateOf("90") }
    var amazon by remember { mutableStateOf("85") }; var production by remember { mutableStateOf("200") }
    var advertising by remember { mutableStateOf("8000") }; var message by remember { mutableStateOf("Ready") }
    var busy by remember { mutableStateOf(false) }
    fun runAction(block: suspend () -> String) { busy = true; scope.launch { message = try { block() } catch (e: Exception) { "Error: ${e.message}" }; busy = false } }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column { Text("BizSimAI", style = MaterialTheme.typography.headlineMedium); Text("$role · $userId", style = MaterialTheme.typography.bodySmall) }
            TextButton(onClick = onLogout) { Text("Logout") }
        }
        OutlinedTextField(code, { code = it.uppercase() }, label = { Text("Session code") }, modifier = Modifier.fillMaxWidth())
        if (role.lowercase() == "student") {
            OutlinedTextField(teamName, { teamName = it }, label = { Text("Team name") }, modifier = Modifier.fillMaxWidth())
            Button(enabled = !busy && code.isNotBlank() && teamName.isNotBlank(), onClick = { runAction {
                val joined = repo.join(code, teamName.trim(), userId)
                teamId = joined.teamId; teamName = joined.teamName; round = joined.round
                prefs.edit().putString("sessionCode", code).putString("teamName", teamName).putString("teamId", teamId).putInt("round", round).apply()
                "Joined ${joined.teamName} · round ${joined.round} · ${joined.state}"
            } }, modifier = Modifier.fillMaxWidth()) { Text(if (teamId.isBlank()) "Join session" else "Rejoin session") }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(enabled = !busy && code.isNotBlank(), onClick = { runAction {
                val s = repo.status(code); round = s.currentRound; prefs.edit().putInt("round", round).apply()
                "${s.state} · round ${s.currentRound}/${s.totalRounds} · ${s.teamsSubmitted}/${s.totalTeams} submitted"
            } }, modifier = Modifier.weight(1f)) { Text("Refresh") }
            OutlinedButton(enabled = !busy && code.isNotBlank(), onClick = { runAction {
                val l = repo.leaderboard(code); l.leaderboard.joinToString("\n") { "#${it.rank ?: "–"} ${it.teamName}: ${"%.1f".format(it.totalScore)}" }.ifBlank { "No leaderboard results yet" }
            } }, modifier = Modifier.weight(1f)) { Text("Leaderboard") }
        }
        if (role.lowercase() == "student" && teamId.isNotBlank()) {
            Text("Round $round decision", style = MaterialTheme.typography.titleLarge)
            DecisionField("Wholesale price", wholesale) { wholesale = it }; DecisionField("Internet price", internet) { internet = it }
            DecisionField("Amazon price", amazon) { amazon = it }; DecisionField("Production quantity", production) { production = it }
            DecisionField("Advertising budget", advertising) { advertising = it }
            Button(enabled = !busy, onClick = { runAction {
                val d = PlayerDecision(wholesalePrice = wholesale.toDoubleOrNull() ?: 80.0, internetPrice = internet.toDoubleOrNull() ?: 90.0,
                    amazonPrice = amazon.toDoubleOrNull() ?: 85.0, productionQuantity = production.toIntOrNull() ?: 200,
                    advertisingBudget = advertising.toDoubleOrNull() ?: 8000.0)
                val response = repo.submit(code, round, teamId, d)
                if (!response.isSuccessful) error("submission HTTP ${response.code()}")
                "Decision accepted for $teamId · round $round"
            } }, modifier = Modifier.fillMaxWidth()) { Text("Submit decision") }
        }
        if (role.lowercase() in setOf("professor", "owner")) {
            Button(enabled = !busy && code.isNotBlank(), onClick = { runAction {
                val processed = repo.processRoundAsProfessor(code); "Processed round ${processed.round}; ${processed.results.size} team results"
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

@Composable private fun DecisionField(label: String, value: String, onValueChange: (String) -> Unit) =
    OutlinedTextField(value, onValueChange, label = { Text(label) }, singleLine = true, modifier = Modifier.fillMaxWidth())
