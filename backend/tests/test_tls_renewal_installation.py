from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install_tls_renewal.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _prepare_test_root(root: Path) -> dict[str, str]:
    bin_dir = root / "bin"
    renewal_dir = root / "etc" / "letsencrypt" / "renewal"
    systemd_dir = root / "etc" / "systemd" / "system"
    state_dir = root / "var" / "lib" / "practenture-deploy"
    bin_dir.mkdir(parents=True)
    renewal_dir.mkdir(parents=True)
    systemd_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)

    for cert_name in ("api.practenture.com", "www.practenture.com"):
        (renewal_dir / f"{cert_name}.conf").write_text(
            "authenticator = nginx\nwebroot_path = /obsolete\n",
            encoding="utf-8",
        )

    _write_executable(
        bin_dir / "certbot",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$FAKE_ROOT/certbot.log"
if [ "${1:-}" = "reconfigure" ]; then
    cert_name=""
    while [ "$#" -gt 0 ]; do
        if [ "$1" = "--cert-name" ]; then cert_name=$2; shift 2; else shift; fi
    done
    test -n "$cert_name"
    printf 'authenticator = webroot\nwebroot_path = %s/var/www/certbot,\n' \
        "$FAKE_ROOT" > "$FAKE_ROOT/etc/letsencrypt/renewal/$cert_name.conf"
fi
""",
    )
    _write_executable(bin_dir / "docker", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(bin_dir / "systemd-analyze", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        bin_dir / "systemctl",
        """#!/usr/bin/env bash
set -euo pipefail
command=${1:-}
case "$command" in
  is-enabled) test -f "$FAKE_ROOT/enabled" ;;
  is-active) test -f "$FAKE_ROOT/active" ;;
  enable) touch "$FAKE_ROOT/enabled" ;;
  restart|start) touch "$FAKE_ROOT/active" ;;
  disable) rm -f "$FAKE_ROOT/enabled" "$FAKE_ROOT/active" ;;
  stop) rm -f "$FAKE_ROOT/active" ;;
  show) printf 'Tue 2099-01-01 03:00:00 UTC\n' ;;
  daemon-reload) ;;
  *) exit 0 ;;
esac
""",
    )

    env = os.environ.copy()
    env.update(
        {
            "PRACTENTURE_TLS_TESTING": "1",
            "PRACTENTURE_TLS_TEST_ROOT": str(root),
            "FAKE_ROOT": str(root),
        }
    )
    return env


def _run_installer(root: Path, env: dict[str, str], release: str) -> subprocess.CompletedProcess[str]:
    rollback = root / "var" / "lib" / "practenture-deploy" / f"tls-rollback-{release}"
    run_env = env | {"PRACTENTURE_TLS_ROLLBACK_DIR": str(rollback)}
    result = subprocess.run(
        ["bash", str(INSTALLER)],
        check=False,
        cwd=REPO_ROOT,
        env=run_env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, (
        f"installer exited {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return result


def test_tls_installer_avoids_redundant_acme_calls_and_detects_drift(tmp_path: Path):
    root = tmp_path / "host"
    env = _prepare_test_root(root)

    first = _run_installer(root, env, "first")
    calls_after_first = (root / "certbot.log").read_text(encoding="utf-8").splitlines()
    assert len(calls_after_first) == 3
    assert sum(line.startswith("reconfigure ") for line in calls_after_first) == 2
    assert sum(line.startswith("renew ") and "--dry-run" in line for line in calls_after_first) == 1
    assert "TLS_RENEWAL_DRY_RUN_PASSED" in first.stdout
    assert (root / "var/lib/practenture-deploy/tls-renewal-attestation-v1").is_file()

    second = _run_installer(root, env, "second")
    assert "TLS_RENEWAL_ATTESTATION_VERIFIED" in second.stdout
    assert (root / "certbot.log").read_text(encoding="utf-8").splitlines() == calls_after_first

    # Adopt an exact pre-attestation installation without contacting ACME. This
    # is the one-time migration path for the already validated production host.
    (root / "var/lib/practenture-deploy/tls-renewal-attestation-v1").unlink()
    adopted = _run_installer(root, env, "adopted")
    assert "TLS_RENEWAL_EXISTING_CONFIGURATION_ADOPTED" in adopted.stdout
    assert (root / "certbot.log").read_text(encoding="utf-8").splitlines() == calls_after_first

    # Any managed-byte drift must fail closed into full reconfiguration.
    hook = root / "etc/letsencrypt/renewal-hooks/deploy/practenture-nginx-reload"
    hook.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    drift = _run_installer(root, env, "drift")
    calls_after_drift = (root / "certbot.log").read_text(encoding="utf-8").splitlines()
    assert "TLS_RENEWAL_DRY_RUN_PASSED" in drift.stdout
    assert len(calls_after_drift) == len(calls_after_first) + 3
