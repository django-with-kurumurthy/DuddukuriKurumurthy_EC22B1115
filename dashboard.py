import streamlit as st
import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller
import plotly.express as px
import sqlite3
import os
from streamlit_autorefresh import st_autorefresh

# -----------------------------
# Page Configuration
# -----------------------------
st.set_page_config(layout="wide", page_title="Quant Developer Dashboard")
st.title("📈 Quant Developer Real-Time Analytics Dashboard")

# -----------------------------
# Sidebar Controls
# -----------------------------
st.sidebar.header("⚙️ Settings")
mode = st.sidebar.radio("Data Source", ["📁 NDJSON File", "🗄️ Live Database"], index=1)

timeframe = st.sidebar.selectbox(
    "Resample timeframe", ["1S", "1T (1 minute)", "5T (5 minutes)"], index=1
)
rolling_window = st.sidebar.number_input("Rolling window (periods)", 3, 200, 20)
z_alert = st.sidebar.slider("Z-score alert threshold", 0.5, 5.0, 2.0, 0.1)
refresh_rate = st.sidebar.slider("Auto-refresh interval (seconds)", 2, 30, 5)

# -----------------------------
# Auto Refresh Setup (DB mode uses autorefresh)
# -----------------------------
if mode == "🗄️ Live Database":
    _ = st_autorefresh(interval=refresh_rate * 1000, key="live_refresh")

# -----------------------------
# Cached file reader (safe)
# -----------------------------
@st.cache_data(ttl=10)
def read_ndjson(file_path: str) -> pd.DataFrame:
    """Read NDJSON file and normalize types. Cached safely (no widgets here)."""
    df = pd.read_json(file_path, lines=True)
    # permissive parsing for timestamps
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce", infer_datetime_format=True)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["ts", "price"])
    return df.sort_values("ts")

# -----------------------------
# DB loader (not cached — small query each refresh)
# -----------------------------
def load_from_db() -> pd.DataFrame:
    conn = sqlite3.connect("tick_data.db")
    query = "SELECT symbol, timestamp AS ts, price FROM ticks ORDER BY timestamp DESC LIMIT 5000"
    try:
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        conn.close()
        st.error("Error reading DB: " + str(e))
        return pd.DataFrame()
    conn.close()
    if df.empty:
        return pd.DataFrame()
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce", infer_datetime_format=True)
    df = df.dropna(subset=["ts", "price", "symbol"])
    return df.sort_values("ts")

# -----------------------------
# Fetch Data: NDJSON or DB
# -----------------------------
if mode == "📁 NDJSON File":
    # list files and select (widget outside cached function)
    ndjson_files = [f for f in os.listdir() if f.endswith(".ndjson")]
    if not ndjson_files:
        st.sidebar.warning("⚠️ No NDJSON files found in folder. Add .ndjson or switch to Live Database.")
        st.stop()
    selected_file = st.sidebar.selectbox("Select NDJSON file", ndjson_files)
    # read using cached reader
    try:
        df = read_ndjson(selected_file)
    except Exception as e:
        st.error("Error reading selected NDJSON: " + str(e))
        st.stop()
else:
    st.sidebar.info("🔄 Live data auto-refresh every few seconds")
    df = load_from_db()
    if df.empty:
        st.sidebar.warning("⚠️ Database empty or no ticks yet. Start collector or switch to NDJSON.")
        st.stop()

st.sidebar.success(f"✅ Loaded {len(df)} rows")
if df.empty:
    st.stop()

# -----------------------------
# Symbol Selection
# -----------------------------
symbols = df["symbol"].unique().tolist()
if len(symbols) < 2:
    st.warning("⚠️ Not enough symbols in data. Waiting for more...")
    st.stop()

col1, col2 = st.columns(2)
s1 = col1.selectbox("Symbol 1", symbols, index=0)
s2 = col2.selectbox("Symbol 2", symbols, index=1 if len(symbols) > 1 else 0)

if s1 == s2:
    st.warning("Please select two different symbols.")
    st.stop()

# -----------------------------
# Resample and Analytics
# -----------------------------
df = df.set_index("ts")
try:
    resampled = df.groupby("symbol")["price"].resample(timeframe.split()[0]).last().unstack(0)
except Exception as e:
    st.error("Error during resampling: " + str(e))
    st.stop()

# forward-fill and drop rows that are still empty
resampled = resampled.fillna(method="ffill").dropna(how="all")
if s1 not in resampled.columns or s2 not in resampled.columns:
    st.warning("Selected symbols currently don't have resampled data. Wait for more ticks.")
    st.stop()

