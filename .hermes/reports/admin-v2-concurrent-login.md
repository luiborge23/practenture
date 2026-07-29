# Admin V2 concurrent login rotation

## Result

PASS — successful Admin V2 logins now create independent active sessions. Login rotation revokes only the prior active Admin V2 cookie presented by the same owner; absent, unknown, revoked, or foreign-owner cookies do not revoke sessions and are never adopted.

## Implementation

- `backend/admin_v2/routes.py`: forwards the request's Admin V2 cookie to the authentication service.
- `backend/admin_v2/service.py`: hashes the inbound cookie (when present) and passes only its hash to persistence; every response still receives a newly generated opaque token.
- `backend/admin_v2/repository.py`: in the existing MFA/session transaction, conditionally revokes only `token_hash + owner_user_id + active`, then inserts the fresh independent session.
- `backend/tests/admin_v2/test_concurrent_login_rotation.py`: barrier-driven, separate-TestClient race coverage for independent concurrent logins and two rotations of one shared old cookie, plus sequential rotation and fixation/foreign-cookie contracts.

## Verification

- Focused race suite: `4 passed` (`tests/admin_v2/test_concurrent_login_rotation.py`)
- All Admin V2 tests: `49 passed`
- Legacy suites: `31 passed, 1 skipped`
- Aggregate non-duplicated gate: `80 passed, 1 skipped`
- `git diff --check`: clean
- No network, production, source-worktree, or commit actions performed.
- Post-test status matched the captured baseline except for this intentional implementation/test/report work; the pre-existing deleted tracked bytecode artifact was left untouched.

## SHA-256

- `admin_v2/repository.py`: `9a9bcda42c7cd6121fef936030d051f1c897e790a053131270f02a26a22a5e82`
- `admin_v2/service.py`: `ce1ed8fefde3e0c3f6d426aedf6de18f0d664ca415fdbeeb697c241ecc51a154`
- `admin_v2/routes.py`: `ba980cb8d4123c1a8a11fd8a8892b10dc16f07368c053478f6df348d3d4e1502`
- `tests/admin_v2/test_concurrent_login_rotation.py`: `d5537a6d67eac80b2e1aeeb0fd8dfd18d6f894cf04b11185536495f114e9a269`
