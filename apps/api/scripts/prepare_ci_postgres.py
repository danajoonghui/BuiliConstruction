from __future__ import annotations

import asyncio
import os
import sys

import asyncpg

API_PASSWORD = "ci-api-password"
WORKER_PASSWORD = "ci-worker-password"
MIGRATOR_PASSWORD = "ci-migrator-password"


async def run(mode: str) -> None:
    connection = await asyncpg.connect(os.getenv("CI_POSTGRES_ADMIN_URL", "postgresql://postgres:postgres@127.0.0.1:5432/buili"))
    try:
        if mode == "bootstrap":
            await connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            for role, password in (
                ("buili_api", API_PASSWORD),
                ("buili_worker", WORKER_PASSWORD),
                ("buili_migrator", MIGRATOR_PASSWORD),
            ):
                if not await connection.fetchval("SELECT 1 FROM pg_roles WHERE rolname=$1", role):
                    await connection.execute(
                        f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT'
                    )
            await connection.execute("GRANT CONNECT ON DATABASE buili TO buili_api, buili_worker, buili_migrator")
            await connection.execute("GRANT USAGE, CREATE ON SCHEMA public TO buili_migrator")
            await connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            await connection.execute("REVOKE buili_worker FROM buili_api")
        elif mode == "grants":
            await connection.execute("GRANT USAGE ON SCHEMA public TO buili_api, buili_worker")
            await connection.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO buili_api, buili_worker"
            )
            await connection.execute(
                "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO buili_api, buili_worker"
            )
            await connection.execute(
                "ALTER DEFAULT PRIVILEGES FOR ROLE buili_migrator IN SCHEMA public "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO buili_api, buili_worker"
            )
            await connection.execute("REVOKE CREATE ON SCHEMA public FROM buili_api, buili_worker")
            await connection.execute("REVOKE buili_worker FROM buili_api")
        else:
            raise SystemExit("usage: prepare_ci_postgres.py bootstrap|grants")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1] if len(sys.argv) > 1 else ""))
