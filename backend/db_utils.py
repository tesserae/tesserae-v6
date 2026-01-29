"""
Database Utilities
Consolidated database access patterns with proper error handling
"""
import os
import psycopg2
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL')

class DatabaseError(Exception):
    """Custom exception for database operations"""
    pass

@contextmanager
def get_db_connection():
    """Context manager for database connections with proper cleanup"""
    conn = None
    try:
        if not DATABASE_URL:
            raise DatabaseError("DATABASE_URL not configured")
        conn = psycopg2.connect(DATABASE_URL)
        yield conn
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        raise DatabaseError(f"Database connection failed: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@contextmanager
def get_db_cursor(commit=True):
    """Context manager for database cursor with automatic commit/rollback"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            cur.close()

def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    """Execute a query with proper error handling
    
    Args:
        query: SQL query string
        params: Query parameters (tuple or dict)
        fetch_one: Return single row
        fetch_all: Return all rows
    
    Returns:
        Query result or None
    """
    try:
        with get_db_cursor() as cur:
            cur.execute(query, params)
            if fetch_one:
                return cur.fetchone()
            elif fetch_all:
                return cur.fetchall()
            return None
    except DatabaseError:
        raise
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise DatabaseError(f"Query failed: {e}")

def execute_insert(query, params=None, returning=False):
    """Execute an INSERT query with optional RETURNING clause
    
    Args:
        query: SQL INSERT query
        params: Query parameters
        returning: If True, fetch and return the first column of first row
    
    Returns:
        Inserted ID if returning=True, else None
    """
    try:
        with get_db_cursor() as cur:
            cur.execute(query, params)
            if returning:
                result = cur.fetchone()
                return result[0] if result else None
            return None
    except DatabaseError:
        raise
    except Exception as e:
        logger.error(f"Insert failed: {e}")
        raise DatabaseError(f"Insert failed: {e}")
