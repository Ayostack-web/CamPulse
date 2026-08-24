"""RLS audit harness.

Verifies the live database against ``app.db_rls_baseline`` so a future
migration can never silently drop coverage again:

1. Static drift guard  -- every model table must have a baseline spec.
2. Catalog check       -- RLS enabled AND forced on every covered table,
                          and no unknown public table slipping through.
3. Behavioral probes   -- impersonates a dedicated least-privilege role
                          (SET ROLE) and proves that, under
                          ``app.current_user_id``, one student cannot read
                          or write another's rows, while the documented
                          service path (context absent) still passes.

The catalog/probe checks auto-heal ONLY databases whose name contains
"test" (CI) or when RLS_AUTO_BASELINE=1 is exported. Point DATABASE_URL at
a shared/dev database and they verify without mutating anything; failures
there are fixed by running ``alembic upgrade head`` (migration 030).
"""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio.engine import AsyncConnection

from app.core.config import get_settings
from app.database import engine
from app.db_rls_baseline import (
    EXTRA_BASELINE_TABLES,
    PROBE_ROLE,
    PROBE_TABLES,
    SPEC_BY_TABLE,
    baseline_statements,
)

pytestmark = pytest.mark.usefixtures("db_schema")


def _auto_baseline_allowed(db_name: str) -> bool:
    """Auto-healing must never touch shared/managed databases by accident."""
    host = (make_url(get_settings().database_url).host or "").lower()
    if "supabase" in host or "pooler" in host:
        return os.environ.get("RLS_AUTO_BASELINE") == "FORCE"
    return "test" in db_name or os.environ.get("RLS_AUTO_BASELINE") == "1"


@pytest_asyncio.fixture(scope="module")
async def admin_conn():
    async with engine.connect() as conn:
        db_name = (await conn.execute(text("SELECT current_database()"))).scalar_one()
        applied = False
        if _auto_baseline_allowed(db_name):
            for stmt in baseline_statements():
                await conn.execute(text(stmt))
            await conn.commit()
            applied = True
        yield _Admin(conn, db_name, applied)


class _Admin:
    def __init__(self, conn: AsyncConnection, db_name: str, applied: bool):
        self.conn = conn
        self.db_name = db_name
        self.applied = applied


# ── 1. Static drift guard ────────────────────────────────────────────


def test_every_model_table_has_a_baseline_spec():
    from app.models import Base

    model_tables = {t.name for t in Base.metadata.sorted_tables}
    missing = sorted(model_tables - set(SPEC_BY_TABLE))
    assert not missing, (
        "Tables exist in models.py but have NO entry in app/db_rls_baseline.py. "
        f"They would ship without row-level security: {missing}. "
        "Add a TableSpec for each before merging."
    )


# ── 2. Live catalog check ────────────────────────────────────────────


async def test_rls_enabled_and_forced(admin_conn):
    if not admin_conn.applied:
        pytest.skip(
            f"Database '{admin_conn.db_name}' is not an auto-baseline target "
            "(name must contain 'test' or set RLS_AUTO_BASELINE=1); "
            "run `alembic upgrade head` to bring it to the baseline first."
        )

    rows = await admin_conn.conn.execute(text(
        "SELECT c.relname AS table_name, c.relrowsecurity AS enabled, "
        "       c.relforcerowsecurity AS forced "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r'"
    ))
    catalog = {r.table_name: (r.enabled, r.forced) for r in rows}

    problems = []
    for table in SPEC_BY_TABLE:
        state = catalog.get(table)
        if state is None:
            problems.append(f"{table}: covered by baseline but missing from database")
        elif not state[0]:
            problems.append(f"{table}: RLS not enabled")
        elif not state[1]:
            problems.append(f"{table}: RLS enabled but NOT forced (owners bypass it)")

    known = set(SPEC_BY_TABLE) | {"alembic_version", "_prisma_migrations"}
    unknown = sorted(set(catalog) - known - EXTRA_BASELINE_TABLES)
    for t in unknown:
        problems.append(f"{t}: exists in database but has no baseline spec")

    assert not problems, "RLS audit failed:\n  " + "\n  ".join(problems)


# ── 3. Behavioral probes through a least-privilege role ─────────────


