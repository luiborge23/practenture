from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import tarfile
from typing import cast, IO


ROOT = Path(__file__).resolve().parents[1]
NGINX = ROOT / "nginx-practenture.conf"
COMPOSE = ROOT / "docker-compose.yml"
DEPLOY = ROOT / "ec2-deploy.sh"
MIGRATION_ENV = ROOT / "backend" / "migrations" / "env.py"
BUILDER = ROOT / "scripts" / "build_release_artifact.py"
TLS_RENEWAL_INSTALLER = ROOT / "scripts" / "install_tls_renewal.sh"
TLS_RENEWAL_RESTORER = ROOT / "scripts" / "restore_tls_renewal.sh"
RELEASE_VERIFIER = ROOT / "scripts" / "verify_release_manifest.py"
ROLLBACK_RUNBOOK = ROOT / "backend" / "docs" / "ROLLBACK_PLAN.md"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci-cd.yml"
BACKEND_DOCKERIGNORE = ROOT / "backend" / ".dockerignore"
LEGACY_RELEASE_VALIDATION = ROOT / "backend" / "scripts" / "release_validation.sh"
LEGACY_DEPLOY = ROOT / "backend" / "scripts" / "deploy_backup_gated.sh"
IOS_INFO_PLIST = ROOT / "Info.plist"
IOS_PROJECT = ROOT / "Practenture.xcodeproj" / "project.pbxproj"
IOS_DEBUG_CONFIG = ROOT / "Practenture" / "Config" / "Debug.xcconfig"
IOS_RELEASE_CONFIG = ROOT / "Practenture" / "Config" / "Release.xcconfig"


def test_ios_release_uses_strict_ats_and_one_canonical_https_backend() -> None:
    canonical_backend = "https://api.practenture.com"
    project = IOS_PROJECT.read_text(encoding="utf-8")

    target_config_list = re.search(
        r'(?P<id>[A-F0-9]+) /\* Build configuration list for '
        r'PBXNativeTarget "Practenture" \*/ = \{(?P<body>.*?)\n\t\t\};',
        project,
        re.DOTALL,
    )
    assert target_config_list is not None

    release_id_match = re.search(
        r'(?P<id>[A-F0-9]+) /\* Release \*/,',
        target_config_list.group("body"),
    )
    assert release_id_match is not None
    release_id = release_id_match.group("id")

    release_config = re.search(
        rf'{re.escape(release_id)} /\* Release \*/ = \{{'
        r'(?P<body>.*?)\n\t\t\};',
        project,
        re.DOTALL,
    )
    assert release_config is not None
    settings_match = re.search(
        r'buildSettings = \{(?P<settings>.*?)\n\t\t\t\};',
        release_config.group("body"),
        re.DOTALL,
    )
    assert settings_match is not None
    release_settings = settings_match.group("settings")

    def release_setting(name: str) -> str:
        matches = re.findall(
            rf'^\s*{re.escape(name)} = (?P<value>.*);$',
            release_settings,
            re.MULTILINE,
        )
        assert len(matches) == 1
        return matches[0].strip().strip('"')

    assert release_setting("PRACTENTURE_BACKEND_URL") == canonical_backend
    assert release_setting("INFOPLIST_FILE") == "Info.plist"

    for critical_setting in ("PRACTENTURE_BACKEND_URL", "INFOPLIST_FILE"):
        assert re.search(
            rf'^\s*"?{re.escape(critical_setting)}\[[^]]+\]"?\s*=',
            project,
            re.MULTILINE,
        ) is None
    assert "INFOPLIST_KEY_NSAppTransportSecurity" not in project

    selected_info_plist = ROOT / release_setting("INFOPLIST_FILE")
    info = plistlib.loads(selected_info_plist.read_bytes())
    assert info["PRACTENTURE_BACKEND_URL"] == canonical_backend
    assert "NSAppTransportSecurity" not in info

    for config in (IOS_DEBUG_CONFIG, IOS_RELEASE_CONFIG):
        config_text = config.read_text(encoding="utf-8")
        assert f"PRACTENTURE_BACKEND_URL = {canonical_backend}" in config_text
        assert "PRACTENTURE_BACKEND_URL[" not in config_text
        assert "INFOPLIST_FILE[" not in config_text
        assert "INFOPLIST_KEY_NSAppTransportSecurity" not in config_text


def test_admin_v2_nginx_routes_precede_spa_and_preserve_prefix() -> None:
    assert not (ROOT / "nginx.conf").exists()
    config = NGINX.read_text()
    shell = config.index("location = /admin-v2 {")
    shell_slash = config.index("location = /admin-v2/ {")
    api = config.index("location /api/admin/v2/ {")
    fallback = config.index("location / {\n        try_files")
    assert shell < fallback and shell_slash < fallback and api < fallback
    assert "location /static/admin_v2/ {" in config
    api_block = config[api : config.index("    }", api)]
    assert "proxy_pass http://practenture-backend:8000;" in api_block
    assert "proxy_pass http://practenture-backend:8000/;" not in api_block
    generic_api = config.index("location /api/ {")
    generic_api_block = config[generic_api : config.index("    }", generic_api)]
    assert "proxy_pass http://practenture-backend:8000;" in generic_api_block
    assert "proxy_pass http://practenture-backend:8000/;" not in generic_api_block
    admin_block = config[config.index("location = /admin {") : shell]
    assert "proxy_pass http://practenture-backend:8000/admin-v2;" in admin_block
    legal = config.index("location ~ ^/(privacy|terms|support)$ {")
    legal_block = config[legal : config.index("    }", legal)]
    assert legal < fallback
    assert "proxy_pass http://practenture-backend:8000;" in legal_block
    assert "proxy_pass http://practenture-backend:8000/;" not in legal_block
    assert config.count(
        'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;'
    ) == 2
    assert "$proxy_add_x_forwarded_for" not in config
    assert config.count("proxy_set_header X-Forwarded-For $remote_addr;") == 10


