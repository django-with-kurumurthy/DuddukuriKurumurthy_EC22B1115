import subprocess
import os
import signal
import time
import sys

# -----------------------------
# CONFIGURATION
# -----------------------------
# Use the same Python and Streamlit inside your venv
PYTHON_CMD = sys.executable
STREAMLIT_CMD = r"D:\django\Quant_Project\venv\Scripts\streamlit.exe"

COLLECTOR_SCRIPT = "binance_stream.py"
DASHBOARD_SCRIPT = "dashboard.py"

# -----------------------------
# FUNCTION TO START A PROCESS
# -----------------------------
def start_process(cmd_list, stdout=None, stderr=None):
    """Start a subprocess and return its process handle."""
    return subprocess.Popen(cmd_list, stdout=stdout, stderr=stderr, shell=False)

# -----------------------------
# MAIN APP LAUNCHER
# -----------------------------
def main():
    print("🚀 Starting Quant Developer Project (Collector + Dashboard)...")
    cwd = os.getcwd()
    print("📂 Working directory:", cwd)

    # 1️⃣ Start the live data collector
    collector_cmd = [PYTHON_CMD, COLLECTOR_SCRIPT]
    print("▶ Starting collector:", " ".join(collector_cmd))
    try:
        collector_proc = start_process(collector_cmd)
    except FileNotFoundError as e:
        print("❌ ERROR: Could not start collector:", e)
        return

    # Allow collector to start and create DB
    time.sleep(3)

    # 2️⃣ Start the Streamlit dashboard
    streamlit_cmd = [STREAMLIT_CMD, "run", DASHBOARD_SCRIPT, "--server.port", "8501"]
    print("▶ Starting Streamlit dashboard:", " ".join(streamlit_cmd))
    try:
        dashboard_proc = start_process(streamlit_cmd)
    except FileNotFoundError as e:
        print("❌ ERROR: Could not start Streamlit:", e)
        collector_proc.terminate()
        return

    print("\n✅ Both collector and dashboard are running.")
    print("🌐 Open browser at: http://localhost:8501")
    print("🛑 Press Ctrl+C to stop both processes.\n")

    try:
        while True:
            # Check if any process exited unexpectedly
            c_ret = collector_proc.poll()
            d_ret = dashboard_proc.poll()
            if c_ret is not None:
                print(f"⚠️ Collector exited with code {c_ret}")
            if d_ret is not None:
                print(f"⚠️ Dashboard exited with code {d_ret}")
            if c_ret is not None or d_ret is not None:
                print("⛔ One of the processes stopped. Exiting app.py.")
                break
            time.sleep(3)
    except KeyboardInterrupt:
        print("\n🧹 Stopping both processes...")

    # Stop both cleanly
    for proc, name in [(collector_proc, "Collector"), (dashboard_proc, "Dashboard")]:
        try:
            if proc and proc.poll() is None:
                print(f"⏹ Terminating {name} (pid={proc.pid})...")
                proc.terminate()
                time.sleep(1)
                if proc.poll() is None:
                    proc.kill()
        except Exception as e:
            print(f"Error stopping {name}: {e}")

    print("✅ All processes stopped. Exiting cleanly.")

if __name__ == "__main__":
    main()
