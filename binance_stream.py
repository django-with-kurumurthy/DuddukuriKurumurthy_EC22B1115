import asyncio
import websockets
import json
import sqlite3
from datetime import datetime

# ------------------------------
# DATABASE SETUP
# ------------------------------
def init_db():
    conn = sqlite3.connect("tick_data.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS ticks (
                    symbol TEXT,
                    timestamp DATETIME,
                    price REAL,
                    qty REAL
                )""")
    conn.commit()
    conn.close()

# ------------------------------
# INSERT FUNCTION
# ------------------------------
def insert_tick(symbol, timestamp, price, qty):
    conn = sqlite3.connect("tick_data.db")
    c = conn.cursor()
    c.execute("INSERT INTO ticks VALUES (?, ?, ?, ?)", (symbol, timestamp, price, qty))
    conn.commit()
    conn.close()

# ------------------------------
# BINANCE STREAM HANDLER
# ------------------------------
async def binance_websocket_handler():
    uri = "wss://stream.binance.com:9443/stream?streams=btcusdt@trade/ethusdt@trade"
    print(f"Connecting to {uri}")
    async with websockets.connect(uri) as websocket:
        print("✅ Connected to Binance combined stream\n")
        while True:
            msg = await websocket.recv()
            data = json.loads(msg)
            stream = data.get("stream", "")
            payload = data.get("data", {})
            symbol = payload.get("s")
            price = float(payload.get("p", 0))
            qty = float(payload.get("q", 0))
            ts = datetime.utcfromtimestamp(payload.get("T", 0)/1000.0)
            insert_tick(symbol, ts, price, qty)
            print(f"[{symbol}] {price} @ {ts}")

if __name__ == "__main__":
    init_db()
    asyncio.get_event_loop().run_until_complete(binance_websocket_handler())
