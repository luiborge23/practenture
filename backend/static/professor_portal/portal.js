"use strict";

const $ = (id) => document.getElementById(id);
const API = "/api/professor-portal";
let sessions = [];
let createdCode = "";
let pendingAction = null;
let createIdempotencyKey = crypto.randomUUID();
let protectedMfaAction = "";
let currentRecoveryCodes = [];

function cookie(name) {
  const prefix = `${encodeURIComponent(name)}=`;
  return document.cookie.split(";").map((value) => value.trim())
    .find((value) => value.startsWith(prefix))?.slice(prefix.length) || "";
}

function setMessage(id, message = "") {
  const node = $(id);
  node.textContent = message;
  node.hidden = !message;
}

function errorDetail(payload, fallback) {
  if (typeof payload?.detail === "string") return payload.detail;
  if (Array.isArray(payload?.detail)) {
    return payload.detail.map((item) => item.msg || "Invalid value").join("; ");
  }
  return fallback;
}

async function request(path, options = {}, mutation = false) {
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  if (options.body) headers["Content-Type"] = "application/json";
  if (mutation) {
    const token = decodeURIComponent(cookie("practenture_professor_csrf"));
    if (!token) throw new Error("Your secure session is missing its request token. Sign in again.");
    headers["X-CSRF-Token"] = token;
  }
  const response = await fetch(path, { credentials: "same-origin", ...options, headers });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(errorDetail(payload, `Request failed (${response.status})`));
    error.status = response.status;
    throw error;
  }
  return payload;
}

function showAuth() {
  $("dashboard-view").hidden = true;
  $("auth-view").hidden = false;
  history.replaceState({}, "", "/login");
}

function showDashboard(session, activated = false) {
  $("auth-view").hidden = true;
  $("dashboard-view").hidden = false;
  $("welcome").textContent = `Signed in as ${session.name || session.userId}. Your web and iOS sessions use this same Professor identity.`;
  setMessage("activation-success", activated ? `Professor account created successfully. You are signed in as ${session.userId}.` : "");
  history.replaceState({}, "", "/dashboard");
  showSessions();
  loadProgress();
}

function selectTab(mode) {
  recoveryView("none");
  const login = mode === "login";
  $("login-form").hidden = !login;
  $("activate-form").hidden = login;
  $("login-tab").setAttribute("aria-selected", String(login));
  $("activate-tab").setAttribute("aria-selected", String(!login));
  setMessage("auth-alert");
}

function recoveryView(mode) {
  $("tabs").hidden = mode !== "none";
  $("login-form").hidden = mode !== "none";
  $("activate-form").hidden = true;
  $("forgot-form").hidden = mode !== "forgot";
  $("reset-form").hidden = mode !== "reset";
  $("reset-success").hidden = mode !== "success";
  setMessage("auth-alert");
}

function showSessions() {
  $("sessions-view").hidden = false;
  $("create-view").hidden = true;
  $("security-view").hidden = true;
  $("nav-sessions").classList.add("active");
  $("nav-create").classList.remove("active");
  $("nav-security").classList.remove("active");
}

async function showCreate() {
  $("sessions-view").hidden = true;
  $("create-view").hidden = false;
  $("security-view").hidden = true;
  $("create-form").hidden = false;
  $("create-success").hidden = true;
  $("nav-sessions").classList.remove("active");
  $("nav-create").classList.add("active");
  $("nav-security").classList.remove("active");
  setMessage("create-alert");
  updateReview();
  await loadCreationOptions();
  $("create-name").focus();
}

function showMfaPanel(panel) {
  for (const id of ["mfa-disabled-panel", "mfa-setup-panel", "mfa-enabled-panel", "mfa-protected-panel", "mfa-recovery-panel"]) {
    $(id).hidden = id !== panel;
  }
}

async function loadMfaStatus() {
  setMessage("security-alert");
  try {
    const status = await request(`${API}/mfa/status`);
    if (status.enabled) {
      $("mfa-recovery-count").textContent = `${status.recoveryCodesRemaining} unused recovery code${status.recoveryCodesRemaining === 1 ? " remains" : "s remain"}.`;
      showMfaPanel("mfa-enabled-panel");
    } else {
      showMfaPanel("mfa-disabled-panel");
    }
  } catch (error) {
    if (error.status === 401) return showAuth();
    setMessage("security-alert", error.message);
  }
}

async function showSecurity() {
  $("sessions-view").hidden = true;
  $("create-view").hidden = true;
  $("security-view").hidden = false;
  $("nav-sessions").classList.remove("active");
  $("nav-create").classList.remove("active");
  $("nav-security").classList.add("active");
  setMessage("security-alert"); setMessage("security-status");
  await loadMfaStatus();
}

