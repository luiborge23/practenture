from __future__ import annotations

import hashlib
import json
from pathlib import Path
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
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci-cd.yml"
BACKEND_DOCKERIGNORE = ROOT / "backend" / ".dockerignore"
LEGACY_RELEASE_VALIDATION = ROOT / "backend" / "scripts" / "release_validation.sh"
LEGACY_DEPLOY = ROOT / "backend" / "scripts" / "deploy_backup_gated.sh"


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
    assert config.count(
        'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;'
    ) == 2
    assert "$proxy_add_x_forwarded_for" not in config
    assert config.count("proxy_set_header X-Forwarded-For $remote_addr;") == 9


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
    assert "${PRACTENTURE_JWT_SECRET:?PRACTENTURE_JWT_SECRET must be set}" in compose
    assert "${PRACTENTURE_OWNER_PASSWORD:?PRACTENTURE_OWNER_PASSWORD must be set}" in compose
    assert "${PRACTENTURE_PROFESSOR_PASSWORD:?PRACTENTURE_PROFESSOR_PASSWORD must be set}" in compose
    assert "FORWARDED_ALLOW_IPS=*" not in compose
    assert "FORWARDED_ALLOW_IPS=${FORWARDED_ALLOW_IPS:-172.16.0.0/12}" in compose
    assert "PRACTENTURE_CORS_ORIGINS=${PRACTENTURE_CORS_ORIGINS:-*}" not in compose
    assert "PRACTENTURE_CORS_ORIGINS=${PRACTENTURE_CORS_ORIGINS:-*}" not in dockerfile
    assert "PRACTENTURE_JWT_SECRET=" not in dockerfile
    assert "python:3.11-slim@sha256:" in dockerfile
    assert "nginx:alpine@sha256:" in compose


def test_migration_default_targets_authoritative_mounted_database() -> None:
    env = MIGRATION_ENV.read_text()
    assert "PRACTENTURE_DB_PATH" in env
    assert '"/data/practenture.db"' in env
    assert '"sqlite+aiosqlite:///data.db"' not in env


def test_deploy_consumes_verified_artifact_and_restores_release_on_rollback() -> None:
    deploy = DEPLOY.read_text()
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
    assert "Deployment requires HEAD to match origin/main exactly" in deploy
    assert '--source-revision "$SOURCE_REVISION"' in deploy
    assert 'EXPLICIT_JWT_SECRET="${PRACTENTURE_JWT_SECRET:-}"' in deploy
    assert 'JWT_SECRET="${EXPLICIT_JWT_SECRET:-${PRACTENTURE_JWT_SECRET:-}}"' in deploy
    assert 'TLS_ROLLBACK_DIR="/var/lib/practenture-deploy/tls-rollback-$DEPLOY_ID"' in deploy
    assert 'sudo ./scripts/restore_tls_renewal.sh "$TLS_ROLLBACK_DIR"' in deploy
    assert 'sudo test -f "$TLS_ROLLBACK_DIR/install-complete"' in deploy


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
    assert "no Let's Encrypt renewal configurations were found" in script
    assert "practenture-certbot-renew.service" in script
    assert "practenture-certbot-renew.timer" in script
    assert "OnCalendar=*-*-* 03,15:00:00" in script
    assert "RandomizedDelaySec=3600" in script
    assert "Persistent=true" in script
    assert "WEBROOT_PATH=\"/var/www/certbot\"" in script
    assert "ExecStart=$CERTBOT_BIN renew --quiet" in script
    assert '"$CERTBOT_BIN" reconfigure \\' in script
    assert '--cert-name "$cert_name"' in script
    assert "^authenticator = webroot$" in script
    assert 'cp -a "$work_dir/previous-renewal-configs" "$snapshot_staging/previous-renewal-configs"' in script
    assert script.index("trap cleanup EXIT") < script.index(
        'install -d -m 700 "$work_dir/previous-renewal-configs"'
    )
    assert '"$DOCKER_BIN" exec practenture-nginx nginx -t' in script
    assert '"$DOCKER_BIN" exec practenture-nginx nginx -s reload' in script
    assert 'systemctl is-active --quiet "$TIMER_NAME"' in script
    assert "--dry-run" in script
    assert "--run-deploy-hooks" in script
    assert "--no-random-sleep-on-renew" in script
    assert "TLS_RENEWAL_DRY_RUN_PASSED" in script
    assert 'systemctl enable "$TIMER_NAME"' in script
    assert 'systemctl start "$TIMER_NAME"' in script
    assert '"$SYSTEMD_ANALYZE" verify' in script
    assert 'systemctl is-enabled --quiet "$TIMER_NAME"' in script
    assert 'systemctl is-active --quiet "$TIMER_NAME"' in script
    assert "TLS_RENEWAL_TIMER_READY" in script
    assert "TLS_RENEWAL_PREVIOUS_CONFIGURATION_RESTORED" in script
    assert 'timer_was_active=1' in script
    assert 'touch "$snapshot_staging/timer-was-active"' in script
    assert 'snapshot_created=1' in script
    assert 'mv "$snapshot_staging" "$ROLLBACK_DIR"' in script
    assert 'touch "$ROLLBACK_DIR/install-complete"' in script
    assert 'if [ "$rc" -ne 0 ] && [ "$snapshot_created" -eq 1 ]' in script
    assert 'TLS_RENEWAL_RESTORE_INCOMPLETE; durable rollback snapshot retained' in script
    assert '[ "$restore_on_error" -eq 0 ] || [ "$restore_failed" -eq 0 ]' in script
    assert script.index('systemctl disable --now "$TIMER_NAME"') < script.index('if [ "$restore_failed" -eq 0 ]; then')
    assert 'if [ "$timer_existed" -eq 0 ] && [ -f "$SYSTEMD_DIR/$TIMER_NAME" ]' not in script
    assert 'if [ -f "$SYSTEMD_DIR/$TIMER_NAME" ]; then' in restore_script
    assert 'systemctl disable --now "$TIMER_NAME" >/dev/null 2>&1' in restore_script
    assert 'systemctl disable --now "$TIMER_NAME" >/dev/null 2>&1 || true' not in restore_script
    assert 'install -m 644 "$SNAPSHOT_DIR/previous-service"' in restore_script
    assert 'install -m 644 "$SNAPSHOT_DIR/previous-timer"' in restore_script
    assert 'if [ -f "$SNAPSHOT_DIR/timer-existed" ]; then' in restore_script
    assert 'install -m 755 "$SNAPSHOT_DIR/previous-hook"' in restore_script
    assert 'if [ ! -d "$SNAPSHOT_DIR/previous-renewal-configs" ]' in restore_script
    assert 'compgen -G "$SNAPSHOT_DIR/previous-renewal-configs/*.conf"' in restore_script
    assert 'install -m 600 "$renewal_config"' in restore_script
    assert restore_script.index("previous-renewal-configs/*.conf") < restore_script.index(
        'systemctl disable --now "$TIMER_NAME"'
    )
    assert "TLS_RENEWAL_DEPLOYMENT_ROLLBACK_RESTORED" in restore_script
    assert script.index('"$CERTBOT_BIN" renew \\') < script.index(
        'install -m 644 "$work_dir/$SERVICE_NAME"'
    )
    assert nginx.count("location ^~ /.well-known/acme-challenge/") == 2
    assert nginx.count("root /var/www/certbot;") == 2
    assert "- /var/www/certbot:/var/www/certbot:ro" in compose


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


def test_git_does_not_track_runtime_state_or_credentials() -> None:
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
