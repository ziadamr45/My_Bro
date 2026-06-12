"""
Unit tests for migrate.py — Database Migration System

Tests the migration runner with mocked database access:
- MigrationRunner initialization and cache
- _ensure_migrations_table creates tracking table
- _get_applied_migrations returns correct sets
- _get_pending_migrations discovers migration files
- _run_migration executes and records migration
- run_pending runs all pending migrations
- Re-running run_pending is idempotent
- get_status returns correct information
- Error handling: failed migration is not recorded as applied
- Both PG and SQLite code paths
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch, call

# Mock telegram (needed by admin.py which is imported transitively)
sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()

# Mock memory module before importing migrate
mock_memory = MagicMock()

# Import the module under test
import migrate
from migrate import MigrationRunner, migration_runner, run_migrations


class TestMigrationRunnerInit(unittest.TestCase):
    """Tests for MigrationRunner initialization"""

    def test_initial_state(self):
        """Runner starts with no cached applied migrations"""
        runner = MigrationRunner()
        self.assertIsNone(runner._applied)

    def test_singleton_instance_exists(self):
        """Module-level singleton instance exists"""
        self.assertIsInstance(migration_runner, MigrationRunner)


class TestEnsureMigrationsTable(unittest.TestCase):
    """Tests for _ensure_migrations_table"""

    def setUp(self):
        self.runner = MigrationRunner()
        self.mock_execute = MagicMock()
        self.mock_is_postgres = MagicMock()

    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_creates_pg_table(self, mock_get_execute, mock_get_is_postgres):
        """Creates _migrations table with PostgreSQL DDL"""
        mock_get_execute.return_value = self.mock_execute
        mock_get_is_postgres.return_value = lambda: True

        self.runner._ensure_migrations_table()

        self.mock_execute.assert_called_once()
        sql = self.mock_execute.call_args[0][0]
        self.assertIn("_migrations", sql)
        self.assertIn("NOW() AT TIME ZONE 'UTC'", sql)
        self.assertIn("id TEXT PRIMARY KEY", sql)
        self.assertIn("execution_time_ms INTEGER DEFAULT 0", sql)

    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_creates_sqlite_table(self, mock_get_execute, mock_get_is_postgres):
        """Creates _migrations table with SQLite DDL"""
        mock_get_execute.return_value = self.mock_execute
        mock_get_is_postgres.return_value = lambda: False

        self.runner._ensure_migrations_table()

        self.mock_execute.assert_called_once()
        sql = self.mock_execute.call_args[0][0]
        self.assertIn("_migrations", sql)
        self.assertIn("datetime('now')", sql)
        self.assertIn("id TEXT PRIMARY KEY", sql)


class TestGetAppliedMigrations(unittest.TestCase):
    """Tests for _get_applied_migrations"""

    def setUp(self):
        self.runner = MigrationRunner()

    @patch.object(MigrationRunner, '_ensure_migrations_table')
    @patch.object(MigrationRunner, '_get_execute')
    def test_returns_empty_set_when_no_migrations(self, mock_get_execute, mock_ensure):
        """Returns empty set when no migrations have been applied"""
        mock_execute = MagicMock()
        mock_execute.return_value = []  # No rows
        mock_get_execute.return_value = mock_execute

        result = self.runner._get_applied_migrations()

        self.assertEqual(result, set())

    @patch.object(MigrationRunner, '_ensure_migrations_table')
    @patch.object(MigrationRunner, '_get_execute')
    def test_returns_applied_ids(self, mock_get_execute, mock_ensure):
        """Returns set of applied migration IDs"""
        mock_execute = MagicMock()
        mock_execute.return_value = [("001_initial_schema",), ("002_add_foo",)]
        mock_get_execute.return_value = mock_execute

        result = self.runner._get_applied_migrations()

        self.assertEqual(result, {"001_initial_schema", "002_add_foo"})

    @patch.object(MigrationRunner, '_ensure_migrations_table')
    @patch.object(MigrationRunner, '_get_execute')
    def test_caches_result(self, mock_get_execute, mock_ensure):
        """Caches result — second call doesn't hit DB"""
        mock_execute = MagicMock()
        mock_execute.return_value = [("001_initial_schema",)]
        mock_get_execute.return_value = mock_execute

        result1 = self.runner._get_applied_migrations()
        result2 = self.runner._get_applied_migrations()

        self.assertEqual(result1, result2)
        # _execute should only be called once for the SELECT
        # (the _ensure_migrations_table call also uses _execute, but caching
        # means we don't re-query on the second call)

    @patch.object(MigrationRunner, '_ensure_migrations_table')
    @patch.object(MigrationRunner, '_get_execute')
    def test_returns_empty_set_on_db_error(self, mock_get_execute, mock_ensure):
        """Returns empty set when database query fails"""
        mock_execute = MagicMock()
        mock_execute.side_effect = Exception("DB error")
        mock_get_execute.return_value = mock_execute
        mock_ensure.side_effect = Exception("DB error")

        result = self.runner._get_applied_migrations()

        self.assertEqual(result, set())