resampled = resampled.dropna(subset=[s1, s2])

# Compute spread & rolling stats
resampled["spread"] = resampled[s1] - resampled[s2]
resampled["mean"] = resampled["spread"].rolling(rolling_window, min_periods=1).mean()
resampled["std"] = resampled["spread"].rolling(rolling_window, min_periods=1).std().replace(0, np.nan)
resampled["zscore"] = (resampled["spread"] - resampled["mean"]) / resampled["std"]

# -----------------------------
# Hedge Ratio via OLS (safe)
# -----------------------------
hedge_ratio = np.nan
hedge_points = 0
try:
    y = resampled[s1].dropna()
    X = sm.add_constant(resampled[s2].dropna())
    joined = pd.concat([y, X], axis=1).dropna()
    hedge_points = len(joined)
    if hedge_points >= 5:
        model = sm.OLS(joined.iloc[:, 0], joined.iloc[:, 1:]).fit()
        hedge_ratio = model.params[0] if len(model.params) > 0 else np.nan
except Exception:
    hedge_ratio = np.nan

# -----------------------------
# ADF Test (safe)
# -----------------------------
adf_p = None
try:
    spread_clean = resampled["spread"].dropna()
    if len(spread_clean) >= 10:
        adf_p = adfuller(spread_clean)[1]
except Exception:
    adf_p = None

# -----------------------------
# Display Charts
# -----------------------------
st.subheader("💹 Price Comparison")
st.plotly_chart(
    px.line(resampled.reset_index(), x="ts", y=[s1, s2], title="Price Chart"),
    use_container_width=True,
)

st.subheader("📊 Spread and Z-Score")
st.plotly_chart(
    px.line(resampled.reset_index(), x="ts", y=["spread", "mean"], title="Spread"),
    use_container_width=True,
)
st.plotly_chart(
    px.line(resampled.reset_index(), x="ts", y="zscore", title="Z-Score"),
    use_container_width=True,
)

# -----------------------------
# Rolling Correlation
# -----------------------------
try:
    resampled["rolling_corr"] = resampled[s1].rolling(rolling_window, min_periods=2).corr(resampled[s2])
    st.subheader("📈 Rolling Correlation")
    st.plotly_chart(
        px.line(resampled.reset_index(), x="ts", y="rolling_corr", title="Rolling Correlation Between Symbols"),
        use_container_width=True,
    )
except Exception:
    st.info("Rolling correlation not available yet.")

# -----------------------------
# Metrics Display
# -----------------------------
colA, colB, colC = st.columns(3)
latest_spread = resampled["spread"].iloc[-1] if not resampled["spread"].empty else np.nan
colA.metric("Latest Spread", f"{latest_spread:.4f}")
colB.metric("Hedge Ratio (OLS)", f"{hedge_ratio:.4f}" if not np.isnan(hedge_ratio) else "N/A")
colC.metric("ADF p-value", f"{adf_p:.4f}" if adf_p is not None else "N/A")

st.caption(f"📊 Hedge Ratio based on {hedge_points} samples | ADF test on {len(resampled)} samples")

# -----------------------------
# Alerts & Signals
# -----------------------------
z_latest = resampled["zscore"].dropna().iloc[-1] if not resampled["zscore"].dropna().empty else np.nan
if not np.isnan(z_latest) and abs(z_latest) > z_alert:
    if z_latest > 0:
        st.error(f"⚠️ SELL Signal — z-score: {z_latest:.2f}")
    else:
        st.success(f"✅ BUY Signal — z-score: {z_latest:.2f}")

st.subheader("🧭 Mean-Reversion Trading Signal")
if not np.isnan(z_latest):
    if z_latest > 2:
        st.warning("🚨 SELL Signal: Z-Score above +2 (Overbought — potential short entry)")
    elif z_latest < 0:
        st.success("✅ BUY Signal: Z-Score below 0 (Mean reversion — potential long entry)")
    else:
        st.info("ℹ️ Neutral Zone: No strong trading signal currently")
else:
    st.info("ℹ️ Waiting for sufficient data to compute z-score...")

# -----------------------------
# Download CSV
# -----------------------------
resampled_out = resampled.fillna(0).round(6).reset_index()
csv = resampled_out.to_csv(index=False)
st.download_button("📥 Download Processed CSV", csv, "processed_data.csv", "text/csv")