function showRecoveryCodes(codes) {
  currentRecoveryCodes = [...codes];
  $("mfa-recovery-codes").textContent = codes.join("\n");
  showMfaPanel("mfa-recovery-panel");
}

function beginProtectedMfa(action) {
  protectedMfaAction = action;
  const regenerate = action === "regenerate";
  $("mfa-protected-title").textContent = regenerate ? "Replace recovery codes?" : "Disable MFA?";
  $("mfa-protected-copy").textContent = regenerate ? "Every previous recovery code will stop working immediately." : "Your account will return to password-only protection.";
  $("mfa-protected-submit").textContent = regenerate ? "Generate new codes" : "Disable MFA";
  $("mfa-protected-submit").className = `button ${regenerate ? "button-primary" : "button-danger"}`;
  $("mfa-protected-password").value = ""; $("mfa-protected-code").value = "";
  showMfaPanel("mfa-protected-panel");
}

async function loadCreationOptions() {
  try {
    const [scenarioData, classData] = await Promise.all([
      request(`${API}/scenarios`), request(`${API}/classes`),
    ]);
    const scenarioSelect = $("create-scenario");
    const previousScenario = scenarioSelect.value;
    scenarioSelect.replaceChildren();
    for (const scenario of scenarioData.scenarios || []) {
      const option = document.createElement("option");
      option.value = `${scenario.scenario_id}|${scenario.scenario_version}`;
      option.textContent = scenario.title;
      scenarioSelect.append(option);
    }
    if (previousScenario) scenarioSelect.value = previousScenario;

    const classSelect = $("create-class");
    const previousClass = classSelect.value;
    classSelect.replaceChildren(new Option("No class", ""));
    for (const item of classData.classes || []) {
      classSelect.append(new Option(item.name, item.id));
    }
    if (previousClass) classSelect.value = previousClass;
    updateReview();
  } catch (error) {
    setMessage("create-alert", error.message);
  }
}

function createValues() {
  const [scenarioId = "", scenarioVersion = ""] = $("create-scenario").value.split("|");
  return {
    name: $("create-name").value.trim(),
    classId: $("create-class").value || null,
    className: $("create-class").selectedOptions[0]?.textContent || "No class",
    courseCode: $("create-course").value.trim(),
    semester: $("create-semester").value.trim(),
    totalRounds: Number($("create-rounds").value),
    maxHumanTeams: Number($("create-max-teams").value),
    numberOfAICompetitors: Number($("create-ai").value),
    marketType: $("create-market").value,
    aiDifficulty: $("create-difficulty").value,
    scoringMetric: $("create-scoring").value,
    scenarioId,
    scenarioVersion,
    scenarioName: $("create-scenario").selectedOptions[0]?.textContent || "Not selected",
  };
}

function updateReview() {
  const values = createValues();
  const items = [
    ["Scenario", values.scenarioName], ["Session", values.name || "Not entered"],
    ["Class", values.className], ["Rounds", values.totalRounds],
    ["Human teams", values.maxHumanTeams], ["AI competitors", values.numberOfAICompetitors],
    ["Market", values.marketType], ["AI difficulty", values.aiDifficulty],
    ["Scoring", values.scoringMetric],
  ];
  $("create-review").replaceChildren(...items.map(([label, value]) => {
    const item = document.createElement("div");
    item.className = "review-item";
    const caption = document.createElement("span");
    caption.textContent = label;
    const content = document.createElement("strong");
    content.textContent = String(value);
    item.append(caption, content);
    return item;
  }));
}

function statusClass(state) {
  return `status-badge status-${String(state).toLowerCase().replace(/[^a-z]/g, "")}`;
}

function actionButton(label, action, style = "button-secondary") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `button button-small ${style}`;
  button.textContent = label;
  button.addEventListener("click", action);
  return button;
}

function cell(row, child) {
  const td = document.createElement("td");
  if (child instanceof Node) td.append(child); else td.textContent = String(child);
  row.append(td);
  return td;
}

