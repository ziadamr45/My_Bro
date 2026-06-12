"""
Database Migration System
=========================
Replaces scattered CREATE TABLE IF NOT EXISTS with versioned migrations.

Features:
- Tracks applied migrations in a _migrations table
- Runs pending migrations in order on startup
- Supports both PostgreSQL and SQLite
- Idempotent — safe to run multiple times
- Backward compatible — existing tables are not affected
"""

import logging
import os
import re
import time
import importlib
from typing import List, Optional

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


class MigrationRunner:
    def __init__(self):
        self._applied = None  # Cache of applied migration IDs

    # ──────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────

    @staticmethod
    def _get_execute():
        """Lazily import _execute from memory module."""
        from memory import _execute
        return _execute

    @staticmethod
    def _get_is_postgres():
        """Lazily import _is_postgres from memory module."""
        from memory import _is_postgres
        return _is_postgres

    def _ensure_migrations_table(self):
        """Create the _migrations tracking table if it doesn't exist.

        Uses different DDL for PostgreSQL vs SQLite.
        """
        _execute = self._get_execute()
        _is_postgres = self._get_is_postgres()

        if _is_postgres():
            _execute("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    id TEXT PRIMARY KEY,
                    applied_at TEXT DEFAULT (NOW() AT TIME ZONE 'UTC'::text),
                    execution_time_ms INTEGER DEFAULT 0
                );
            """)
        else:
            _execute("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    id TEXT PRIMARY KEY,
                    applied_at TEXT DEFAULT (datetime('now')),
                    execution_time_ms INTEGER DEFAULT 0
                );
            """)

    def _get_applied_migrations(self) -> set:
        """Get set of applied migration IDs from _migrations table."""
        if self._applied is not None:
            return self._applied

        _execute = self._get_execute()

        try:
            self._ensure_migrations_table()
            rows = _execute("SELECT id FROM _migrations", fetch=True)
            if rows:
                self._applied = {row[0] for row in rows}
            else:
                self._applied = set()
        except Exception as e:
            logger.warning(f"Could not read applied migrations: {e}")
            self._applied = set()

        return self._applied

    def _get_pending_migrations(self) -> List[str]:
        """Get sorted list of migration IDs that haven't been applied yet.

        Scans the migrations/ directory for .py files, sorts them by name,
        and filters out already-applied ones.
        """
        applied = self._get_applied_migrations()
        pending = []

        if not os.path.isdir(MIGRATIONS_DIR):
            logger.warning(f"Migrations directory not found: {MIGRATIONS_DIR}")
            return pending

        for filename in sorted(os.listdir(MIGRATIONS_DIR)):
            if filename.startswith("_") or not filename.endswith(".py"):
                continue
            # Skip __init__.py and other non-migration files
            if filename == "__init__.py":
                continue
            migration_id = filename[:-3]  # Strip .py extension
            if migration_id not in applied:
                pending.append(migration_id)

        return pending

    def _split_sql_statements(self, sql: str) -> List[str]:
        """Split a multi-statement SQL string into individual statements.

        Handles:
        - Semicolons inside string literals (doesn't split on them)
        - Empty statements and SQL comments (-- style)
        """
        statements = []
        current = []
        in_string = False
        string_char = None

        for char in sql:
            if in_string:
                current.append(char)
                if char == string_char:
                    in_string = False
            elif char in ("'", '"'):
                in_string = True
                string_char = char
                current.append(char)
            elif char == ';':
                stmt = self._clean_statement(''.join(current))
                if stmt:
                    statements.append(stmt)
                current = []
            else:
                current.append(char)

        # Handle last statement without trailing semicolon
        stmt = self._clean_statement(''.join(current))
        if stmt:
            statements.append(stmt)

        return statements

    @staticmethod
    def _clean_statement(stmt: str) -> str:
        """Remove comment-only lines from a SQL statement and return it
        stripped. Returns empty string if the statement is empty after
        removing comments."""
        lines = []
        for line in stmt.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith('--'):
                lines.append(line)
        result = '\n'.join(lines).strip()
        return result

    def _is_alter_add_column(self, stmt: str) -> bool:
        """Check if a SQL statement is an ALTER TABLE ADD COLUMN.

        These statements may fail on SQLite if the column already exists,
        which is expected and should be silently ignored.
        """
        return bool(re.match(
            r'ALTER\s+TABLE\s+\S+\s+ADD\s+COLUMN\s+',
            stmt.strip(),
            re.IGNORECASE
        ))

    def _run_migration(self, migration_id: str):
        """Run a single migration file.

        Imports the migration module, selects the appropriate SQL (PG or SQLite),
        splits into individual statements, and executes each one.

        For SQLite, ALTER TABLE ADD COLUMN errors are silently ignored
        (the column may already exist from the old inline migration code).
        """
        _execute = self._get_execute()
        _is_postgres = self._get_is_postgres()

        start_time = time.time()

        # Import the migration module
        module_name = f"migrations.{migration_id}"
        try:
            mod = importlib.import_module(module_name)
        except ImportError as e:
            logger.error(f"Failed to import migration {migration_id}: {e}")
            raise

        # Validate migration module
        if not hasattr(mod, 'MIGRATION_ID'):
            raise ValueError(f"Migration {migration_id} missing MIGRATION_ID")
        if mod.MIGRATION_ID != migration_id:
            raise ValueError(
                f"Migration file {migration_id}.py has MIGRATION_ID={mod.MIGRATION_ID!r}, "
                f"expected {migration_id!r}"
            )

        # Select SQL based on database type
        if _is_postgres():
            sql = getattr(mod, 'UP_PG', None)
            db_type_label = "PostgreSQL"
        else:
            sql = getattr(mod, 'UP_SQLITE', None)
            db_type_label = "SQLite"

        if not sql:
            raise ValueError(
                f"Migration {migration_id} missing SQL for {db_type_label}"
            )

        # Execute each statement individually for better error handling
        statements = self._split_sql_statements(sql)
        errors_ignored = 0

        for stmt in statements:
            try:
                _execute(stmt)
            except Exception as e:
                # For SQLite, ALTER TABLE ADD COLUMN may fail if column exists
                if not _is_postgres() and self._is_alter_add_column(stmt):
                    logger.debug(
                        f"SQLite ALTER TABLE ADD COLUMN ignored (column likely exists): {e}"
                    )
                    errors_ignored += 1
                else:
                    logger.error(f"Migration {migration_id} failed on statement: {stmt[:100]}...")
                    raise

        # Record successful migration
        elapsed_ms = int((time.time() - start_time) * 1000)
        self._record_migration(migration_id, elapsed_ms)

        if errors_ignored:
            logger.info(
                f"✅ Migration {migration_id} applied ({elapsed_ms}ms, "
                f"{errors_ignored} SQLite ALTER errors ignored) [{db_type_label}]"
            )
        else:
            logger.info(
                f"✅ Migration {migration_id} applied ({elapsed_ms}ms) [{db_type_label}]"
            )

    def _record_migration(self, migration_id: str, elapsed_ms: int):
        """Record a successfully applied migration in the _migrations table."""
        _execute = self._get_execute()
        _is_postgres = self._get_is_postgres()

        ph = "%s" if _is_postgres() else "?"
        _execute(
            f"INSERT INTO _migrations (id, execution_time_ms) VALUES ({ph}, {ph})",
            (migration_id, elapsed_ms)
        )

        # Update cache
        if self._applied is not None:
            self._applied.add(migration_id)

    # ──────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────

    def run_pending(self):
        """Run all pending migrations in order.

        Safe to call multiple times — only unapplied migrations will run.
        """
        pending = self._get_pending_migrations()

        if not pending:
            logger.info("No pending migrations")
            return

        logger.info(f"Running {len(pending)} pending migration(s): {pending}")
        self._ensure_migrations_table()

        for migration_id in pending:
            try:
                self._run_migration(migration_id)
            except Exception as e:
                logger.error(f"❌ Migration {migration_id} FAILED: {e}")
                # Stop running further migrations on failure
                raise

        logger.info(f"All {len(pending)} migration(s) applied successfully")

    def get_status(self) -> dict:
        """Get migration status for monitoring/debugging.

        Returns:
            dict with keys:
                applied: list of applied migration IDs
                pending: list of pending migration IDs
                total: total number of migration files found
        """
        applied = self._get_applied_migrations()

        # Get all migration files
        all_migrations = []
        if os.path.isdir(MIGRATIONS_DIR):
            for filename in sorted(os.listdir(MIGRATIONS_DIR)):
                if filename.startswith("_") or not filename.endswith(".py"):
                    continue
                if filename == "__init__.py":
                    continue
                all_migrations.append(filename[:-3])

        pending = [m for m in all_migrations if m not in applied]

        return {
            "applied": sorted(applied),
            "pending": pending,
            "total": len(all_migrations),
        }

    def reset_cache(self):
        """Reset the internal cache of applied migrations.

        Useful for testing or after manual database changes.
        """
        self._applied = None


# Singleton instance
migration_runner = MigrationRunner()


def run_migrations():
    """Convenience function to run all pending migrations"""
    migration_runner.run_pending()