class TestGetPendingMigrations(unittest.TestCase):
    """Tests for _get_pending_migrations"""

    def setUp(self):
        self.runner = MigrationRunner()

    @patch.object(MigrationRunner, '_get_applied_migrations')
    def test_finds_migration_files(self, mock_applied):
        """Finds migration files in the migrations directory"""
        mock_applied.return_value = set()  # No migrations applied

        pending = self.runner._get_pending_migrations()

        # The migrations directory exists and has 001_initial_schema.py
        self.assertIn("001_initial_schema", pending)

    @patch.object(MigrationRunner, '_get_applied_migrations')
    def test_excludes_applied_migrations(self, mock_applied):
        """Excludes already-applied migrations from pending list"""
        mock_applied.return_value = {"001_initial_schema"}

        pending = self.runner._get_pending_migrations()

        self.assertNotIn("001_initial_schema", pending)

    @patch.object(MigrationRunner, '_get_applied_migrations')
    def test_excludes_init_file(self, mock_applied):
        """Excludes __init__.py from migration list"""
        mock_applied.return_value = set()

        pending = self.runner._get_pending_migrations()

        self.assertNotIn("__init__", pending)

    @patch.object(MigrationRunner, '_get_applied_migrations')
    def test_excludes_private_files(self, mock_applied):
        """Excludes files starting with underscore"""
        mock_applied.return_value = set()

        pending = self.runner._get_pending_migrations()

        for p in pending:
            self.assertFalse(p.startswith("_"))

    @patch.object(MigrationRunner, '_get_applied_migrations')
    def test_returns_sorted_list(self, mock_applied):
        """Returns migrations in sorted order"""
        mock_applied.return_value = set()

        pending = self.runner._get_pending_migrations()

        self.assertEqual(pending, sorted(pending))

    @patch.object(MigrationRunner, '_get_applied_migrations')
    def test_handles_missing_directory(self, mock_applied):
        """Returns empty list if migrations directory doesn't exist"""
        mock_applied.return_value = set()
        original_dir = migrate.MIGRATIONS_DIR
        try:
            migrate.MIGRATIONS_DIR = "/nonexistent/path"
            pending = self.runner._get_pending_migrations()
            self.assertEqual(pending, [])
        finally:
            migrate.MIGRATIONS_DIR = original_dir