function renderSessions() {
  $("metric-total").textContent = String(sessions.length);
  $("metric-active").textContent = String(sessions.filter((item) => item.state === "active").length);
  $("metric-teams").textContent = String(sessions.reduce((sum, item) => sum + item.humanTeams, 0));
  $("empty-state").hidden = sessions.length !== 0;
  const body = $("session-rows");
  body.replaceChildren();

  for (const item of sessions) {
    const row = document.createElement("tr");
    const identity = document.createElement("div");
    identity.className = "session-name";
    const name = document.createElement("strong"); name.textContent = item.name || `Session ${item.code}`;
    const code = document.createElement("span"); code.textContent = item.code;
    identity.append(name, code); cell(row, identity);
    const badge = document.createElement("span"); badge.className = statusClass(item.state); badge.textContent = item.state; cell(row, badge);
    cell(row, `${item.currentRound} / ${item.totalRounds}`);
    cell(row, `${item.humanTeams} / ${item.maxHumanTeams}`);
    cell(row, item.currentRoundSubmissions);
    cell(row, item.totalSubmissions);
    const actions = document.createElement("div"); actions.className = "row-actions";
    if (item.state === "creating") actions.append(actionButton("Start", () => runSessionAction(item, "start"), "button-primary"));
    if (item.state === "active") actions.append(actionButton("Process round", () => runSessionAction(item, "process-round"), "button-primary"));
    if (["creating", "active"].includes(item.state)) actions.append(actionButton("End", () => runSessionAction(item, "end")));
    if (!["finished", "completed"].includes(item.state)) actions.append(actionButton("Announce", () => announce(item)));
    const grades = document.createElement("a"); grades.className = "button button-small button-quiet"; grades.textContent = "Grades"; grades.href = `${API}/progress/${encodeURIComponent(item.code)}/grades`; actions.append(grades);
    const leaderboard = document.createElement("a"); leaderboard.className = "button button-small button-quiet"; leaderboard.textContent = "Leaderboard"; leaderboard.href = `${API}/progress/${encodeURIComponent(item.code)}/leaderboard`; actions.append(leaderboard);
    actions.append(actionButton("Delete", () => removeSession(item), "button-quiet"));
    cell(row, actions);
    body.append(row);
  }
}

async function loadProgress() {
  setMessage("workspace-alert");
  try {
    const payload = await request(`${API}/progress`);
    sessions = payload.sessions || [];
    renderSessions();
  } catch (error) {
    if (error.status === 401) return showAuth();
    setMessage("workspace-alert", error.message);
  }
}

function confirmAction({ title, message, confirmLabel = "Confirm", danger = false, inputLabel = "", requiredText = "" }) {
  return new Promise((resolve) => {
    $("dialog-title").textContent = title;
    $("dialog-message").textContent = message;
    $("dialog-confirm").textContent = confirmLabel;
    $("dialog-confirm").className = `button ${danger ? "button-danger" : "button-primary"}`;
    $("dialog-input-wrap").hidden = !inputLabel;
    $("dialog-input-label").textContent = inputLabel;
    $("dialog-input").value = "";
    const dialog = $("action-dialog");
    const close = () => {
      dialog.removeEventListener("close", close);
      resolve(dialog.returnValue === "confirm" && (!requiredText || $("dialog-input").value.trim() === requiredText));
    };
    dialog.addEventListener("close", close);
    dialog.showModal();
  });
}

async function runSessionAction(item, action) {
  const copy = action === "start"
    ? { title: "Start this simulation?", message: `Start ${item.name} at round 1? Students will be able to submit decisions.`, label: "Start session" }
    : action === "process-round"
      ? { title: `Process round ${item.currentRound}?`, message: "Practenture will reject this command if any human team is missing a decision. The backend advances the round exactly once.", label: "Process round" }
      : { title: "End this simulation?", message: "Students will no longer be able to submit decisions. Existing results and exports remain available.", label: "End session" };
  if (!await confirmAction({ title: copy.title, message: copy.message, confirmLabel: copy.label, danger: action === "end" })) return;
  await mutateSession(item, action, copy.label);
}

async function mutateSession(item, action, successVerb) {
  setMessage("workspace-alert");
  setMessage("workspace-status", `${successVerb} in progress…`);
  try {
    await request(`${API}/sessions/${encodeURIComponent(item.code)}/${action}`, { method: "POST" }, true);
    setMessage("workspace-status", `${successVerb} completed for ${item.code}.`);
    await loadProgress();
  } catch (error) {
    setMessage("workspace-status");
    setMessage("workspace-alert", error.message);
  }
}

async function announce(item) {
  const confirmed = await confirmAction({ title: `Announcement to ${item.code}`, message: "This message will be visible to every team in this session.", confirmLabel: "Send announcement", inputLabel: "Announcement message" });
  const message = $("dialog-input").value.trim();
  if (!confirmed || !message) return;
  try {
    await request(`${API}/sessions/${encodeURIComponent(item.code)}/announcements`, { method: "POST", body: JSON.stringify({ message, authorName: "Professor" }) }, true);
    setMessage("workspace-status", `Announcement sent to ${item.code}.`);
  } catch (error) { setMessage("workspace-alert", error.message); }
}