def test_compose_exposes_tls_and_mounts_certificates_read_only() -> None:
    compose = COMPOSE.read_text()
    assert '- "80:80"' in compose
    assert '- "443:443"' in compose
    assert "/etc/letsencrypt:/etc/letsencrypt:ro" in compose
    assert "/var/www/practenture:/var/www/practenture:ro" in compose
    assert "PRACTENTURE_DB_PATH=/data/practenture.db" in compose


def test_container_defaults_require_a_jwt_secret_and_reject_wildcard_cors() -> None:
    compose = COMPOSE.read_text()
    dockerfile = (ROOT / "Dockerfile").read_text()
    env_example = (ROOT / ".env.example").read_text()
    assert "${PRACTENTURE_JWT_SECRET:?PRACTENTURE_JWT_SECRET must be set}" in compose
    assert "${PRACTENTURE_PROVIDER_JOB_ENCRYPTION_KEY:?PRACTENTURE_PROVIDER_JOB_ENCRYPTION_KEY must be set}" in compose
    assert "PRACTENTURE_APPLE_TEAM_ID=${PRACTENTURE_APPLE_TEAM_ID:-}" in compose
    assert "PRACTENTURE_APPLE_KEY_ID=${PRACTENTURE_APPLE_KEY_ID:-}" in compose
    assert "PRACTENTURE_APPLE_PRIVATE_KEY=${PRACTENTURE_APPLE_PRIVATE_KEY:-}" in compose
    for required_provider_setting in (
        "PRACTENTURE_PROVIDER_JOB_ENCRYPTION_KEY=",
        "PRACTENTURE_APPLE_TEAM_ID=",
        "PRACTENTURE_APPLE_KEY_ID=",
        "PRACTENTURE_APPLE_PRIVATE_KEY=",
    ):
        assert required_provider_setting in env_example
    assert "${PRACTENTURE_OWNER_PASSWORD:?PRACTENTURE_OWNER_PASSWORD must be set}" in compose
    assert "${PRACTENTURE_PROFESSOR_PASSWORD:?PRACTENTURE_PROFESSOR_PASSWORD must be set}" in compose
    assert "FORWARDED_ALLOW_IPS=*" not in compose
    assert "FORWARDED_ALLOW_IPS=${FORWARDED_ALLOW_IPS:-172.16.0.0/12}" in compose
    assert "PRACTENTURE_CORS_ORIGINS=${PRACTENTURE_CORS_ORIGINS:-*}" not in compose
    assert "PRACTENTURE_CORS_ORIGINS=${PRACTENTURE_CORS_ORIGINS:-*}" not in dockerfile
    assert "PRACTENTURE_JWT_SECRET=" not in dockerfile
    assert "python:3.11-slim@sha256:" in dockerfile
    assert "nginx:alpine@sha256:" in compose


def test_backend_image_drops_root_after_preparing_runtime_paths() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    ownership = dockerfile.index("chown -R bizsim:bizsim /app /data")
    user = dockerfile.index("USER bizsim")
    command = dockerfile.index('CMD ["gunicorn"')
    assert ownership < user < command
    compose = COMPOSE.read_text()
    assert "db-permissions:" in compose
    assert 'user: "0:0"' in compose
    assert "chown -R bizsim:bizsim /data" in compose
    assert "condition: service_completed_successfully" in compose


def test_migration_default_targets_authoritative_mounted_database() -> None:
    env = MIGRATION_ENV.read_text()
    assert "PRACTENTURE_DB_PATH" in env
    assert '"/data/practenture.db"' in env
    assert '"sqlite+aiosqlite:///data.db"' not in env


