import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "schutz.db")

def get_connection():
    """Dapatkan koneksi SQLite"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def execute(query: str, params=None):
    if params is None:
        params = []
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    
    class Result:
        def __init__(self, rows):
            self.rows = rows
    
    result = Result(cursor.fetchall())
    conn.close()
    return result

def fetch_one(query: str, params=None):
    if params is None:
        params = []
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    return row

def fetch_all(query: str, params=None):
    if params is None:
        params = []
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows

# Export biar gampang
__all__ = ['execute', 'fetch_one', 'fetch_all', 'get_connection']