async function removeSession(item) {
  const confirmed = await confirmAction({ title: "Delete simulation permanently?", message: `This removes session ${item.code}, its decisions, and its results. This cannot be undone.`, confirmLabel: "Delete permanently", danger: true, inputLabel: `Type ${item.code} to confirm`, requiredText: item.code });
  if (!confirmed) {
    if ($("action-dialog").returnValue === "confirm") setMessage("workspace-alert", `Deletion cancelled because the confirmation did not exactly match ${item.code}.`);
    return;
  }
  try {
    await request(`${API}/sessions/${encodeURIComponent(item.code)}`, { method: "DELETE" }, true);
    setMessage("workspace-status", `Session ${item.code} was deleted.`);
    await loadProgress();
  } catch (error) { setMessage("workspace-alert", error.message); }
}

$("login-tab").addEventListener("click", () => selectTab("login"));
$("activate-tab").addEventListener("click", () => selectTab("activate"));
$("forgot-password").addEventListener("click", () => recoveryView("forgot"));
$("forgot-cancel").addEventListener("click", () => selectTab("login"));
$("reset-cancel").addEventListener("click", () => recoveryView("forgot"));
$("reset-success-login").addEventListener("click", () => selectTab("login"));

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault(); setMessage("auth-alert");
  try {
    const session = await request(`${API}/login`, { method: "POST", body: JSON.stringify({ provider: "password", username: $("login-username").value.trim(), password: $("login-password").value, mfa_code: $("login-mfa").value.trim() || null }) });
    $("login-password").value = ""; $("login-mfa").value = ""; $("login-mfa-wrap").hidden = true; $("login-mfa-help").hidden = true; showDashboard(session);
  } catch (error) {
    if (error.status === 409) {
      $("login-mfa-wrap").hidden = false; $("login-mfa-help").hidden = false; $("login-mfa").focus();
    }
    setMessage("auth-alert", error.message);
  }
});

$("activate-form").addEventListener("submit", async (event) => {
  event.preventDefault(); setMessage("auth-alert");
  if ($("activate-password").value !== $("activate-confirm").value) return setMessage("auth-alert", "Passwords do not match.");
  try {
    const username = $("activate-username").value.trim();
    const session = await request(`${API}/activate`, { method: "POST", body: JSON.stringify({ professor_code: $("activate-code").value.trim(), username, email: $("activate-email").value.trim(), name: $("activate-name").value.trim(), password: $("activate-password").value, confirm_password: $("activate-confirm").value }) });
    $("activate-password").value = ""; $("activate-confirm").value = ""; showDashboard(session, true);
  } catch (error) { setMessage("auth-alert", error.message); }
});

$("forgot-form").addEventListener("submit", async (event) => {
  event.preventDefault(); setMessage("auth-alert");
  try {
    await request("/api/auth/forgot-password", { method: "POST", body: JSON.stringify({ email: $("forgot-email").value.trim() }) });
    recoveryView("reset");
    setMessage("auth-status", "Reset request accepted. If a password account exists for that email, a new reset message was sent. Use only the newest code; earlier codes no longer work. Check Spam or Junk as well.");
  } catch (error) { setMessage("auth-alert", error.message); }
});

$("reset-form").addEventListener("submit", async (event) => {
  event.preventDefault(); setMessage("auth-alert");
  if ($("reset-password").value !== $("reset-confirm").value) return setMessage("auth-alert", "Passwords do not match.");
  try {
    await request("/api/auth/reset-password", { method: "POST", body: JSON.stringify({ token: $("reset-token").value.trim(), new_password: $("reset-password").value }) });
    $("reset-token").value = ""; $("reset-password").value = ""; $("reset-confirm").value = "";
    setMessage("auth-status"); recoveryView("success");
  } catch (error) { setMessage("auth-alert", error.message); }
});

$("logout").addEventListener("click", async () => {
  try { await request(`${API}/logout`, { method: "POST" }, true); } catch (_) { /* clear local view even if expired */ }
  showAuth(); selectTab("login");
});
$("refresh").addEventListener("click", loadProgress);
$("nav-sessions").addEventListener("click", showSessions);
$("nav-create").addEventListener("click", showCreate);
$("nav-security").addEventListener("click", showSecurity);
$("create-session").addEventListener("click", showCreate);
$("empty-create").addEventListener("click", showCreate);
$("create-cancel").addEventListener("click", showSessions);
$("open-created").addEventListener("click", async () => { showSessions(); await loadProgress(); });
$("create-another").addEventListener("click", () => { $("create-success").hidden = true; $("create-form").hidden = false; $("create-form").reset(); updateReview(); $("create-name").focus(); });
$("copy-code").addEventListener("click", async () => { await navigator.clipboard.writeText(createdCode); setMessage("workspace-status", `Join code ${createdCode} copied.`); });
$("create-form").addEventListener("input", updateReview);
$("create-form").addEventListener("change", updateReview);

