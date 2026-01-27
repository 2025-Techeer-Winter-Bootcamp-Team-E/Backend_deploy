#!/usr/bin/env python
"""Wait for database to be ready."""
import os
import sys
import time

import psycopg2


def wait_for_db():
    """Wait for PostgreSQL to be ready."""
    db_host = os.environ.get('POSTGRES_HOST', 'postgres')
    db_port = os.environ.get('POSTGRES_PORT', '5432')
    db_name = os.environ.get('POSTGRES_DB', 'backend')
    db_user = os.environ.get('POSTGRES_USER', 'postgres')
    db_password = os.environ.get('POSTGRES_PASSWORD', 'postgres')

    max_retries = 30
    retry_interval = 2

    for i in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=db_host,
                port=db_port,
                dbname=db_name,
                user=db_user,
                password=db_password,
            )
            conn.close()
            print(f"PostgreSQL is ready! (attempt {i + 1})")
            return True
        except psycopg2.OperationalError as e:
            print(f"PostgreSQL not ready yet (attempt {i + 1}/{max_retries}): {e}")
            time.sleep(retry_interval)

    print("Could not connect to PostgreSQL after maximum retries")
    sys.exit(1)


if __name__ == '__main__':
    wait_for_db()
