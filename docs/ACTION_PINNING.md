# GitHub Actions immutable source pins — development supply-chain control

The `.github/workflows/ci.yml` file uses **exact 40-character Git commit SHAs**, not mutable tags. The source-only `infra/ci/actions-lock.json` records the corresponding upstream patch-release tag and commit for each action. The list was checked against the official upstream repository refs on November 25, 2026.

| Action | Upstream tag | Pinned Git commit |
| --- | --- | --- |
| `actions/checkout` | v4.2.2 | `11bd71901bbe5b1630ceea73d27597364c9af683` |
| `actions/setup-python` | v5.6.0 | `a26af69be951a213d495a4c3e4e4022e16d87065` |
| `actions/setup-node` | v4.4.0 | `49933ea5288caeca8642d1e84afbd3f7d6820020` |
| `actions/setup-java` | v4.7.1 | `c5195efecf7bdfc987ee8bae7a71cb8b11521c00` |
| `actions/upload-artifact` | v4.6.2 | `ea165f8d65b6e75b540449e92b4886f43607fa02` |
| `android-actions/setup-android` | v4.0.4 | `be39fa834029ff78f1a44aa3bb0819b8fc2bd8fd` |

## Validation

```sh
# No network activity, no dependencies, credentials, or builds:
python3 scripts/check_ci_actions.py
python3 -m unittest scripts.test_ci_actions -v
```

The source checker rejects unreviewed action names, mutable/partial refs, malformed SHA-40 pins, mismatched version comments, manifest mutations and missing actions, as well as symbolic links to alternate CI files. Protected CI runs it as part of `config`. CI's actual action execution provides integration evidence that each SHA resolves; this document does **not** prove upstream release provenance, binary reproducibility or absence of compromised dependencies.

## Updating a pin safely

1. Verify the official publisher and the upstream action code/changelog. Retrieve the exact official patch-release tag object and ensure it directly targets a commit.
2. Inspect action permissions, dependencies, compatible Node runtime and transitive actions. Assess maintenance/security advisories and existing branch policy.
3. Change the `uses:` digest, human-readable version comment and lockfile entry **together** in a protected PR. Update regression tests if adding a new approved action.
4. Run source integrity, native/web/API builds, disposable PostgreSQL and optional SeaweedFS/edge jobs. Merge only with the five protected checks and relevant optional jobs green.
5. Revert via reviewed PR/commit if a pinned update fails. Never silently update to a mutable tag.

## Remaining supply-chain gates

Container images are still version-tagged and **not pinned to multi-platform OCI digest**. Python application requirements include constrained ranges, Node uses a lockfile, Android uses Gradle wrapper and libraries; exact dependency SBOM, verified image signatures, vulnerability advisory triage, encrypted artifacts, reproducible builds and signed release provenance remain incomplete. These pins reduce CI action drift but **do not make production deployment safe**.
