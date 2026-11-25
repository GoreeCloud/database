# Third-party source and license register

The repository contains **first-party glue code**, deployment configuration, web and Android clients, not a copied fork of the entire upstream stacks. Review licenses again when vendoring or redistributing upstream source/binaries.

| Component | Version/reference | Upstream | License | Status |
| --- | --- | --- | --- | --- |
| PostgreSQL | Docker image `17.12-alpine3.23` | https://www.postgresql.org/ | PostgreSQL License | Container integration |
| PostgREST | Docker image `v16.6` | https://github.com/PostgREST/postgrest | MIT | Container integration |
| Python | `3.12-slim` base image | https://www.python.org/ | PSF | Runtime |
| FastAPI | `>=0.116,<1` | https://github.com/fastapi/fastapi | MIT | Backend dependency |
| psycopg | `>=3.2,<4` | https://github.com/psycopg/psycopg | LGPL-3.0-or-later | Backend dependency (no vendored modifications) |
| PyJWT | `>=2.15.1,<3` with `crypto` extra | https://github.com/jpadilla/pyjwt | MIT | Backend dependency; opt-in JWKS/RSA verification, minimum version includes 2026 algorithm/redirect hardening |
| cryptography | Transitive through `PyJWT[crypto]` | https://github.com/pyca/cryptography | Apache-2.0 OR BSD-3-Clause | RSA verification dependency; version resolved by pip |
| React | `^19.1.1` | https://github.com/facebook/react | MIT | Web dependency |
| Vite | `^7.1.0` | https://github.com/vitejs/vite | MIT | Web toolchain |
| Kotlin / Compose | Gradle-configured | https://kotlinlang.org/ / https://developer.android.com/compose | Apache-2.0 | Android framework |
| Wasmtime (Bytecode Alliance) | Optional Python wheel `wasmtime==51.0.0` | https://github.com/bytecodealliance/wasmtime | Apache-2.0 WITH LLVM-exception | Local pure Wasm research lab only; no hosted edge runtime |
| SeaweedFS | Opt-in Docker image `chrislusf/seaweedfs:4.54` | https://github.com/seaweedfs/seaweedfs | Apache-2.0 | Separate signed S3 protocol sandbox, **not yet connected to Database storage APIs** |
| Supabase Auth / GoTrue | Candidate only | https://github.com/supabase/auth | MIT | **Not integrated** |

Image tags and bounded Python versions are a development baseline, not immutable digests or locked whole dependency graphs. Before a public release, lock image digests, regenerate dependency locks and verify notices. Do not conflate links to upstream source with a vendored copy or GoreeCloud-authored source.