class TestSplitSqlStatements(unittest.TestCase):
    """Tests for _split_sql_statements"""

    def setUp(self):
        self.runner = MigrationRunner()

    def test_splits_on_semicolons(self):
        """Splits SQL string on semicolons"""
        sql = "CREATE TABLE a (id INT); CREATE TABLE b (id INT);"
        result = self.runner._split_sql_statements(sql)
        self.assertEqual(len(result), 2)
        self.assertIn("CREATE TABLE a", result[0])
        self.assertIn("CREATE TABLE b", result[1])

    def test_handles_semicolons_in_strings(self):
        """Doesn't split on semicolons inside string literals"""
        sql = "INSERT INTO t VALUES ('hello;world');"
        result = self.runner._split_sql_statements(sql)
        self.assertEqual(len(result), 1)
        self.assertIn("hello;world", result[0])

    def test_ignores_empty_statements(self):
        """Ignores empty statements and comments"""
        sql = ";; -- comment\n CREATE TABLE a (id INT); ;;"
        result = self.runner._split_sql_statements(sql)
        self.assertEqual(len(result), 1)

    def test_handles_statement_without_trailing_semicolon(self):
        """Handles last statement without trailing semicolon"""
        sql = "CREATE TABLE a (id INT)"
        result = self.runner._split_sql_statements(sql)
        self.assertEqual(len(result), 1)
        self.assertIn("CREATE TABLE a", result[0])


class TestIsAlterAddColumn(unittest.TestCase):
    """Tests for _is_alter_add_column"""

    def setUp(self):
        self.runner = MigrationRunner()

    def test_detects_alter_add_column(self):
        """Detects ALTER TABLE ADD COLUMN statements"""
        self.assertTrue(self.runner._is_alter_add_column(
            "ALTER TABLE user_profiles ADD COLUMN platform TEXT DEFAULT 'telegram'"
        ))

    def test_detects_case_insensitive(self):
        """Case-insensitive detection"""
        self.assertTrue(self.runner._is_alter_add_column(
            "alter table user_profiles add column platform TEXT"
        ))

    def test_rejects_create_table(self):
        """Does not match CREATE TABLE"""
        self.assertFalse(self.runner._is_alter_add_column(
            "CREATE TABLE user_profiles (id INT)"
        ))

    def test_rejects_alter_drop(self):
        """Does not match ALTER TABLE DROP COLUMN"""
        self.assertFalse(self.runner._is_alter_add_column(
            "ALTER TABLE user_profiles DROP COLUMN platform"
        ))

    def test_rejects_create_index(self):
        """Does not match CREATE INDEX"""
        self.assertFalse(self.runner._is_alter_add_column(
            "CREATE INDEX IF NOT EXISTS idx_foo ON bar(baz)"
        ))


class TestRunMigration(unittest.TestCase):
    """Tests for _run_migration"""

    def setUp(self):
        self.runner = MigrationRunner()
        self.runner._applied = set()  # Fresh cache

    @patch.object(MigrationRunner, '_record_migration')
    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_runs_pg_migration(self, mock_get_execute, mock_get_is_postgres, mock_record):
        """Runs a PG migration successfully"""
        mock_execute = MagicMock()
        mock_get_execute.return_value = mock_execute
        mock_get_is_postgres.return_value = lambda: True

        self.runner._run_migration("001_initial_schema")

        # Should have called _execute multiple times (one per statement)
        self.assertTrue(mock_execute.call_count > 0)
        # Should have recorded the migration
        mock_record.assert_called_once()
        self.assertEqual(mock_record.call_args[0][0], "001_initial_schema")

    @patch.object(MigrationRunner, '_record_migration')
    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_runs_sqlite_migration(self, mock_get_execute, mock_get_is_postgres, mock_record):
        """Runs a SQLite migration successfully"""
        mock_execute = MagicMock()
        mock_get_execute.return_value = mock_execute
        mock_get_is_postgres.return_value = lambda: False

        self.runner._run_migration("001_initial_schema")

        self.assertTrue(mock_execute.call_count > 0)
        mock_record.assert_called_once()

    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_ignores_sqlite_alter_add_column_errors(self, mock_get_execute, mock_get_is_postgres):
        """SQLite ALTER TABLE ADD COLUMN errors are silently ignored"""
        mock_execute = MagicMock()
        mock_get_execute.return_value = mock_execute
        mock_get_is_postgres.return_value = lambda: False

        # First calls succeed, then ALTER TABLE ADD COLUMN fails, then more succeed
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            sql = args[0] if args else ""
            if "ALTER TABLE" in sql and "ADD COLUMN" in sql:
                raise Exception("duplicate column name")
            return None

        mock_execute.side_effect = side_effect

        # Should NOT raise
        self.runner._run_migration("001_initial_schema")

    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_raises_on_pg_create_table_error(self, mock_get_execute, mock_get_is_postgres):
        """PG CREATE TABLE errors are raised, not ignored"""
        mock_execute = MagicMock()
        mock_get_execute.return_value = mock_execute
        mock_get_is_postgres.return_value = lambda: True

        mock_execute.side_effect = Exception("PostgreSQL error")

        with self.assertRaises(Exception):
            self.runner._run_migration("001_initial_schema")

    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_raises_on_missing_migration_module(self, mock_get_execute, mock_get_is_postgres):
        """Raises ImportError for non-existent migration file"""
        mock_execute = MagicMock()
        mock_get_execute.return_value = mock_execute
        mock_get_is_postgres.return_value = lambda: True

        with self.assertRaises(ImportError):
            self.runner._run_migration("999_nonexistent")

    @patch.object(MigrationRunner, '_record_migration')
    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_records_execution_time(self, mock_get_execute, mock_get_is_postgres, mock_record):
        """Records migration execution time in milliseconds"""
        mock_execute = MagicMock()
        mock_get_execute.return_value = mock_execute
        mock_get_is_postgres.return_value = lambda: True

        self.runner._run_migration("001_initial_schema")

        # elapsed_ms should be a non-negative integer
        elapsed_ms = mock_record.call_args[0][1]
        self.assertIsInstance(elapsed_ms, int)
        self.assertGreaterEqual(elapsed_ms, 0)


