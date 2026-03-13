import traceback, time
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[1] / "data" / "app.log"

def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def log_exception(prefix: str, e: Exception):
    tb = traceback.format_exc()
    log(f"{prefix}: {e}\n{tb}")
