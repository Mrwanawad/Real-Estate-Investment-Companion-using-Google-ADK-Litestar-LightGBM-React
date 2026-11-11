"""One command local stack: embedded Postgres (pgserver) + migrations + seed + API.

Usage: python scripts/dev_stack.py [--port 8000] [--no-seed] [--provider fake|gemini|anthropic]
The Postgres data dir lives in the user's local app data (pgserver breaks on spaced paths).
Run the UI separately: cd frontend && npm run dev
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PGDATA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "reic" / "pgdata"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-seed", action="store_true")
    parser.add_argument("--provider", choices=["fake", "gemini", "anthropic"])
    args = parser.parse_args()

    import pgserver

    PGDATA.mkdir(parents=True, exist_ok=True)
    server = pgserver.get_server(PGDATA, cleanup_mode=None)
    base = server.get_uri().split("://", 1)[1]
    env = os.environ.copy()
    env["DATABASE_URL"] = f"postgresql+asyncpg://{base}"
    env.setdefault("BROKER_API_KEY", "dev-broker-key")
    env.setdefault("RATE_LIMIT_PER_MINUTE", "0")  # smoke and eval scripts burst past the limit
    if args.provider:
        env["LLM_PROVIDER"] = args.provider
    print(f"Postgres: postgresql://{base}")

    run = lambda *cmd: subprocess.run(cmd, cwd=ROOT, env=env, check=True)  # noqa: E731
    run(sys.executable, "-m", "alembic", "upgrade", "head")
    if not args.no_seed:
        run(sys.executable, "scripts/seed.py", env["DATABASE_URL"])
    print(f"API: http://localhost:{args.port}  (broker key: {env['BROKER_API_KEY']})")
    run(
        sys.executable,
        "-m",
        "uvicorn",
        "reic.bootstrap.app:create_app",
        "--factory",
        "--port",
        str(args.port),
    )


if __name__ == "__main__":
    main()
