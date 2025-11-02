import sqlite3
import pandas as pd

DB_PATH = "tick_data.db"

def get_latest_data(limit=1000):
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM ticks ORDER BY timestamp DESC LIMIT ?"
    df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()
    return df.sort_values("timestamp")
