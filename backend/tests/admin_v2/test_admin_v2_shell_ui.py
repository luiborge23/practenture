"""Focused contracts for the additive Admin Console V2 browser shell."""
from pathlib import Path

from fastapi.testclient import TestClient

from main import app

BACKEND = Path(__file__).resolve().parents[2]


def test_shell_references_only_local_versioned_assets_and_is_not_cached():
    with TestClient(app) as client:
        response = client.get("/admin-v2")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert 'href="/static/admin_v2/admin-v2.css?v=3"' in response.text
    assert 'href="/static/admin_v2/admin-workspaces.css?v=2"' in response.text
    assert 'src="/static/admin_v2/admin-workspaces.js?v=5"' in response.text
    assert 'src="/static/admin_v2/admin-v2.js?v=13"' in response.text
    assert "http://" not in response.text
    assert "https://" not in response.text
    assert "localStorage" not in response.text


def test_recovery_fragment_is_removed_from_browser_history_after_capture():
    script = (BACKEND / "static" / "admin_v2" / "admin-v2.js").read_text(encoding="utf-8")
    start = script.index("function showRecoveryCompletion(token)")
    body = script[start : script.index("function showAdministratorLogin", start)]
    assert 'history.replaceState(null,"",location.pathname+location.search)' in body
    assert body.index("history.replaceState") < body.index('$("recovery-token").value=token')


def test_shell_assets_exist_and_are_served_with_expected_types():
    expected = {
        "admin-v2.css": "text/css",
        "admin-v2.js": "javascript",
        "admin-workspaces.css": "text/css",
        "admin-workspaces.js": "javascript",
    }
    with TestClient(app) as client:
        for name, media_type in expected.items():
            path = BACKEND / "static" / "admin_v2" / name
            assert path.is_file(), name
            response = client.get(f"/static/admin_v2/{name}")
            assert response.status_code == 200
            assert media_type in response.headers["content-type"]


def test_operations_view_uses_the_canonical_operations_api_namespace():
    script = (BACKEND / "static" / "admin_v2" / "admin-workspaces.js").read_text(encoding="utf-8")
    for path in ("/operations/health", "/operations/backups", "/operations/restore-drills"):
        assert path in script
    for obsolete_path in ('request("/health")', 'request("/backups")', 'request("/restore-drills")'):
        assert obsolete_path not in script


def test_admin_workspaces_expose_complete_operator_actions():
    script = (BACKEND / "static" / "admin_v2" / "admin-workspaces.js").read_text(encoding="utf-8")
    for marker in (
        "renderOrganizationsWorkspace",
        "renderInvitationsWorkspace",
        "renderUsersWorkspace",
        "renderSessionsWorkspace",
        "renderAuditWorkspace",
        "renderOperationsWorkspace",
        "renderCleanupWorkspace",
        "renderAccountWorkspace",
        "Create verified backup",
        "Preview cleanup plan",
        "Export JSON",
        "Require password reset",
        "Generate replacement",
        "wsPagination",
    ):
        assert marker in script
    assert 'request(`/sessions/${' not in script


def test_account_workspace_exposes_complete_administrator_mfa_lifecycle():
    script = (BACKEND / "static" / "admin_v2" / "admin-workspaces.js").read_text(encoding="utf-8")
    for marker in (
        'request("/auth/mfa/status")',
        'request("/auth/mfa/setup"',
        'request("/auth/mfa/confirm"',
        'request("/auth/mfa/recovery-codes"',
        'request("/auth/mfa/disable"',
        "Set up Administrator MFA",
        "Replace recovery codes",
        "Disable Administrator MFA",
        "I saved these one-time recovery codes securely.",
    ):
        assert marker in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script


def test_shell_has_accessible_landmarks_and_no_inline_executable_code():
    html = (BACKEND / "templates" / "admin_v2.html").read_text(encoding="utf-8")
    for marker in ("<header", "<nav", "<main", "<aside", "<form", "aria-live="):
        assert marker in html
    assert "<script>" not in html
    assert "style=" not in html
    assert "localStorage" not in html
    assert "sessionStorage" not in html
    assert "Delete all" not in html


def test_admin_shell_makes_professor_enrollment_a_primary_visible_action():
    html = (BACKEND / "templates" / "admin_v2.html").read_text(encoding="utf-8")
    script = (BACKEND / "static" / "admin_v2" / "admin-v2.js").read_text(encoding="utf-8")

    assert 'data-view="invitations">Professor access</a>' in html
    assert "Give a professor access" in script
    assert 'link.href="#invitations"' in script


def test_invitation_handoff_exposes_code_only_and_manual_email_actions():
    html = (BACKEND / "templates" / "admin_v2.html").read_text(encoding="utf-8")
    core_script = (BACKEND / "static" / "admin_v2" / "admin-v2.js").read_text(encoding="utf-8")
    workspace_script = (BACKEND / "static" / "admin_v2" / "admin-workspaces.js").read_text(encoding="utf-8")
    script = core_script + workspace_script

    for marker in (
        "Copy iOS invitation code",
        "Open prepared email",
        "Practenture does not send this invitation until you explicitly choose SES delivery",
        "Do not put invitation secrets into links.",
    ):
        assert marker in html
    assert "mailto:" in script
    assert "login?invite=" not in script
    assert "Create professor access" in script
    assert "Generate replacement" in workspace_script
    assert "The previous code is no longer valid" in workspace_script
    assert 'button("Resend")' not in script


def test_scalable_admin_lists_expose_filters_cursor_paging_and_mobile_actions():
    script = (BACKEND / "static" / "admin_v2" / "admin-workspaces.js").read_text(encoding="utf-8")
    css = (BACKEND / "static" / "admin_v2" / "admin-workspaces.css").read_text(encoding="utf-8")

    for marker in (
        'query.set("cursor", cursor)',
        "pageInfo.nextCursor",
        "Previous",
        "Next",
        "Professor email, code, notes, or ticket",
        "Name, university, or slug",
        "Username, name, or email",
        "Code, professor, class, organization, or scenario",
        "Actor ID",
        "Target ID",
    ):
        assert marker in script
    assert 'cell.dataset.label = column.label' in script
    assert 'content:attr(data-label)' in css
    assert '.table-card thead{display:none}' in css


def test_overview_envelope_and_datetime_filters_match_api_contracts():
    core = (BACKEND / "static" / "admin_v2" / "admin-v2.js").read_text(encoding="utf-8")
    workspaces = (BACKEND / "static" / "admin_v2" / "admin-workspaces.js").read_text(encoding="utf-8")
    assert "renderMetrics(data.overview||data)" in core
    assert "function wsSessionFilters(filters)" in workspaces
    assert "new Date(filters[key]).toISOString()" in workspaces
    assert "Object.entries(wsSessionFilters(filters))" in workspaces
    assert 'request(`/operations/backups?${backupQuery}`)' in workspaces
    assert "pageInfo: backups.pageInfo" in workspaces
    assert "pageInfo: drills.pageInfo" in workspaces
    assert "row.details ? JSON.stringify(row.details)" in workspaces
    assert 'try{await reauthenticate();const result=await request(`/invitations/' in core
    assert '$("password").required=false' in core
    assert 'dialog.addEventListener("cancel",nativeCancel)' in core
    assert 'dialog.addEventListener("close",nativeClose)' in core


def test_legacy_admin_surface_remains_available():
    with TestClient(app) as client:
        legacy = client.get("/admin")
        owner = client.get("/owner", follow_redirects=False)
    assert legacy.status_code == 200
    assert owner.status_code == 308
    assert owner.headers["location"] == "/admin"
