# GoreeCloud Database edge-function execution laboratory

**Status: opt-in CLI research preview, not a deployable edge-functions service.** The [Wasmtime](https://github.com/bytecodealliance/wasmtime) runtime (official Python version `51.0.0`, Apache-2.0 with LLVM exception) executes a first-party **pure WebAssembly** demo. No public route, listener, data store, native APK integration, credential forwarding, egress, event trigger, dynamic deployment or project provisioning is present.

## Model and safeguards

- The CLI accepts only `--module-id` and a bounded integer `--input`. Module IDs must match a strict short identifier and exist in `infra/edge/approved.json`. Approved WAT source is loaded exclusively from `infra/edge/modules/` after exact SHA-256 verification. Symlinked, missing, oversized, tampered, unapproved and path-traversal modules are denied before compilation.
- `wasmtime==51.0.0` is pinned for this preview. `wasmtime.Module` compiles the SHA-verified WAT. **All Wasm imports are rejected**; there is no WASI linkage, file access, socket API, HTTP, process execution, environment variables or host functions available to the guest. The only allowed export is a `run(i32)->i32` function.
- The engine consumes Wasmtime fuel (100,000), uses a 1 MiB Wasm stack and a `Store.set_limits` cap. The preview forbids linear-memory and table creation (both counts set to zero), and permits one instance. Infinite loops trap on fuel exhaustion. Guest output is one integer, no raw stack traces or untrusted messages printed.
- The input is a signed integer from -1,000,000 through +1,000,000, and WAT source is bounded to 8 KiB. A committed SHA manifest records the reviewed source; it is **not** a cryptographic signature, CI attestation or proof of trusted publishers. Source and manifest can both be modified by an authorized maintainer and require protected review.

## Run on an authorized disposable development host

```sh
# A fresh environment, not a server deployment:
python3 -m pip install 'wasmtime==51.0.0'
# Read-only SHA-256 approval check (no Wasm execution):
python3 -c "from scripts.edge_preview import approved_source; approved_source('double')"
# Explicit pure Wasm example:
python3 scripts/edge_preview.py --module-id double --input 7
# Expected: {"module": "double", "result": 14, "status": "local-preview"}
# Test import denial, fuel exhaustion, memory restrictions and manifest drift:
python3 -m unittest scripts.test_edge_preview -v
```

All source and CI scripts live in this repository. The optional `edge-preview` CI job installs the pinned Wasmtime Python wheel and runs the pure code with regression tests. Other CI jobs do not install the runtime; their source-only integrity tests can skip guest-execution cases safely. This is a **new development dependency**, not a runtime dependency of the existing management API or Android/web apps.

## Limitations and production gate

This CLI is **not a production-grade sandbox**: it executes inside the developer/CI host process with Wasmtime's native runtime, without a separate OS process jail, seccomp/AppArmor/Bubblewrap policy, independently enforced wall-clock timeout or per-tenant CPU/memory accounting. Compiler/native-runtime defects, excessive resource use during compilation and supply-chain compromise remain in scope. Never pass untrusted customer modules or sensitive data to this laboratory, and never run it on production VPS nodes.

Before any deployed edge function capability: approved provenance signatures and artifact storage, independent per-call sandbox isolation with OS-level resource/egress controls, wall-clock interruption, tenant admission, audit events, explicit endpoint authentication and scopes, GoreeShield consent, Wardveil scanning, Mesh event contracts, rollout/rollback, quota enforcement, real load/fuzz tests and infrastructure authorization are mandatory.

Tracked under [issue #8](https://github.com/GoreeCloud/database/issues/8). No existing task or production runtime is considered complete by this preview.
