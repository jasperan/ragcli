#!/usr/bin/env python3
"""Manual Oracle smoke test.

This file is named like a pytest module, so keep all live database work behind
``main()``. That lets ``pytest`` collect the repository on machines without a
running Oracle service.
"""

from __future__ import annotations

from ragcli.config.config_manager import load_config
from ragcli.database.oracle_client import OracleClient


def main() -> int:
    client: OracleClient | None = None
    cursor = None
    try:
        print("Loading config...")
        config = load_config()
        print("Config loaded successfully.")

        print("Creating OracleClient...")
        client = OracleClient(config)
        print("OracleClient created.")

        print("Getting connection...")
        conn = client.get_connection()
        print("Connection acquired.")

        cursor = conn.cursor()

        print("Executing query...")
        cursor.execute("SELECT COUNT(*) FROM DOCUMENTS")
        count = cursor.fetchone()[0]
        print(f"SUCCESS: DOCUMENTS table has {count} rows.")
        print("Connection closed. Test completed successfully.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1
    finally:
        if cursor is not None:
            cursor.close()
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
