from __future__ import annotations

import hashlib
import json
from pathlib import Path
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


def test_admin_v2_nginx_routes_precede_spa_and_preserve_prefix() -> None:
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
    assert "location /api/ {\n        proxy_pass http://practenture-backend:8000/;" in config
    admin_block = config[config.index("location = /admin {") : shell]
    assert "proxy_pass http://practenture-backend:8000/admin-v2;" in admin_block
    assert config.count(
        'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;'
    ) == 2


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
    assert "PRACTENTURE_CORS_ORIGINS=${PRACTENTURE_CORS_ORIGINS:-*}" not in compose
    assert "PRACTENTURE_CORS_ORIGINS=${PRACTENTURE_CORS_ORIGINS:-*}" not in dockerfile
    assert "PRACTENTURE_JWT_SECRET=" not in dockerfile


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
    assert "ln -sfn \"$PREVIOUS_RELEASE\" \"$HOME/practenture-current\"" in deploy
    assert "docker inspect practenture-backend" in deploy
    assert "docker inspect bizsim-backend" not in deploy
    assert "curl -sf http://127.0.0.1:8000/api/health" in deploy
    assert "Professor login: professor /" not in deploy


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
        assert not any("/.env" in f"/{name}" or "__pycache__" in name for name in names)
        extracted = archive.extractfile("RELEASE-MANIFEST.json")
        assert extracted is not None
        manifest = json.load(cast(IO[bytes], extracted))
        assert manifest["formatVersion"] == 1
        assert manifest["files"]