def test_deploy_consumes_verified_artifact_and_restores_release_on_rollback() -> None:
    deploy = DEPLOY.read_text()
    for required_provider_setting in (
        "PRACTENTURE_PROVIDER_JOB_ENCRYPTION_KEY",
        "PRACTENTURE_APPLE_TEAM_ID",
        "PRACTENTURE_APPLE_KEY_ID",
        "PRACTENTURE_APPLE_PRIVATE_KEY",
    ):
        assert required_provider_setting in deploy
    assert "Apple authentication requires audience, team ID, key ID, and private key" in deploy
    assert "rsync -avz --delete" not in deploy
    assert "build_release_artifact.py" in deploy
    assert "sha256sum -c practenture-release.tar.gz.sha256" in deploy
    assert "practenture-releases/$RELEASE_SHA" in deploy
    assert "previous-release" in deploy
    assert "candidate-release" in deploy
    proxy_probe = "curl --fail --silent --show-error --resolve practenture.com:443:127.0.0.1 https://practenture.com/api/health"
    assert deploy.index(proxy_probe) < deploy.index('mv -Tf "$LINK_TMP" "$HOME/practenture-current"')
    assert "ln -sfn" not in deploy
    assert "MANIFEST_SOURCE_REVISION" in deploy
    assert "open(sys.argv[1], encoding='utf-8')" in deploy
    assert '"\\$RELEASE_TMP/RELEASE-MANIFEST.json"' in deploy
    assert "practenture-releases/.staging-$RELEASE_SHA" in deploy
    assert 'mv "\\$RELEASE_TMP" "\\$RELEASE_PATH"' in deploy
    assert 'if [ -e "\\$RELEASE_PATH" ]; then' in deploy
    assert ".release-artifact-sha256" in deploy
    assert 'scripts/verify_release_manifest.py" \\' in deploy
    assert "--manifest-sha256" in deploy
    assert "ACTIVATION_RECOVERED" in deploy
    assert "ACTIVATION_ROLLED_BACK_FOR_RETRY" in deploy
    assert "Existing activation lacks complete rollback evidence" in deploy
    assert 'if [ ! -f "\\$RELEASE_PATH/.activation-started" ]; then' in deploy
    assert "Candidate completion failed; restoring retained release before retry" in deploy
    assert "An existing candidate activation is indeterminate" in deploy
    assert '--build-arg "PRACTENTURE_RELEASE_SHA=$SOURCE_REVISION"' in deploy
    assert '"practenture-backend:rollback-$DEPLOY_ID" > .rollback-image' in deploy
    assert "docker-compose -p practenture stop nginx practenture-backend" in deploy
    assert "predeploy-$DEPLOY_ID.db" in deploy
    assert "FIRST_ACTIVATION_RESET_FOR_RETRY" in deploy
    assert 'if [ -z "$PREVIOUS_IMAGE" ]; then' in deploy
    assert "A first activation has no retained image" in deploy
    assert "Candidate was healthy but release promotion failed; rolling back." in deploy
    assert "if ! ssh -o StrictHostKeyChecking=no" in deploy
    assert "REMOTE_DEPLOY_FAILED=1" in deploy
    assert "touch .activation-started" in deploy
    assert "touch .activation-complete" in deploy
    assert 'touch "$CANDIDATE_RELEASE/.promotion-complete"' in deploy
    promotion = deploy.index('touch "$CANDIDATE_RELEASE/.promotion-complete"')
    backup_cleanup = deploy.index(
        'docker exec practenture-backend rm -f "/data/predeploy-$DEPLOY_ID.db"',
        promotion,
    )
    marker_cleanup = deploy.index(
        'rm -f "$CANDIDATE_RELEASE/.activation-started"',
        promotion,
    )
    assert promotion < marker_cleanup < backup_cleanup
    assert 'WARNING: deferred predeploy backup cleanup failed for $DEPLOY_ID' in deploy
    activation_health = deploy.index("BACKEND_HEALTHY=0")
    assert activation_health < deploy.index(
        "docker-compose -p practenture up -d --no-build nginx",
        activation_health,
    )
    assert "Candidate activation did not produce its completion marker" in deploy
    assert "org.opencontainers.image.revision" in deploy
    assert "Candidate failed a deployment gate; restoring retained application" in deploy
    assert "Promotion committed; recovered from an interrupted post-commit cleanup." in deploy
    assert 'test ! -f "$CANDIDATE_RELEASE/.activation-started"' in deploy
    assert 'if [ -f .activation-started ] && sudo test -d "$TLS_ROLLBACK_DIR"' in deploy
    assert "assert os.path.isfile(p)" in deploy
    assert 'ln -s "$PREVIOUS_RELEASE" "$LINK_TMP"' in deploy
    assert 'mv -Tf "$LINK_TMP" "$HOME/practenture-current"' in deploy
    assert "docker inspect practenture-backend" in deploy
    assert "docker inspect bizsim-backend" not in deploy
    assert proxy_probe in deploy
    assert "curl -sf http://127.0.0.1:8000/api/health" not in deploy
    assert "Professor login: professor /" not in deploy
    assert "PRACTENTURE_ALLOW_BOOTSTRAP_SECRETS" in deploy
    assert "Deployment credentials are incomplete" in deploy
    assert "forbidden test/example marker" in deploy
    assert "Deployment requires a clean Git worktree" in deploy
    assert "Deployment requires HEAD to match the authoritative GitHub main branch exactly" in deploy
    assert 'EXPECTED_REPOSITORY="luiborge23/practenture"' in deploy
    assert "PRACTENTURE_RELEASE_RUN_ID" in deploy
    assert 'gh run view "$RELEASE_RUN_ID"' in deploy
    assert '--repo "$EXPECTED_REPOSITORY"' in deploy
    assert "headSha,status,conclusion,event,headBranch,workflowName" in deploy
    assert '"Practenture Quality Gates"' in deploy
    assert '".github/workflows/ci-cd.yml"' in deploy
    assert "check-suites/$CHECK_SUITE_ID/check-runs" in deploy
    assert 'gh run download "$RELEASE_RUN_ID"' in deploy
    assert 'CI_ARTIFACT_NAME="backend-release-$SOURCE_REVISION"' in deploy
    assert 'cmp "$CI_RELEASE_ARTIFACT" "$LOCAL_REPEAT"' in deploy
    assert "CI release artifact checksum file does not match its exact bytes" in deploy
    assert "CI artifact is not byte-identical to the clean local exact-SHA tree" in deploy
    assert '--source-revision "$SOURCE_REVISION"' in deploy
    assert 'EXPLICIT_JWT_SECRET="${PRACTENTURE_JWT_SECRET:-}"' in deploy
    assert 'JWT_SECRET="${EXPLICIT_JWT_SECRET:-${PRACTENTURE_JWT_SECRET:-}}"' in deploy
    assert 'TLS_ROLLBACK_DIR="/var/lib/practenture-deploy/tls-rollback-$DEPLOY_ID"' in deploy
    assert 'sudo ./scripts/restore_tls_renewal.sh "$TLS_ROLLBACK_DIR"' in deploy
    assert 'sudo test -f "$TLS_ROLLBACK_DIR/install-complete"' in deploy


def test_deploy_ci_preflight_fails_closed_before_credentials_or_ssh(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    deploy = repo / "ec2-deploy.sh"
    deploy.write_bytes(DEPLOY.read_bytes())
    deploy.chmod(0o755)
    (repo / ".gitignore").write_text(".ec2-state.json\n.env\n", encoding="utf-8")
    (repo / ".ec2-state.json").write_text(
        '{"public_ip":"192.0.2.10"}\n', encoding="utf-8"
    )
    for command in (
        ["git", "init", "-b", "main"],
        ["git", "config", "user.name", "Release Contract"],
        ["git", "config", "user.email", "release-contract@example.invalid"],
        ["git", "add", "ec2-deploy.sh", ".gitignore"],
        ["git", "commit", "-m", "fixture"],
    ):
        subprocess.run(command, cwd=repo, check=True, capture_output=True, text=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/main", revision],
        cwd=repo,
        check=True,
    )

    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    gh = mock_bin / "gh"
    gh.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
case "$1 $2" in
  "run view") printf '%s\\n' "$MOCK_RUN_METADATA" ;;
  "api repos/luiborge23/practenture/git/ref/heads/main")
    printf '%s\\n' "$MOCK_MAIN_SHA" ;;
  "api repos/luiborge23/practenture/actions/runs/123")
    printf 'suite-1\\t%s\\n' "$MOCK_WORKFLOW_PATH" ;;
  "api repos/luiborge23/practenture/check-suites/suite-1/check-runs?per_page=100")
    printf '%s\\n' "$MOCK_ANNOTATIONS" ;;
  *) printf 'unexpected gh call: %s\\n' "$*" >&2; exit 98 ;;
