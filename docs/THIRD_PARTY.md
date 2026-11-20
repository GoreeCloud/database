# Third-party source and license register

The repository contains **first-party glue code**, deployment configuration, web and Android clients, not a copied fork of the entire upstream stacks. Review licenses again when vendoring or redistributing upstream source/binaries.

| Component | Version/reference | Upstream | License | Status |
| --- | --- | --- | --- | --- |
| PostgreSQL | Docker image `17.12-alpine3.23` | https://www.postgresql.org/ | PostgreSQL License | Container integration |
| PostgREST | Docker image `v16.6` | https://github.com/PostgREST/postgrest | MIT | Container integration |
| Python | `3.12-slim` base image | https://www.python.org/ | PSF | Runtime |
| FastAPI | `>=0.116,<1` | https://github.com/fastapi/fastapi | MIT | Backend dependency |
| psycopg | `>=3.2,<4` | https://github.com/psycopg/psycopg | LGPL-3.0-or-later | Backend dependency (no vendored modifications) |
| React | `^19.1.1` | https://github.com/facebook/react | MIT | Web dependency |
| Vite | `^7.1.0` | https://github.com/vitejs/vite | MIT | Web toolchain |
| Kotlin / Compose | Gradle-configured | https://kotlinlang.org/ / https://developer.android.com/compose | Apache-2.0 | Android framework |
| SeaweedFS | Candidate only | https://github.com/seaweedfs/seaweedfs | Apache-2.0 | **Not integrated** |
| Supabase Auth / GoTrue | Candidate only | https://github.com/supabase/auth | MIT | **Not integrated** |

Image tags and bounded Python versions are a development baseline, not immutable digests or locked whole dependency graphs. Before a public release, lock image digests, regenerate dependency locks and verify notices. Do not conflate links to upstream source with a vendored copy or GoreeCloud-authored source.