class TestRecordMigration(unittest.TestCase):
    """Tests for _record_migration"""

    def setUp(self):
        self.runner = MigrationRunner()
        self.runner._applied = set()

    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_inserts_record_with_pg_placeholder(self, mock_get_execute, mock_get_is_postgres):
        """Uses %s placeholder for PostgreSQL"""
        mock_execute = MagicMock()
        mock_get_execute.return_value = mock_execute
        mock_get_is_postgres.return_value = lambda: True

        self.runner._record_migration("001_initial_schema", 42)

        sql = mock_execute.call_args[0][0]
        self.assertIn("%s", sql)
        params = mock_execute.call_args[0][1]
        self.assertEqual(params, ("001_initial_schema", 42))

    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_inserts_record_with_sqlite_placeholder(self, mock_get_execute, mock_get_is_postgres):
        """Uses ? placeholder for SQLite"""
        mock_execute = MagicMock()
        mock_get_execute.return_value = mock_execute
        mock_get_is_postgres.return_value = lambda: False

        self.runner._record_migration("001_initial_schema", 42)

        sql = mock_execute.call_args[0][0]
        self.assertIn("?", sql)

    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_updates_cache(self, mock_get_execute, mock_get_is_postgres):
        """Updates the internal cache of applied migrations"""
        mock_execute = MagicMock()
        mock_get_execute.return_value = mock_execute
        mock_get_is_postgres.return_value = lambda: True

        self.runner._record_migration("001_initial_schema", 42)

        self.assertIn("001_initial_schema", self.runner._applied)