esac
""",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    for command_name in ("ssh", "scp"):
        command = mock_bin / command_name
        command.write_text(
            "#!/usr/bin/env bash\nprintf remote > \"$MOCK_REMOTE_MARKER\"\nexit 99\n",
            encoding="utf-8",
        )
        command.chmod(0o755)

    valid = f"{revision}\tcompleted\tsuccess\tpush\tmain\tPractenture Quality Gates"
    canonical_workflow = ".github/workflows/ci-cd.yml"
    scenarios = (
        (None, revision, valid, "0", canonical_workflow, "Deployment requires PRACTENTURE_RELEASE_RUN_ID"),
        ("123", "0" * 40, valid, "0", canonical_workflow, "authoritative GitHub main branch"),
        ("123", revision, f"{'0' * 40}\tcompleted\tsuccess\tpush\tmain\tPractenture Quality Gates", "0", canonical_workflow, "Release run must be"),
        ("123", revision, f"{revision}\tin_progress\t\tpush\tmain\tPractenture Quality Gates", "0", canonical_workflow, "Release run must be"),
        ("123", revision, f"{revision}\tcompleted\tfailure\tpush\tmain\tPractenture Quality Gates", "0", canonical_workflow, "Release run must be"),
        ("123", revision, f"{revision}\tcompleted\tsuccess\tpull_request\tmain\tPractenture Quality Gates", "0", canonical_workflow, "Release run must be"),
        ("123", revision, f"{revision}\tcompleted\tsuccess\tpush\tdevelop\tPractenture Quality Gates", "0", canonical_workflow, "Release run must be"),
        ("123", revision, f"{revision}\tcompleted\tsuccess\tpush\tmain\tOther Workflow", "0", canonical_workflow, "Release run must be"),
        ("123", revision, valid, "0", ".github/workflows/other.yml", "canonical CI workflow path"),
        ("123", revision, valid, "1", canonical_workflow, "Exact-SHA checks contain unresolved annotations"),
        ("123", revision, valid, "0", canonical_workflow, "Deployment credentials are incomplete"),
    )
    for run_id, main_sha, metadata, annotations, workflow_path, expected_error in scenarios:
        marker = tmp_path / "remote-called"
        marker.unlink(missing_ok=True)
        env = os.environ.copy()
        for key in tuple(env):
            if key.startswith("PRACTENTURE_"):
                env.pop(key)
        env.update(
            {
                "PATH": f"{mock_bin}:{env['PATH']}",
                "MOCK_RUN_METADATA": metadata,
                "MOCK_MAIN_SHA": main_sha,
                "MOCK_ANNOTATIONS": annotations,
                "MOCK_WORKFLOW_PATH": workflow_path,
                "MOCK_REMOTE_MARKER": str(marker),
            }
        )
        if run_id is None:
            env.pop("PRACTENTURE_RELEASE_RUN_ID", None)
        else:
            env["PRACTENTURE_RELEASE_RUN_ID"] = run_id
        result = subprocess.run(
            ["bash", str(deploy), "deploy"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert expected_error in result.stderr
        assert not marker.exists()
        assert not (repo / ".env").exists()


def test_remote_deployment_heredocs_have_valid_bash_syntax() -> None:
    deploy = DEPLOY.read_text()
    blocks = re.findall(
        r"<<'?((?:REMOTE|USER)_?[A-Z_]*)'?\n(.*?)\n\1",
        deploy,
        flags=re.DOTALL,
    )
    assert {name for name, _body in blocks} >= {
        "REMOTE_STAGE",
        "REMOTE_RECOVER",
        "REMOTE_DEPLOY",
        "REMOTE_PROMOTE",
        "REMOTE_ROLLBACK",
    }
    for name, body in blocks:
        if name == "REMOTE_STAGE":
            # This heredoc is intentionally expanded by the local shell; the
            # backslashes preserve remote dollar signs until that expansion.
            body = body.replace("\\$", "$")
        parsed = subprocess.run(
            ["bash", "-n"], input=body, capture_output=True, text=True
        )
        assert parsed.returncode == 0, f"{name}: {parsed.stderr}"


def test_tls_renewal_installer_is_fail_closed_and_reloads_nginx() -> None:
    script = TLS_RENEWAL_INSTALLER.read_text()
    restore_script = TLS_RENEWAL_RESTORER.read_text()
    nginx = NGINX.read_text()
    compose = COMPOSE.read_text()
    assert TLS_RENEWAL_INSTALLER.stat().st_mode & 0o111
    assert TLS_RENEWAL_RESTORER.stat().st_mode & 0o111
    assert "set -euo pipefail" in script
    assert "expected exactly the api.practenture.com and www.practenture.com renewal lineages" in script
    assert "practenture-certbot-renew.service" in script
    assert "practenture-certbot-renew.timer" in script
    assert "OnCalendar=*-*-* 03,15:00:00" in script
    assert "RandomizedDelaySec=3600" in script
    assert "Persistent=true" in script
    assert "WEBROOT_PATH=\"/var/www/certbot\"" in script
    assert "ExecStart=$CERTBOT_BIN renew --quiet --no-random-sleep-on-renew" in script
    assert "Requires=docker.service" in script
    assert "ExecStartPre=$DOCKER_BIN inspect practenture-nginx" in script
    assert "ExecStartPre=$DOCKER_BIN exec practenture-nginx nginx -t" in script
    assert "NoNewPrivileges=yes" in script
    assert "ProtectSystem=strict" in script
    assert "ReadWritePaths=$LETSENCRYPT_DIR" in script
    assert '"$CERTBOT_BIN" reconfigure \\' in script
    assert '--cert-name "$cert_name"' in script
    reconfigure_block = script.split('"$CERTBOT_BIN" reconfigure \\', 1)[1].split(
        "grep -Eq '^authenticator = webroot$'", 1
    )[0]
    assert "--no-random-sleep-on-renew" not in reconfigure_block
    assert "^authenticator = webroot$" in script
    assert "^webroot_path = " in script
    assert 'cp -a "$work_dir/previous-renewal-configs" "$snapshot_staging/previous-renewal-configs"' in script
    assert script.index("trap cleanup EXIT") < script.index(
        'install -d -m 700 "$work_dir/previous-renewal-configs"'
    )
    assert '"$DOCKER_BIN" exec practenture-nginx nginx -t' in script
    assert '"$DOCKER_BIN" exec practenture-nginx nginx -s reload' in script
    assert '"$SYSTEMCTL_BIN" is-active --quiet "$TIMER_NAME"' in script
    assert "--dry-run" in script
    assert "--run-deploy-hooks" in script
    assert "--no-random-sleep-on-renew" in script
    assert "TLS_RENEWAL_DRY_RUN_PASSED" in script
    assert '"$SYSTEMCTL_BIN" enable "$TIMER_NAME"' in script
    assert '"$SYSTEMCTL_BIN" start "$TIMER_NAME"' in script
    assert '"$SYSTEMD_ANALYZE" verify' in script
    assert '"$SYSTEMCTL_BIN" is-enabled --quiet "$TIMER_NAME"' in script
    assert '"$SYSTEMCTL_BIN" is-active --quiet "$TIMER_NAME"' in script
    assert "TLS_RENEWAL_TIMER_READY" in script
    assert "TLS_RENEWAL_PREVIOUS_CONFIGURATION_RESTORED" in script
    assert 'timer_was_active=1' in script
    assert 'touch "$snapshot_staging/timer-was-active"' in script
    assert 'touch "$snapshot_staging/hook-dir-existed"' in script
    assert 'touch "$snapshot_staging/webroot-existed"' in script
    assert 'snapshot_created=1' in script
    assert 'mv "$snapshot_staging" "$ROLLBACK_DIR"' in script
    assert 'touch "$ROLLBACK_DIR/install-complete"' in script
    assert 'if [ "$rc" -ne 0 ] && [ "$snapshot_created" -eq 1 ]' in script
    assert 'TLS_RENEWAL_RESTORE_INCOMPLETE; durable rollback snapshot retained' in script
    assert '[ "$restore_on_error" -eq 0 ] || [ "$restore_failed" -eq 0 ]' in script
    assert script.index('"$SYSTEMCTL_BIN" disable --now "$TIMER_NAME"') < script.index(
        'if [ "$restore_failed" -eq 0 ]; then'
    )
    assert 'if [ "$timer_existed" -eq 0 ] && [ -f "$SYSTEMD_DIR/$TIMER_NAME" ]' not in script
    assert 'if [ -f "$SYSTEMD_DIR/$TIMER_NAME" ]; then' in restore_script
    assert 'systemctl disable --now "$TIMER_NAME" >/dev/null 2>&1' in restore_script
    assert 'systemctl disable --now "$TIMER_NAME" >/dev/null 2>&1 || true' not in restore_script
    assert 'cp -a "$SNAPSHOT_DIR/previous-service"' in restore_script
    assert 'cp -a "$SNAPSHOT_DIR/previous-timer"' in restore_script
    assert 'if [ -f "$SNAPSHOT_DIR/timer-existed" ]; then' in restore_script
    assert 'cp -a "$SNAPSHOT_DIR/previous-hook"' in restore_script
    assert 'if [ ! -d "$SNAPSHOT_DIR/previous-renewal-configs" ]' in restore_script
    assert 'compgen -G "$SNAPSHOT_DIR/previous-renewal-configs/*.conf"' in restore_script
    assert 'cp -a "$renewal_config" "$destination"' in restore_script
    assert 'rmdir "$HOOK_DIR"' in restore_script
    assert 'rmdir "$WEBROOT_PATH"' in restore_script
    assert restore_script.index("previous-renewal-configs/*.conf") < restore_script.index(
        'systemctl disable --now "$TIMER_NAME"'
    )
    assert "TLS_RENEWAL_DEPLOYMENT_ROLLBACK_RESTORED" in restore_script
    assert script.index('"$CERTBOT_BIN" renew \\') < script.index(
        'install -m 644 "$work_dir/$SERVICE_NAME"'
    )
    aggregate_renew = script.split('"$CERTBOT_BIN" renew \\', 1)[1].split(
        'echo "TLS_RENEWAL_DRY_RUN_PASSED"', 1
    )[0]
    assert "--webroot" not in aggregate_renew
    assert "--webroot-path" not in aggregate_renew
    assert "PRACTENTURE_TLS_TEST_ROOT requires PRACTENTURE_TLS_TESTING=1" in script
    assert 'required_cert_names=("api.practenture.com" "www.practenture.com")' in script
    assert 'TEST_BIN_DIR="$TEST_ROOT/bin"' in script
    assert nginx.count("location ^~ /.well-known/acme-challenge/") == 2
    assert nginx.count("root /var/www/certbot;") == 2
    assert "- /var/www/certbot:/var/www/certbot:ro" in compose


def _tls_installer_fixture(
    tmp_path: Path, *, fail_renew: bool, existing_runtime: bool = True
) -> tuple[Path, dict[str, str], dict[Path, bytes], dict[Path, tuple[int, int]]]:
    root = tmp_path / "root"
    fake_bin = root / "bin"
    renewal_dir = root / "etc" / "letsencrypt" / "renewal"
    hook = root / "etc" / "letsencrypt" / "renewal-hooks" / "deploy" / "practenture-nginx-reload"
    webroot = root / "var" / "www" / "certbot"
    systemd = root / "etc" / "systemd" / "system"
    for directory in (fake_bin, renewal_dir, systemd):
        directory.mkdir(parents=True, exist_ok=True)

    originals: dict[Path, bytes] = {}
    for cert_name in ("api.practenture.com", "www.practenture.com"):
        live = root / "etc" / "letsencrypt" / "live" / cert_name
        archive = root / "etc" / "letsencrypt" / "archive" / cert_name
        live.mkdir(parents=True, exist_ok=True)
        archive.mkdir(parents=True, exist_ok=True)
        for filename in ("cert.pem", "privkey.pem", "chain.pem", "fullchain.pem"):
            (archive / filename).write_text("fixture\n", encoding="utf-8")
            (live / filename).symlink_to(archive / filename)
        originals[renewal_dir / f"{cert_name}.conf"] = (
            f"version = 2.6.0\n"
            f"archive_dir = {archive}\n"
            f"cert = {live}/cert.pem\n"
            f"privkey = {live}/privkey.pem\n"
            f"chain = {live}/chain.pem\n"
            f"fullchain = {live}/fullchain.pem\n"
            "[renewalparams]\n"
            "account = fixture-account\n"
            "authenticator = standalone\n"
            "server = https://acme-staging-v02.api.letsencrypt.org/directory\n"
            "key_type = rsa\n"
        ).encode()
    if existing_runtime:
        hook.parent.mkdir(parents=True, exist_ok=True)
        webroot.mkdir(parents=True, exist_ok=True)
        originals.update(
            {
                systemd / "practenture-certbot-renew.service": b"previous service\n",
                systemd / "practenture-certbot-renew.timer": b"previous timer\n",
                hook: b"#!/usr/bin/env bash\necho previous-hook\n",
                webroot / "preexisting-challenge-state": b"preserve me\n",
            }
        )
    original_state: dict[Path, tuple[int, int]] = {}
    modes = (0o600, 0o640, 0o644, 0o620, 0o750)
    for index, (path, content) in enumerate(originals.items()):
        path.write_bytes(content)
        path.chmod(modes[index % len(modes)])
        timestamp_ns = 1_700_000_000_000_000_000 + index * 1_000_000_000
        os.utime(path, ns=(timestamp_ns, timestamp_ns))
        stat = path.stat()
        original_state[path] = (stat.st_mode & 0o777, stat.st_mtime_ns)
    if existing_runtime:
        for index, directory in enumerate((hook.parent, webroot)):
            directory.chmod(0o710 + index)
            directory_timestamp_ns = 1_699_999_999_000_000_000 + index * 1_000_000_000
            os.utime(
                directory,
                ns=(directory_timestamp_ns, directory_timestamp_ns),
            )
            stat = directory.stat()
            original_state[directory] = (stat.st_mode & 0o777, stat.st_mtime_ns)

    certbot = fake_bin / "certbot"
    certbot.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf 'certbot %s\\n' "$*" >> "$PRACTENTURE_TLS_TEST_ROOT/commands.log"
if [ "$1" = reconfigure ]; then
  cert_name=$3
  expected="reconfigure --cert-name $cert_name --webroot --webroot-path $PRACTENTURE_TLS_TEST_ROOT/var/www/certbot --run-deploy-hooks"
  [ "$*" = "$expected" ] || exit 88
  case "$cert_name" in api.practenture.com|www.practenture.com) ;; *) exit 89 ;; esac
  config="$PRACTENTURE_TLS_TEST_ROOT/etc/letsencrypt/renewal/$cert_name.conf"
  sed -e 's/^authenticator = standalone$/authenticator = webroot/' "$config" > "$config.tmp"
  printf 'webroot_path = %s/var/www/certbot,\\n' "$PRACTENTURE_TLS_TEST_ROOT" >> "$config.tmp"
  mv "$config.tmp" "$config"
elif [ "$1" = renew ]; then
  expected="renew --dry-run --run-deploy-hooks --no-random-sleep-on-renew"
  [ "$*" = "$expected" ] || exit 90
  [ "${FAKE_CERTBOT_FAIL_RENEW:-0}" != 1 ] || exit 90
  for cert_name in api.practenture.com www.practenture.com; do
    config="$PRACTENTURE_TLS_TEST_ROOT/etc/letsencrypt/renewal/$cert_name.conf"
    grep -Eq '^archive_dir = .+' "$config"
    grep -Eq '^cert = .+' "$config"
    grep -Eq '^privkey = .+' "$config"
    grep -Eq '^chain = .+' "$config"
    grep -Eq '^fullchain = .+' "$config"
    grep -Fqx '[renewalparams]' "$config"
    grep -Eq '^authenticator = webroot$' "$config"
    grep -Fqx "webroot_path = $PRACTENTURE_TLS_TEST_ROOT/var/www/certbot," "$config"
  done
fi
touch "$PRACTENTURE_TLS_TEST_ROOT/var/www/certbot/.certbot-temporary-state"
rm -f "$PRACTENTURE_TLS_TEST_ROOT/var/www/certbot/.certbot-temporary-state"
hook="$PRACTENTURE_TLS_TEST_ROOT/etc/letsencrypt/renewal-hooks/deploy/practenture-nginx-reload"
if [ -x "$hook" ]; then
  "$hook"
  [ "$1" != renew ] || "$hook"
fi
""",
        encoding="utf-8",
    )
    certbot.chmod(0o755)

    for name, body in {
        "docker": """#!/usr/bin/env bash
printf 'docker %s\\n' "$*" >> "$PRACTENTURE_TLS_TEST_ROOT/commands.log"
exit 0
""",
        "systemctl": """#!/usr/bin/env bash
printf 'systemctl %s\\n' "$*" >> "$PRACTENTURE_TLS_TEST_ROOT/commands.log"
[ "$1" != show ] || printf '2026-08-04 03:00:00 UTC\\n'
exit 0
""",
        "systemd-analyze": """#!/usr/bin/env bash
printf 'systemd-analyze %s\\n' "$*" >> "$PRACTENTURE_TLS_TEST_ROOT/commands.log"
exit 0
""",
    }.items():
        executable = fake_bin / name
        executable.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body, encoding="utf-8")
        executable.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PRACTENTURE_TLS_TESTING": "1",
            "PRACTENTURE_TLS_TEST_ROOT": str(root),
            "FAKE_CERTBOT_FAIL_RENEW": "1" if fail_renew else "0",
        }
    )
    env.pop("PRACTENTURE_TLS_ROLLBACK_DIR", None)
    return root, env, originals, original_state


