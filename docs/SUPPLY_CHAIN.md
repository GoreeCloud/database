# Dependency update and supply-chain review

## Scope and behavior

A reviewed `.github/dependabot.yml` now monitors GitHub Actions, Python (the FastAPI API project), npm (the React/Vite app), Android Gradle and the Dockerfiles/Compose manifests. Each ecosystem receives a weekly schedule with a small open-PR limit to avoid saturating a solo-maintainer CI budget.

**This creates proposed pull requests only.** It does not approve, merge, publish, deploy, migrate, or rotate any service. The protected `main` branch and the repository's required CI checks remain authoritative. An update is not accepted until source integrity, version behavior, license, compatibility, migrations, privacy and security impact are reviewed.

## Review checklist

1. Confirm release provenance and the actual version being updated, including transitive dependencies, declared licenses and known security advisories.
2. For Docker, verify base image provenance and pin an approved immutable digest before production use; this preview currently uses tagged base images and **is not reproducibly supply-chain locked**.
3. For Android/Gradle, confirm compatible Kotlin, Android Gradle Plugin, Compose and Material 3 dependencies and test a native debug build. A debug build is **not** a signed device release.
4. For Python and npm, validate semver-impact, dependency lockfile changes, API tests, web build and representative local/container integration.
5. Revisit the production threat model, GoreeShield data governance, Wardveil hardening and GoreeCloud Identity/Mesh integration claims. None are certified merely because Dependabot suggests an update.
6. Require all protected CI checks, review the diff/rollback, then merge through the authorized PR flow. No automatic production upgrade.

## Operational limits

- Automated update PRs depend on GitHub's feature availability, registry access and scheduling. `dependabot.yml` in a branch does not mean scheduled processing is enabled on the default branch.
- `pyproject.toml` uses broad compatible ranges and the Python API build lacks a fully approved transitive lockfile. Further reproducibility work is tracked under the production readiness issue #9.
- The Android CI job enables Gradle dependency/wrapper caching through the already installed `actions/setup-java` action, keyed by the native Gradle scripts and wrapper properties. This reduces repeated Maven fetches on cache hits; it does not guarantee cache availability or fix external HTTP 429 responses when a cache is cold.
- The registry may return errors or throttle requests; do not weaken verification to bypass rate limits. Dependabot alerts/advisories, SBOM generation, signing and full license provenance are separate features and remain unverified.
- Any future scheduled automation/notification outside GitHub requires separate configured authorization; none is created by this document.

Source of configuration syntax: [GitHub Dependabot documentation](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-version-updates). Configuration review date: 2026-11-25.