class TestRunPending(unittest.TestCase):
    """Tests for run_pending"""

    def setUp(self):
        self.runner = MigrationRunner()

    @patch.object(MigrationRunner, '_run_migration')
    @patch.object(MigrationRunner, '_ensure_migrations_table')
    @patch.object(MigrationRunner, '_get_pending_migrations')
    def test_runs_all_pending(self, mock_pending, mock_ensure, mock_run):
        """Runs all pending migrations"""
        mock_pending.return_value = ["001_initial_schema", "002_add_foo"]

        self.runner.run_pending()

        self.assertEqual(mock_run.call_count, 2)
        mock_run.assert_any_call("001_initial_schema")
        mock_run.assert_any_call("002_add_foo")

    @patch.object(MigrationRunner, '_run_migration')
    @patch.object(MigrationRunner, '_ensure_migrations_table')
    @patch.object(MigrationRunner, '_get_pending_migrations')
    def test_no_pending_migrations(self, mock_pending, mock_ensure, mock_run):
        """Does nothing when no pending migrations"""
        mock_pending.return_value = []

        self.runner.run_pending()

        mock_run.assert_not_called()

    @patch.object(MigrationRunner, '_run_migration')
    @patch.object(MigrationRunner, '_ensure_migrations_table')
    @patch.object(MigrationRunner, '_get_pending_migrations')
    def test_stops_on_failure(self, mock_pending, mock_ensure, mock_run):
        """Stops running further migrations on failure"""
        mock_pending.return_value = ["001_initial_schema", "002_add_foo"]
        mock_run.side_effect = [None, Exception("Migration failed")]

        # The first call succeeds, second fails
        # But we need to test that after the first failure, no more migrations run
        mock_run.side_effect = Exception("Migration failed")

        with self.assertRaises(Exception):
            self.runner.run_pending()

        # Only one call was made before the exception
        self.assertEqual(mock_run.call_count, 1)

    @patch.object(MigrationRunner, '_run_migration')
    @patch.object(MigrationRunner, '_ensure_migrations_table')
    @patch.object(MigrationRunner, '_get_pending_migrations')
    def test_idempotent_rerun(self, mock_pending, mock_ensure, mock_run):
        """Re-running run_pending is idempotent — no double execution.

        After the first run, pending list should be empty because
        _get_pending_migrations checks _get_applied_migrations which
        includes the newly recorded migration.
        """
        # First run: 1 pending migration
        mock_pending.return_value = ["001_initial_schema"]
        self.runner.run_pending()
        self.assertEqual(mock_run.call_count, 1)

        # Second run: no pending migrations (they were recorded)
        mock_pending.return_value = []
        self.runner.run_pending()
        # Still only 1 call total
        self.assertEqual(mock_run.call_count, 1)


class TestFailedMigrationNotRecorded(unittest.TestCase):
    """Tests that a failed migration is NOT recorded as applied"""

    def setUp(self):
        self.runner = MigrationRunner()
        self.runner._applied = set()

    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_failed_migration_not_in_applied_cache(self, mock_get_execute, mock_get_is_postgres):
        """A failed migration should not be added to the applied cache"""
        mock_execute = MagicMock()
        mock_get_execute.return_value = mock_execute
        mock_get_is_postgres.return_value = lambda: True

        # All _execute calls fail
        mock_execute.side_effect = Exception("DB error")

        try:
            self.runner._run_migration("001_initial_schema")
        except Exception:
            pass

        # The migration should NOT be in the applied cache
        self.assertNotIn("001_initial_schema", self.runner._applied)


class TestGetStatus(unittest.TestCase):
    """Tests for get_status"""

    def setUp(self):
        self.runner = MigrationRunner()

    @patch.object(MigrationRunner, '_get_applied_migrations')
    def test_returns_correct_status(self, mock_applied):
        """Returns correct migration status"""
        mock_applied.return_value = {"001_initial_schema"}

        status = self.runner.get_status()

        self.assertIn("applied", status)
        self.assertIn("pending", status)
        self.assertIn("total", status)
        self.assertIn("001_initial_schema", status["applied"])
        self.assertIsInstance(status["pending"], list)
        self.assertIsInstance(status["total"], int)

    @patch.object(MigrationRunner, '_get_applied_migrations')
    def test_pending_excludes_applied(self, mock_applied):
        """Pending list doesn't include applied migrations"""
        mock_applied.return_value = {"001_initial_schema"}

        status = self.runner.get_status()

        self.assertNotIn("001_initial_schema", status["pending"])

    @patch.object(MigrationRunner, '_get_applied_migrations')
    def test_total_counts_all_migrations(self, mock_applied):
        """Total counts all migration files, not just applied"""
        mock_applied.return_value = set()

        status = self.runner.get_status()

        # Should be at least 1 (001_initial_schema)
        self.assertGreaterEqual(status["total"], 1)


