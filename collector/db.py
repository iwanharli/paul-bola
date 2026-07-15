"""Postgres connection + upsert helpers for db_boforecasting."""
import json
import os
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Every caller across collector/ and model/ imports this module, so load .env
# here once with a path anchored to THIS file -- not relying on load_dotenv()'s
# cwd-dependent search. That cwd-dependent version "worked" on local macOS
# only because Postgres.app trusts local socket connections without a
# password; it failed hard (fe_sendauth: no password supplied) the moment
# this ran on a server with real password auth, since callers in model/ run
# with cwd=model/ where no .env exists (it lives in collector/).
load_dotenv(Path(__file__).resolve().parent / ".env")


def _admin_connect():
    """Connect to the default 'postgres' database to create db_boforecasting if missing."""
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        user=os.environ.get("PGUSER"),
        password=os.environ.get("PGPASSWORD") or None,
        dbname="postgres",
    )


def ensure_database():
    target_db = os.environ.get("PGDATABASE", "db_boforecasting")
    conn = _admin_connect()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{target_db}"')
                print(f"Created database {target_db}")
    finally:
        conn.close()


def connect():
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        user=os.environ.get("PGUSER"),
        password=os.environ.get("PGPASSWORD") or None,
        dbname=os.environ.get("PGDATABASE", "db_boforecasting"),
    )


def apply_schema(conn, schema_path: str):
    with open(schema_path) as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def upsert(conn, table: str, row: dict, conflict_col: str = "id"):
    cols = list(row.keys())
    values = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in row.values()]
    col_list = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != conflict_col)
    sql = (
        f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_col}) DO UPDATE SET {updates}"
    )
    with conn.cursor() as cur:
        cur.execute(sql, values)


def upsert_composite(conn, table: str, row: dict, conflict_cols: list[str], coalesce_cols=None):
    """
    coalesce_cols: columns updated as COALESCE(EXCLUDED.col, table.col) instead
    of a blanket overwrite -- so an incoming NULL never clobbers an existing
    non-null value. Used e.g. for worldcup_matches scores, which a faster
    source (live_result_collect) may fill before openfootball catches up;
    openfootball's later NULL for that match must not wipe the result.
    """
    coalesce_cols = set(coalesce_cols or [])
    cols = list(row.keys())
    values = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in row.values()]
    col_list = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    conflict_list = ", ".join(conflict_cols)
    update_parts = []
    for c in cols:
        if c in conflict_cols:
            continue
        if c in coalesce_cols:
            update_parts.append(f"{c} = COALESCE(EXCLUDED.{c}, {table}.{c})")
        else:
            update_parts.append(f"{c} = EXCLUDED.{c}")
    updates = ", ".join(update_parts)
    sql = (
        f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_list}) DO UPDATE SET {updates}"
    )
    with conn.cursor() as cur:
        cur.execute(sql, values)


def log_collection(conn, source: str, endpoint: str, scope: str, status: str, detail: str = ""):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO collection_log (source, endpoint, scope, status, detail) "
            "VALUES (%s, %s, %s, %s, %s)",
            (source, endpoint, scope, status, detail),
        )
    conn.commit()
