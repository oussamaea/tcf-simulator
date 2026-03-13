
import time
from typing import Dict, Any
from .storage import load_srs, save_srs

def _now():
    return int(time.time())

def _days(n):  # seconds for n days
    return n*86400

# Simple spaced repetition schedule (SM-2 inspired but simplified)
SCHEDULE = [0, 1, 3, 7, 14, 30, 60]

def add_card(front: str, back: str):
    srs = load_srs()
    srs["last_id"] += 1
    srs["cards"].append({
        "id": srs["last_id"],
        "front": front.strip(),
        "back": back.strip(),
        "stage": 0,
        "due": _now()
    })
    save_srs(srs)

def get_due_cards(limit=20):
    srs = load_srs()
    now = _now()
    cards = [c for c in srs["cards"] if c["due"] <= now]
    return cards[:limit]

def review_card(card_id: int, correct: bool):
    srs = load_srs()
    for c in srs["cards"]:
        if c["id"] == card_id:
            if correct:
                c["stage"] = min(c["stage"]+1, len(SCHEDULE)-1)
            else:
                c["stage"] = max(c["stage"]-1, 0)
            c["due"] = _now() + _days(SCHEDULE[c["stage"]])
            break
    save_srs(srs)

def all_cards():
    return load_srs().get("cards", [])