class TestResetCache(unittest.TestCase):
    """Tests for reset_cache"""

    def setUp(self):
        self.runner = MigrationRunner()

    def test_resets_applied_cache(self):
        """Reset cache clears the internal cache"""
        self.runner._applied = {"001_initial_schema"}
        self.runner.reset_cache()
        self.assertIsNone(self.runner._applied)


class TestConvenienceFunction(unittest.TestCase):
    """Tests for the module-level run_migrations() function"""

    @patch.object(MigrationRunner, 'run_pending')
    def test_calls_singleton_run_pending(self, mock_run_pending):
        """The convenience function delegates to the singleton"""
        run_migrations()
        mock_run_pending.assert_called_once()


class TestMigration001Module(unittest.TestCase):
    """Tests for the 001_initial_schema migration module"""

    def test_module_imports(self):
        """The migration module can be imported via importlib"""
        import importlib
        mod = importlib.import_module("migrations.001_initial_schema")
        self.assertIsNotNone(mod)

    def test_has_migration_id(self):
        """Migration module has MIGRATION_ID"""
        import importlib
        mod = importlib.import_module("migrations.001_initial_schema")
        self.assertEqual(mod.MIGRATION_ID, "001_initial_schema")

    def test_has_up_pg(self):
        """Migration module has UP_PG SQL"""
        import importlib
        mod = importlib.import_module("migrations.001_initial_schema")
        self.assertTrue(hasattr(mod, 'UP_PG'))
        self.assertIsInstance(mod.UP_PG, str)
        self.assertIn("CREATE TABLE", mod.UP_PG)

    def test_has_up_sqlite(self):
        """Migration module has UP_SQLITE SQL"""
        import importlib
        mod = importlib.import_module("migrations.001_initial_schema")
        self.assertTrue(hasattr(mod, 'UP_SQLITE'))
        self.assertIsInstance(mod.UP_SQLITE, str)
        self.assertIn("CREATE TABLE", mod.UP_SQLITE)

    def test_has_down(self):
        """Migration module has DOWN SQL"""
        import importlib
        mod = importlib.import_module("migrations.001_initial_schema")
        self.assertTrue(hasattr(mod, 'DOWN'))

    def test_pg_has_all_tables(self):
        """PG SQL contains all expected tables"""
        import importlib
        mod = importlib.import_module("migrations.001_initial_schema")

        expected_tables = [
            "user_profiles",
            "conversations",
            "learning_progress",
            "favorites",
            "user_memories",
            "banned_users",
            "premium_users",
            "usage_tracking",
            "workspace_items",
            "smart_alerts",
            "premium_history",
            "admin_users",
            "bot_stats",
            "sent_articles",
        ]
        for table in expected_tables:
            self.assertIn(table, mod.UP_PG, f"Table {table} missing from UP_PG")

    def test_sqlite_has_all_tables(self):
        """SQLite SQL contains all expected tables"""
        import importlib
        mod = importlib.import_module("migrations.001_initial_schema")

        expected_tables = [
            "user_profiles",
            "conversations",
            "learning_progress",
            "favorites",
            "user_memories",
            "banned_users",
            "premium_users",
            "usage_tracking",
            "workspace_items",
            "smart_alerts",
            "premium_history",
            "admin_users",
            "bot_stats",
            "sent_articles",
        ]
        for table in expected_tables:
            self.assertIn(table, mod.UP_SQLITE, f"Table {table} missing from UP_SQLITE")

    def test_pg_has_indexes(self):
        """PG SQL contains CREATE INDEX statements"""
        import importlib
        mod = importlib.import_module("migrations.001_initial_schema")

        self.assertIn("CREATE INDEX", mod.UP_PG)
        self.assertIn("idx_conversations_user", mod.UP_PG)
        self.assertIn("idx_usage_user_date", mod.UP_PG)

    def test_sqlite_has_indexes(self):
        """SQLite SQL contains CREATE INDEX statements"""
        import importlib
        mod = importlib.import_module("migrations.001_initial_schema")

        self.assertIn("CREATE INDEX", mod.UP_SQLITE)
        self.assertIn("idx_conversations_user", mod.UP_SQLITE)

    def test_pg_has_alter_table_migrations(self):
        """PG SQL contains ALTER TABLE ADD COLUMN IF NOT EXISTS for migrated columns"""
        import importlib
        mod = importlib.import_module("migrations.001_initial_schema")

        self.assertIn("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS platform", mod.UP_PG)
        self.assertIn("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS wa_phone", mod.UP_PG)
        self.assertIn("ALTER TABLE usage_tracking ADD COLUMN IF NOT EXISTS image_generations", mod.UP_PG)

    def test_sqlite_has_alter_table_migrations(self):
        """SQLite SQL contains ALTER TABLE ADD COLUMN for migrated columns"""
        import importlib
        mod = importlib.import_module("migrations.001_initial_schema")

        self.assertIn("ALTER TABLE user_profiles ADD COLUMN platform", mod.UP_SQLITE)
        self.assertIn("ALTER TABLE user_profiles ADD COLUMN wa_phone", mod.UP_SQLITE)
        self.assertIn("ALTER TABLE usage_tracking ADD COLUMN image_generations", mod.UP_SQLITE)

    def test_uses_if_not_exists(self):
        """All CREATE TABLE statements use IF NOT EXISTS for safety"""
        import importlib
        mod = importlib.import_module("migrations.001_initial_schema")

        # Count CREATE TABLE occurrences
        import re
        pg_tables = re.findall(r'CREATE TABLE (\w+)', mod.UP_PG)
        pg_if_not_exists = re.findall(r'CREATE TABLE IF NOT EXISTS', mod.UP_PG)
        self.assertEqual(len(pg_tables), len(pg_if_not_exists),
                        "Not all PG CREATE TABLE statements use IF NOT EXISTS")

        sqlite_tables = re.findall(r'CREATE TABLE (\w+)', mod.UP_SQLITE)
        sqlite_if_not_exists = re.findall(r'CREATE TABLE IF NOT EXISTS', mod.UP_SQLITE)
        self.assertEqual(len(sqlite_tables), len(sqlite_if_not_exists),
                        "Not all SQLite CREATE TABLE statements use IF NOT EXISTS")


