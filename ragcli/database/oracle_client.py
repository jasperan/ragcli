"""Oracle Database 26ai client for ragcli."""

import oracledb
from typing import Optional
from .schemas import get_create_schemas_sql

class OracleClient:
    def __init__(self, config: dict):
        self.config = config
        self.pool = None
        self._connect()
    
    def _connect(self):
        """Establish connection pool."""
        username = self.config['oracle']['username']
        password = self.config['oracle']['password']
        dsn = self.config['oracle']['dsn']
        pool_size = self.config['oracle'].get('pool_size', 10)
        
        # TODO: Add TLS config if use_tls
        self.pool = oracledb.create_pool(
            user=username,
            password=password,
            dsn=dsn,
            min=1,
            max=pool_size,
            increment=1,
            threadeds=True
        )
    
    def get_connection(self) -> oracledb.Connection:
        """Get a connection from the pool."""
        return self.pool.acquire()
    
    def init_db(self):
        """Initialize database schemas and indexes."""
        conn = self.get_connection()
        try:
            for sql in get_create_schemas_sql():
                conn.execute(sql)
            conn.commit()
            print("Database schemas created successfully.")
        except oracledb.Error as e:
            conn.rollback()
            raise Exception(f"Failed to create schemas: {e}")
        finally:
            conn.close()
    
    def close(self):
        """Close the pool."""
        if self.pool:
            self.pool.close()

# TODO: Add error handling, retries (5 retries for connection), auto-index selection
