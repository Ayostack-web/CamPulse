"""RLS baseline: single source of truth for row-level security state.

Shared by ``alembic`` migration 030 and the RLS audit test-suite so the
migration, CI, and local verification can never drift apart.

Design contract (matches ``app.db_rls.apply_rls_context``):

* Every request that should see *user-scoped* rows sets
  ``app.current_user_id`` (transaction-local) before querying.
* Policies therefore read ``current_setting('app.current_user_id', true)``:
  - when SET     -> only rows owned by (or shared with) that user pass;
  - when ABSENT  -> everything passes, because Celery workers, migrations
    and other service paths run without a user context.

Migration 004 defined a ``_NO_CTX`` escape hatch but never used it in any
policy, and ten later tables were never added at all.  This module encodes
the *intended* end state; ``apply_rls_baseline`` is idempotent and safe to
re-run against any environment.
"""
from __future__ import annotations

from dataclasses import dataclass

_NOCTX = "current_setting('app.current_user_id', true) IS NULL"
_UID = "current_setting('app.current_user_id', true)::uuid"


def _owned(predicate: str) -> str:
    """Owner-only access, with the documented service-path escape."""
    return f"(({predicate}) OR {_NOCTX})"


@dataclass(frozen=True)
class TableSpec:
    table: str
    kind: str  # "reference" | "service" | "owner"
    select: str = "true"
    insert: str = "true"
    update: str = "true"
    delete: str = "true"


def _owner(table: str, col: str) -> TableSpec:
    pred = _owned(f"{table}.{col} = {_UID}")
    # notifications INSERT is service-only: users cannot forge notifications
    # for other users. All other CRUD ops follow the standard owner pattern.
    if table == "notifications":
        return TableSpec(table, "owner", pred, _NOCTX, pred, pred)
    return TableSpec(table, "owner", pred, pred, pred, pred)


# ── Reference / service tables: no per-user privacy boundary ─────────
_REFERENCE = ["colleges", "departments", "courses", "badges", "reward_items",
              "universities", "department_catalog"]
_SERVICE = ["material_chunks", "academic_agent_tasks", "uploaded_files",
            "solved_bank_batches", "solved_questions"]

# ── Owner-scoped tables ───────────────────────────────────────────────
_OWNER_COLUMNS = {
    "users": "id",
    "user_privacy": "user_id",
    "user_emails": "user_id",
    "connected_accounts": "user_id",
    "imported_files": "user_id",
    "vault_items": "user_id",
    "user_badges": "user_id",
    "user_streaks": "user_id",
    "points_transactions": "user_id",
    "user_reward_purchases": "user_id",
    "notifications": "user_id",
    "rsvps": "user_id",
    "lessons": "host_id",
    "topics": "author_id",
    "materials": "uploader_id",
    "topic_questions": "author_id",
    "question_answers": "author_id",
    "ai_usage": "user_id",
    "subscriptions": "user_id",
    "flashcard_decks": "user_id",
    "material_unlocks": "user_id",
}

_MEMBER = (
    f"EXISTS (SELECT 1 FROM conversation_members cm "
    f"WHERE cm.conversation_id = conversations.id AND cm.user_id = {_UID})"
)
_MSG_MEMBER = (
    f"EXISTS (SELECT 1 FROM conversation_members cm "
    f"WHERE cm.conversation_id = messages.conversation_id AND cm.user_id = {_UID})"
)
_MRR_MEMBER = (
    f"EXISTS (SELECT 1 FROM conversation_members cm "
    f"JOIN messages m ON m.id = message_read_receipts.message_id "
    f"WHERE cm.conversation_id = m.conversation_id AND cm.user_id = {_UID})"
)

# Self-contained variant for policies ON conversation_members itself
# (004's version referenced conversations.* out of scope and always failed).
_CM_MEMBER = (
    f"EXISTS (SELECT 1 FROM conversation_members me "
    f"WHERE me.conversation_id = conversation_members.conversation_id "
    f"AND me.user_id = {_UID})"
)

_DECK_OWNED = [
    _owned(
        f"EXISTS (SELECT 1 FROM flashcard_decks d "
        f"WHERE d.id = flashcards.deck_id AND d.user_id = {_UID})"
    )
] * 4