def test_tls_renewal_installer_executes_persisted_webroot_dry_run(tmp_path: Path) -> None:
    root, env, _originals, _original_state = _tls_installer_fixture(
        tmp_path, fail_renew=False
    )
    result = subprocess.run(
        ["bash", str(TLS_RENEWAL_INSTALLER)], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "TLS_RENEWAL_DRY_RUN_PASSED" in result.stdout
    assert "TLS_RENEWAL_TIMER_READY" in result.stdout
    service = (
        root / "etc" / "systemd" / "system" / "practenture-certbot-renew.service"
    ).read_text(encoding="utf-8")
    assert "ExecStart=" in service
    assert "renew --quiet --no-random-sleep-on-renew" in service
    assert "Requires=docker.service" in service
    assert "NoNewPrivileges=yes" in service
    assert "ProtectSystem=strict" in service
    assert "ExecStartPre=" in service
    commands = (root / "commands.log").read_text(encoding="utf-8")
    assert commands.count("certbot reconfigure ") == 2
    renew_line = next(line for line in commands.splitlines() if line.startswith("certbot renew "))
    assert "--dry-run" in renew_line
    assert "--run-deploy-hooks" in renew_line
    assert "--no-random-sleep-on-renew" in renew_line
    assert "--webroot" not in renew_line
    assert "--webroot-path" not in renew_line
    assert commands.count("docker exec practenture-nginx nginx -t") == 4
    assert commands.count("docker exec practenture-nginx nginx -s reload") == 4
    for config in (root / "etc" / "letsencrypt" / "renewal").glob("*.conf"):
        text = config.read_text(encoding="utf-8")
        assert "authenticator = webroot" in text
        assert f"webroot_path = {root}/var/www/certbot," in text


def test_tls_renewal_installer_restores_exact_state_when_dry_run_fails(tmp_path: Path) -> None:
    root, env, originals, original_state = _tls_installer_fixture(
        tmp_path, fail_renew=True
    )
    result = subprocess.run(
        ["bash", str(TLS_RENEWAL_INSTALLER)], env=env, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "TLS_RENEWAL_PREVIOUS_CONFIGURATION_RESTORED" in result.stderr
    for path, content in originals.items():
        assert path.read_bytes() == content
    for path, state in original_state.items():
        stat = path.stat()
        assert (stat.st_mode & 0o777, stat.st_mtime_ns) == state
    commands = (root / "commands.log").read_text(encoding="utf-8").splitlines()
    disable_index = commands.index(
        "systemctl disable --now practenture-certbot-renew.timer"
    )
    reload_index = commands.index("systemctl daemon-reload")
    enable_index = commands.index("systemctl enable practenture-certbot-renew.timer")
    start_index = commands.index("systemctl start practenture-certbot-renew.timer")
    assert disable_index < reload_index < enable_index < start_index


def test_tls_renewal_installer_restores_absent_runtime_state(tmp_path: Path) -> None:
    root, env, _originals, _original_state = _tls_installer_fixture(
        tmp_path, fail_renew=True, existing_runtime=False
    )
    result = subprocess.run(
        ["bash", str(TLS_RENEWAL_INSTALLER)], env=env, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "TLS_RENEWAL_PREVIOUS_CONFIGURATION_RESTORED" in result.stderr
    assert not (root / "etc/systemd/system/practenture-certbot-renew.service").exists()
    assert not (root / "etc/systemd/system/practenture-certbot-renew.timer").exists()
    assert not (
        root / "etc/letsencrypt/renewal-hooks/deploy/practenture-nginx-reload"
    ).exists()
    assert not (root / "etc/letsencrypt/renewal-hooks/deploy").exists()
    assert not (root / "var/www/certbot").exists()


def test_tls_renewal_installer_rejects_root_alias_and_lineage_drift(tmp_path: Path) -> None:
    alias = tmp_path / "root-alias"
    alias.symlink_to("/")
    unsafe_env = os.environ.copy()
    unsafe_env.update(
        {"PRACTENTURE_TLS_TESTING": "1", "PRACTENTURE_TLS_TEST_ROOT": str(alias)}
    )
    unsafe = subprocess.run(
        ["bash", str(TLS_RENEWAL_INSTALLER)],
        env=unsafe_env,
        capture_output=True,
        text=True,
    )
    assert unsafe.returncode == 2
    assert "must not resolve to the production filesystem root" in unsafe.stderr

    missing_root, missing_env, _originals, _state = _tls_installer_fixture(
        tmp_path / "missing", fail_renew=False
    )
    (missing_root / "etc/letsencrypt/renewal/api.practenture.com.conf").unlink()
    missing = subprocess.run(
        ["bash", str(TLS_RENEWAL_INSTALLER)],
        env=missing_env,
        capture_output=True,
        text=True,
    )
    assert missing.returncode != 0
    assert "expected exactly" in missing.stderr

    extra_root, extra_env, _originals, _state = _tls_installer_fixture(
        tmp_path / "extra", fail_renew=False
    )
    (extra_root / "etc/letsencrypt/renewal/stale.example.conf").write_text(
        "[renewalparams]\nauthenticator = standalone\n", encoding="utf-8"
    )
    extra = subprocess.run(
        ["bash", str(TLS_RENEWAL_INSTALLER)],
        env=extra_env,
        capture_output=True,
        text=True,
    )
    assert extra.returncode != 0
    assert "expected exactly" in extra.stderr


def test_release_artifact_is_reproducible_and_excludes_state(tmp_path: Path) -> None:
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    for output in (first, second):
        subprocess.run(
            [sys.executable, str(BUILDER), "--root", str(ROOT), "--output", str(output)],
            check=True,
            capture_output=True,
            text=True,
        )
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
    with tarfile.open(first, "r:gz") as archive:
        names = archive.getnames()
        assert "RELEASE-MANIFEST.json" in names
        assert not any(name.endswith((".db", ".db-wal", ".db-shm", ".pyc")) for name in names)
        assert not any(name == ".env" or name.endswith("/.env") or "__pycache__" in name for name in names)
        assert not any(name == ".gradle" or name.startswith(".gradle/") for name in names)
        extracted = archive.extractfile("RELEASE-MANIFEST.json")
        assert extracted is not None
        manifest = json.load(cast(IO[bytes], extracted))
        assert manifest["formatVersion"] == 1
        assert manifest["sourceRevision"] is None
        assert manifest["files"]


def test_extracted_release_verifier_rejects_tampering_and_unexpected_files(
    tmp_path: Path,
) -> None:
    revision = "a" * 40
    artifact = tmp_path / "release.tar.gz"
    release = tmp_path / "release"
    subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--root",
            str(ROOT),
            "--output",
            str(artifact),
            "--source-revision",
            revision,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    release.mkdir()
    with tarfile.open(artifact, "r:gz") as archive:
        archive.extractall(release, filter="data")

    manifest_path = release / "RELEASE-MANIFEST.json"
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    command = [
        sys.executable,
        str(RELEASE_VERIFIER),
        str(release),
        "--source-revision",
        revision,
        "--manifest-sha256",
        manifest_sha256,
    ]
    verified = subprocess.run(command, check=True, capture_output=True, text=True)
    assert verified.stdout.strip() == "RELEASE_MANIFEST_VERIFIED"

    unexpected = release / "backend" / "unexpected.py"
    unexpected.write_text("raise RuntimeError\n", encoding="utf-8")
    assert subprocess.run(command, capture_output=True, text=True).returncode != 0
    unexpected.unlink()

    runtime_link = release / ".activation-complete"
    runtime_link.symlink_to(release / "Dockerfile")
    assert subprocess.run(command, capture_output=True, text=True).returncode != 0
    runtime_link.unlink()

    dockerfile = release / "Dockerfile"
    dockerfile.write_text(dockerfile.read_text() + "\n# tampered\n", encoding="utf-8")
    assert subprocess.run(command, capture_output=True, text=True).returncode != 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dockerfile_entry = next(
        entry for entry in manifest["files"] if entry["path"] == "Dockerfile"
    )
    dockerfile_entry["size"] = dockerfile.stat().st_size
    dockerfile_entry["sha256"] = hashlib.sha256(dockerfile.read_bytes()).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    assert subprocess.run(command, capture_output=True, text=True).returncode != 0


def test_ci_is_hermetic_and_covers_admin_and_the_production_image() -> None:
    workflow = CI_WORKFLOW.read_text()
    assert "pytest -q tests/admin_v2 ../Tests/test_release_contracts.py" in workflow
    assert "node --check static/admin_v2/admin-v2.js" in workflow
    assert "context: backend" in workflow
    assert "file: ${{ github.workspace }}/Dockerfile" in workflow
    assert not (ROOT / "backend" / "Dockerfile").exists()
    assert "Disposable migration, health, backup, and restore rehearsal" in workflow
    assert "--source-revision \"$GITHUB_SHA\"" in workflow
    assert "zricethezav/gitleaks@sha256:" in workflow
    assert "dir /repo --no-banner --redact" in workflow
    assert "Audit processed iOS Release transport configuration" in workflow
    assert "PractentureReleaseDerivedData" in workflow
    assert "-destination 'generic/platform=iOS'" in workflow
    assert "Release-iphoneos/Practenture.app/Info.plist" in workflow
    assert "NSAppTransportSecurity" in workflow
    assert "https://api.practenture.com" in workflow
    assert "ios-release-config.json" in workflow
    assert "Upload immutable exact-SHA release artifact" in workflow
    assert "name: backend-release-${{ github.sha }}" in workflow
    assert "practenture-release-${{ github.sha }}.tar.gz.sha256" in workflow
    assert "if-no-files-found: error" in workflow
    assert "compression-level: 0" in workflow
    assert workflow.index("Disposable migration, health, backup, and restore rehearsal") < workflow.index(
        "Upload immutable exact-SHA release artifact"
    )
    assert workflow.index("verify_release_manifest.py") < workflow.index(
        "Upload immutable exact-SHA release artifact"
    )
    assert (ROOT / ".gitleaks.toml").is_file()
    for unsafe_live_script in (
        "test_sota_phase2.py",
        "test_multi_tenant.py",
        "test_login_permutations.py",
    ):
        assert unsafe_live_script not in workflow


def test_backend_image_excludes_databases_credentials_and_test_harnesses() -> None:
    dockerignore = BACKEND_DOCKERIGNORE.read_text().splitlines()
    for required in (".env", "*.db", "*.db-wal", "*.db-shm", "tests", "test_*.py"):
        assert required in dockerignore


def test_legacy_systemd_release_paths_fail_closed() -> None:
    for path in (LEGACY_RELEASE_VALIDATION, LEGACY_DEPLOY):
        script = path.read_text()
        assert "exit 64" in script
        assert script.index("exit 64") < script.index("===")


def test_rollback_runbook_matches_the_transactional_docker_workflow() -> None:
    runbook = ROLLBACK_RUNBOOK.read_text()
    assert "PRACTENTURE_RELEASE_RUN_ID" in runbook
    assert "backend-release-<SHA>" in runbook
    assert "Automatic activation rollback" in runbook
    assert "Post-promotion operator rollback: **BLOCKED" in runbook
    for retired_instruction in (
        "sudo systemctl stop practenture",
        "s3://practenture-backups",
        ".venv/bin/alembic downgrade",
        "/var/www/practenture",
    ):
        assert retired_instruction not in runbook


def test_git_does_not_track_runtime_state_or_credentials() -> None:
    assert "/.hermes/" in (ROOT / ".gitignore").read_text().splitlines()
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    forbidden = [
        path for path in tracked
        if path == ".env"
        or path.endswith("/.env")
        or "/__pycache__/" in f"/{path}"
        or path.endswith((".pyc", ".pyo", ".db", ".sqlite", ".sqlite3"))
    ]
    assert forbidden == []


def test_environment_example_contains_only_blank_secret_placeholders() -> None:
    values = {}
    for line in (ROOT / ".env.example").read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    for key in (
        "PRACTENTURE_JWT_SECRET",
        "PRACTENTURE_OWNER_PASSWORD",
        "PRACTENTURE_PROFESSOR_PASSWORD",
        "PRACTENTURE_SES_SENDER",
    ):
        assert values[key] == ""