$("mfa-start-form").addEventListener("submit", async (event) => {
  event.preventDefault(); setMessage("security-alert");
  try {
    const result = await request(`${API}/mfa/setup`, { method: "POST", body: JSON.stringify({ password: $("mfa-start-password").value }) }, true);
    $("mfa-start-password").value = ""; $("mfa-qr").src = result.qrCodeDataUri; $("mfa-secret").textContent = result.secret;
    showMfaPanel("mfa-setup-panel"); $("mfa-confirm-code").focus();
  } catch (error) { setMessage("security-alert", error.message); }
});

$("mfa-confirm-form").addEventListener("submit", async (event) => {
  event.preventDefault(); setMessage("security-alert");
  try {
    const result = await request(`${API}/mfa/confirm`, { method: "POST", body: JSON.stringify({ code: $("mfa-confirm-code").value.trim() }) }, true);
    $("mfa-confirm-code").value = ""; setMessage("security-status", "MFA is now enabled."); showRecoveryCodes(result.recoveryCodes);
  } catch (error) { setMessage("security-alert", error.message); }
});

$("mfa-regenerate").addEventListener("click", () => beginProtectedMfa("regenerate"));
$("mfa-disable").addEventListener("click", () => beginProtectedMfa("disable"));
$("mfa-protected-cancel").addEventListener("click", loadMfaStatus);
$("mfa-protected-form").addEventListener("submit", async (event) => {
  event.preventDefault(); setMessage("security-alert");
  const body = JSON.stringify({ password: $("mfa-protected-password").value, code: $("mfa-protected-code").value.trim() });
  try {
    if (protectedMfaAction === "regenerate") {
      const result = await request(`${API}/mfa/recovery-codes`, { method: "POST", body }, true);
      showRecoveryCodes(result.recoveryCodes);
    } else {
      await request(`${API}/mfa/disable`, { method: "POST", body }, true);
      setMessage("security-status", "MFA was disabled."); await loadMfaStatus();
    }
    $("mfa-protected-password").value = ""; $("mfa-protected-code").value = "";
  } catch (error) { setMessage("security-alert", error.message); }
});

$("mfa-download-codes").addEventListener("click", () => {
  const text = `Practenture recovery codes\nGenerated: ${new Date().toISOString()}\n\n${currentRecoveryCodes.join("\n")}\n`;
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  const link = document.createElement("a"); link.href = url; link.download = "practenture-recovery-codes.txt"; link.click(); URL.revokeObjectURL(url);
});
$("mfa-codes-saved").addEventListener("click", async () => { currentRecoveryCodes = []; $("mfa-recovery-codes").textContent = ""; await loadMfaStatus(); });

$("create-form").addEventListener("submit", async (event) => {
  event.preventDefault(); setMessage("create-alert");
  if (!event.currentTarget.reportValidity()) return;
  const values = createValues();
  const submit = $("create-submit"); submit.disabled = true; submit.textContent = "Creating securely…";
  try {
    const result = await request(`${API}/sessions`, { method: "POST", headers: { "Idempotency-Key": createIdempotencyKey }, body: JSON.stringify({ config: { name: values.name, courseCode: values.courseCode, semester: values.semester, totalRounds: values.totalRounds, numberOfAICompetitors: values.numberOfAICompetitors, marketType: values.marketType, aiDifficulty: values.aiDifficulty, scoringMetric: values.scoringMetric }, teams: [], maxHumanTeams: values.maxHumanTeams, classId: values.classId, scenarioId: values.scenarioId, scenarioVersion: values.scenarioVersion }) }, true);
    createIdempotencyKey = crypto.randomUUID();
    createdCode = result.code; $("created-code").textContent = result.code; $("create-form").hidden = true; $("create-success").hidden = false; $("create-success").focus();
    await loadProgress();
  } catch (error) { setMessage("create-alert", error.message); $("create-alert").focus(); }
  finally { submit.disabled = false; submit.textContent = "Create session"; }
});

(async function boot() {
  try { const session = await request(`${API}/session`); showDashboard(session); }
  catch (_) { showAuth(); selectTab("login"); }
})();
