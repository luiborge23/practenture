# Practenture Deployment and Rollback Runbook

## Scope

Production uses the repository-root `ec2-deploy.sh` workflow, Docker Compose,
immutable source releases, and SQLite online backups. The former systemd and S3
procedure is retired and must not be used.

This runbook distinguishes two different situations:

1. **Activation failure:** `ec2-deploy.sh deploy` performs an automatic,
   transaction-style rollback before promotion is committed.
2. **Incident after successful promotion:** an automated and fault-injected
   operator command is not implemented yet. This remains a release-readiness
   blocker; do not improvise a database downgrade or manually retag containers.

## Release prerequisites

Before invoking a deployment, require all of the following:

- a clean worktree with `HEAD == origin/main`;
- a completed successful `push` run of `Practenture Quality Gates` for that
  exact SHA;
- zero annotations on that run's check suite;
- the run's `backend-release-<SHA>` artifact and checksum;
- production credentials and provider configuration validated by the deploy
  preflight without printing secret values;
- production host access and current health confirmed;
- a maintenance owner present for the entire operation.

Invoke deployment only with the authorized run ID:

```bash
PRACTENTURE_RELEASE_RUN_ID=<successful-run-id> ./ec2-deploy.sh deploy
```

The script downloads that run's exact-SHA archive, validates its checksum and
manifest, and requires it to be byte-identical to a deterministic build from
the clean local tree before uploading anything to EC2.

## Automatic activation rollback

Before stopping the current backend, the deploy transaction retains:

- the prior immutable release path;
- a tagged prior backend image;
- a SQLite online backup in `~/practenture-backups/predeploy-<DEPLOY_ID>.db`;
- a disposable copy used for an integrity-checked restore drill;
- a TLS renewal rollback snapshot while TLS configuration is changing.

Promotion is allowed only after migration, container health, image revision,
Nginx, TLS renewal installation, and public HTTPS health gates pass. If a gate
fails before promotion commits, the script restores the retained image,
database, release link, and TLS state, then verifies public HTTPS health.

Treat either of these messages as an incident requiring immediate inspection:

- `An existing candidate activation is indeterminate`
- `Deployment and automatic application rollback both failed`

Do not rerun deployment after an indeterminate activation until the retained
markers, image, backup, release links, container state, and database integrity
have been inspected and documented.

## Retained evidence

The deployment keeps pre-deployment SQLite backups for 30 days and preserves
immutable release directories and rollback image tags. A successful deployment
removes only the temporary in-volume backup and TLS transaction snapshot after
promotion commits.

Read-only checks on the host should confirm:

- `PRAGMA integrity_check` returns `ok` for the live database and retained
  backup;
- the live Alembic revision is the expected single head;
- the `practenture-current` link resolves to the expected immutable release;
- the running image label equals the promoted Git SHA;
- `https://practenture.com/api/health` succeeds through the local Nginx path.

Never print `.env`, provider private keys, JWT values, passwords, or database
contents into logs or incident notes.

## Post-promotion incident policy

There is currently no supported `ec2-deploy.sh rollback` command. Although the
prior release, image, and 30-day database backup are retained, manually combining
them has not passed executable fault-injection coverage. Consequently:

- post-promotion rollback is **BLOCKED**, not assumed ready;
- do not run the retired systemd commands;
- do not run `alembic downgrade` against production;
- do not restore a database with `cp` while a service can access it;
- do not retag or restart containers without a reviewed, incident-specific
  recovery plan and a tested roll-forward path.

Closure requires an automated post-promotion rollback command that preserves a
roll-forward snapshot, restores the prior release/image/database as one
transaction, validates revision and public HTTPS health, and automatically
rolls forward if rollback qualification fails. Its failure boundaries must be
exercised in disposable infrastructure before this gate can pass.

## Evidence to retain

For every deployment or rollback attempt, retain without secrets:

- source SHA and GitHub Actions run ID;
- release artifact SHA-256;
- previous and candidate release paths;
- deployment ID and backup filename;
- migration revision before and after;
- image revision before and after;
- health-check results;
- whether promotion, automatic rollback, or roll-forward completed;
- CI artifacts and check-suite annotation count.

## Current readiness classification

- Exact-SHA CI artifact production and activation rollback: required gates.
- Automatic rollback during failed activation: implemented by
  `ec2-deploy.sh deploy`.
- Post-promotion operator rollback: **BLOCKED until implemented and rehearsed**.