SPECIAL_SPECS: list[TableSpec] = [
    # flashcards are owned through their deck
    TableSpec("flashcards", "owner",
              *_DECK_OWNED),
    # referrals visible to either party, written by service paths only
    TableSpec("referrals", "owner",
              _owned(f"(referrals.referrer_id = {_UID} OR referrals.referee_id = {_UID})")),
    TableSpec("conversations", "owner",
              _owned(_MEMBER), _owned(f"conversations.created_by_id = {_UID}"),
              _owned(_MEMBER), _owned(f"conversations.created_by_id = {_UID}")),
    TableSpec("conversation_members", "owner",
              _owned(_CM_MEMBER),
              # INSERT: only service path (no user context) or existing
              # conversation members can add new members. Prevents any
              # user from adding themselves to arbitrary conversations.
              f"({_CM_MEMBER} OR {_NOCTX})",
              _owned(_CM_MEMBER),
              _owned(f"conversation_members.user_id = {_UID}")),
    # membership rows may be inserted by the app during conversation
    # creation; edits are member-scoped, deletes owner-of-row only.
    TableSpec("messages", "owner",
              _owned(_MSG_MEMBER), _owned(f"messages.sender_id = {_UID}"),
              _owned(f"messages.sender_id = {_UID}"), _owned(f"messages.sender_id = {_UID}")),
    TableSpec("message_read_receipts", "owner",
              _owned(_MRR_MEMBER), _owned(f"message_read_receipts.user_id = {_UID}"),
              delete=_owned(f"message_read_receipts.user_id = {_UID}")),
    # public profiles are world-readable but self-write only
    TableSpec("user_profiles", "owner",
              "true",
              _owned(f"user_profiles.user_id = {_UID}"),
              _owned(f"user_profiles.user_id = {_UID}"),
              _owned(f"user_profiles.user_id = {_UID}")),
]

TABLE_SPECS: list[TableSpec] = (
    [TableSpec(t, "reference") for t in _REFERENCE]
    + [TableSpec(t, "service") for t in _SERVICE]
    + [_owner(t, c) for t, c in _OWNER_COLUMNS.items()]
    + SPECIAL_SPECS
)

SPEC_BY_TABLE: dict[str, TableSpec] = {s.table: s for s in TABLE_SPECS}

# Tables that exist outside SQLAlchemy metadata (raw SQL migrations).
EXTRA_BASELINE_TABLES = {"material_chunks", "academic_agent_tasks", "uploaded_files"}

# Minimal grant surface used by the audit probe role.
PROBE_TABLES = [
    "user_privacy", "vault_items", "notifications",
    "points_transactions", "subscriptions", "flashcard_decks",
]
PROBE_ROLE = "vylix_rls_probe"
PROBE_PASSWORD = "rls_probe_pw"


def drop_policies_statement(table: str) -> str:
    return (
        f"DO $$ DECLARE p text; BEGIN "
        f"FOR p IN SELECT polname FROM pg_policy WHERE polrelid = to_regclass('{table}') LOOP "
        f"EXECUTE format('DROP POLICY %I ON {table}', p); END LOOP; END $$;"
    )


def baseline_statements() -> list[str]:
    """Idempotent DDL bringing every table to the intended RLS state."""
    stmts: list[str] = []
    for spec in TABLE_SPECS:
        stmts.append(f"ALTER TABLE {spec.table} ENABLE ROW LEVEL SECURITY")
        stmts.append(f"ALTER TABLE {spec.table} FORCE ROW LEVEL SECURITY")
        stmts.append(drop_policies_statement(spec.table))
        for cmd in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            using = getattr(spec, cmd.lower())
            # Postgres grammar: SELECT/DELETE are USING-only; INSERT is
            # WITH CHECK-only; UPDATE takes both.
            if cmd == "INSERT":
                clause = f"WITH CHECK ({using})"
            elif cmd == "UPDATE":
                clause = f"USING ({using}) WITH CHECK ({using})"
            else:
                clause = f"USING ({using})"
            stmts.append(
                f"CREATE POLICY {spec.table}_rls_{cmd.lower()} ON {spec.table} FOR {cmd} {clause}"
            )
    return stmts


def downgrade_statements() -> list[str]:
    stmts: list[str] = []
    for spec in reversed(TABLE_SPECS):
        stmts.append(drop_policies_statement(spec.table))
        stmts.append(f"ALTER TABLE {spec.table} NO FORCE ROW LEVEL SECURITY")
        stmts.append(f"ALTER TABLE {spec.table} DISABLE ROW LEVEL SECURITY")
    return stmts
