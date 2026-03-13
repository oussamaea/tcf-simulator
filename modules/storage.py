
import json, time
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
DATA.mkdir(exist_ok=True, parents=True)
HIST = DATA / "history.json"
SRS = DATA / "vocab_srs.json"

def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default

def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_history():
    return load_json(HIST, [])

def save_history(history):
    save_json(HIST, history)

def new_session_record(kind, res, nclc, band):
    history = load_history()
    rec = {"ts": int(time.time()), "type": kind, "result": res, "predicted_nclc": nclc, "band": band}
    history.append(rec); save_history(history)
    return rec

def load_srs():
    return load_json(SRS, {"cards": [], "last_id": 0})

def save_srs(data):
    save_json(SRS, data)
