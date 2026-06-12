"""
Database Migrations Package
===========================

Each migration file follows the naming pattern: NNN_description.py
where NNN is a zero-padded sequence number (001, 002, ...).

Migration files must define:
- MIGRATION_ID: str — unique identifier matching filename
- UP_PG: str — SQL to run on PostgreSQL
- UP_SQLITE: str — SQL to run on SQLite
- DOWN: str — SQL to reverse (not currently used)
"""