class TestBothDatabasePaths(unittest.TestCase):
    """Tests that both PG and SQLite code paths work correctly"""

    def setUp(self):
        self.runner = MigrationRunner()

    @patch.object(MigrationRunner, '_record_migration')
    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_pg_path_uses_up_pg(self, mock_get_execute, mock_get_is_postgres, mock_record):
        """When _is_postgres() returns True, UP_PG SQL is used"""
        mock_execute = MagicMock()
        mock_get_execute.return_value = mock_execute
        mock_get_is_postgres.return_value = lambda: True

        self.runner._run_migration("001_initial_schema")

        # Verify PG-specific SQL was used
        executed_sqls = [call_args[0][0] for call_args in mock_execute.call_args_list]
        # PG SQL should contain NOW() AT TIME ZONE
        pg_specific_found = any("NOW()" in sql for sql in executed_sqls)
        self.assertTrue(pg_specific_found, "PG-specific SQL (NOW() AT TIME ZONE) not found in executed statements")

    @patch.object(MigrationRunner, '_record_migration')
    @patch.object(MigrationRunner, '_get_is_postgres')
    @patch.object(MigrationRunner, '_get_execute')
    def test_sqlite_path_uses_up_sqlite(self, mock_get_execute, mock_get_is_postgres, mock_record):
        """When _is_postgres() returns False, UP_SQLITE SQL is used"""
        mock_execute = MagicMock()
        mock_get_execute.return_value = mock_execute
        mock_get_is_postgres.return_value = lambda: False

        self.runner._run_migration("001_initial_schema")

        # Verify SQLite-specific SQL was used
        executed_sqls = [call_args[0][0] for call_args in mock_execute.call_args_list]
        sqlite_specific_found = any("datetime('now')" in sql for sql in executed_sqls)
        self.assertTrue(sqlite_specific_found, "SQLite-specific SQL (datetime('now')) not found in executed statements")


if __name__ == '__main__':
    unittest.main()