@pytest_asyncio.fixture
async def probe_role_setup(admin_conn):
    """Create the least-privilege probe role; probes impersonate it via
    SET ROLE on a pooled connection (works through Supavisor, which rejects
    tenant-less logins)."""
    if not admin_conn.applied:
        pytest.skip("baseline not applied on this database; see test_rls_enabled_and_forced")
    conn = admin_conn.conn
    await conn.execute(text(f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{PROBE_ROLE}') THEN
                CREATE ROLE {PROBE_ROLE} NOLOGIN;
            END IF;
        END $$;
    """))
    await conn.execute(text(f"GRANT CONNECT ON DATABASE {admin_conn.db_name} TO {PROBE_ROLE}"))
    await conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {PROBE_ROLE}"))
    grants = ", ".join(PROBE_TABLES)
    await conn.execute(text(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {grants} TO {PROBE_ROLE}"
    ))
    # PG16+: SET ROLE requires explicit membership, even for the creator.
    await conn.execute(text(f"GRANT {PROBE_ROLE} TO current_user"))
    await conn.commit()


_OWNERSHIP_COL = {
    "user_privacy": "user_id",
    "vault_items": "user_id",
    "notifications": "user_id",
    "points_transactions": "user_id",
    "subscriptions": "user_id",
    "flashcard_decks": "user_id",
}


_TIMESTAMP_COLUMNS = {
    "user_privacy": ("created_at", "updated_at"),
    "notifications": ("delivered_at", "created_at"),
    "points_transactions": ("created_at",),
    "vault_items": ("saved_at",),
    "subscriptions": ("created_at", "updated_at"),
    "flashcard_decks": ("created_at", "updated_at"),
}


def _seed_rows(table: str, user_id: str) -> dict[str, object]:
    row: dict[str, object] = {
        "id": str(uuid.uuid4()),
        _OWNERSHIP_COL[table]: user_id,
    }
    # Live tables were created by older migrations without DB-side defaults.
    for ts in _TIMESTAMP_COLUMNS.get(table, ()):
        row[ts] = "2026-01-01 00:00:00+00"
    if table == "vault_items":
        row.update(title="probe", local_blob_id="probe-blob")
    elif table == "notifications":
        row.update(kind="probe", title="probe")
    elif table == "points_transactions":
        row.update(amount=1, reason="rls_probe")
    elif table == "subscriptions":
        row.update(reference=f"probe-{uuid.uuid4()}", plan="free", status="ACTIVE")
    elif table == "flashcard_decks":
        row.update(title="probe")
    return row


async def test_one_student_cannot_read_or_write_another_students_rows(probe_role_setup, admin_conn):
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    seeded: list[tuple[str, str]] = []

    async def _seed(table: str, user_id: str) -> None:
        row = _seed_rows(table, user_id)
        cols = ", ".join(row)
        placeholders = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in row.values())
        await admin_conn.conn.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"))
        seeded.append((table, user_id))

    try:
        for user_id in (user_a, user_b):
            await admin_conn.conn.execute(text(
                "INSERT INTO users (id, full_name, created_at, updated_at) "
                f"VALUES ('{user_id}', 'RLS Probe', '2026-01-01 00:00:00+00', "
                "'2026-01-01 00:00:00+00')"
            ))
        for table in PROBE_TABLES:
            await _seed(table, user_a)
            await _seed(table, user_b)
        await admin_conn.conn.commit()
    except Exception:
        await admin_conn.conn.rollback()
        raise

    probe = await engine.connect()
    try:
        await probe.execute(text(f"SET ROLE {PROBE_ROLE}"))

        # User context: isolation must hold.
        await probe.execute(text(
            "SELECT set_config('app.current_user_id', :uid, true)"
        ), {"uid": user_a})

        for table in PROBE_TABLES:
            col = _OWNERSHIP_COL[table]
            own = (await probe.execute(text(
                f"SELECT count(*) FROM {table} WHERE {col} = '{user_a}'"
            ))).scalar_one()
            foreign = (await probe.execute(text(
                f"SELECT count(*) FROM {table} WHERE {col} = '{user_b}'"
            ))).scalar_one()
            assert own == 1, f"{table}: user A should see exactly their own row, saw {own}"
            assert foreign == 0, (
                f"{table}: user A can READ user B's rows through RLS context"
            )

        # Forged writes must be rejected. Each attempt runs inside a
        # SAVEPOINT so the aborted statement does not end our transaction
        # (which would clear the user context for the remaining tables).
        for table in PROBE_TABLES:
            col = _OWNERSHIP_COL[table]
            forged = _seed_rows(table, user_b)
            cols = ", ".join(forged)
            placeholders = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in forged.values())
            sp = await probe.begin_nested()
            try:
                with pytest.raises(Exception):  # noqa: B017 - WITH CHECK must reject
                    await probe.execute(text(
                        f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
                    ))
                await sp.rollback()
            except BaseException:
                await sp.rollback()
                raise

        # Documented service path: no context -> full access (workers).
        await probe.rollback()
        for table in PROBE_TABLES:
            total = (await probe.execute(text(
                f"SELECT count(*) FROM {table}"
            ))).scalar_one()
            assert total >= 2, (
                f"{table}: service path (no user context) is blocked, "
                "breaking the worker contract in app/db_rls.py"
            )
    finally:
        try:
            await probe.rollback()
            await probe.execute(text("RESET ROLE"))
        except Exception:
            pass
        await probe.close()
        await admin_conn.conn.rollback()
        for table, user_id in reversed(seeded):
            col = _OWNERSHIP_COL[table]
            await admin_conn.conn.execute(text(
                f"DELETE FROM {table} WHERE {col} = '{user_id}'"
            ))
        await admin_conn.conn.execute(text(
            f"DELETE FROM users WHERE id IN ('{user_a}', '{user_b}')"
        ))
        await admin_conn.conn.commit()
