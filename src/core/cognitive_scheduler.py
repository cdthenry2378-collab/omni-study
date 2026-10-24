"""Persistent Leitner and FSRS-inspired scheduling with SQLite."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json, math, sqlite3, uuid

LEITNER_DAYS = {1: 1, 2: 2, 3: 4, 4: 9, 5: 14}

class CognitiveScheduler:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self):
        con = sqlite3.connect(self.db_path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _initialize(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS cards(
              id TEXT PRIMARY KEY, front TEXT NOT NULL, back TEXT NOT NULL,
              source_name TEXT NOT NULL, page_num INTEGER NOT NULL DEFAULT 1,
              rect_json TEXT NOT NULL DEFAULT '[0,0,1,1]', box INTEGER NOT NULL DEFAULT 1,
              due_at TEXT NOT NULL, stability REAL NOT NULL DEFAULT 0.4,
              difficulty REAL NOT NULL DEFAULT 5.0, reps INTEGER NOT NULL DEFAULT 0,
              lapses INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(due_at);
            CREATE TABLE IF NOT EXISTS streaks(
              id INTEGER PRIMARY KEY CHECK(id=1), current_streak INTEGER NOT NULL DEFAULT 0,
              best_streak INTEGER NOT NULL DEFAULT 0, last_review_date TEXT);
            INSERT OR IGNORE INTO streaks(id) VALUES(1);
            CREATE TABLE IF NOT EXISTS focus_blocks(
              id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT,
              planned_minutes INTEGER NOT NULL, completed INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS todo_items(
              id TEXT PRIMARY KEY, text TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL, completed_at TEXT);
            CREATE TABLE IF NOT EXISTS reviews(
              id TEXT PRIMARY KEY, card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
              reviewed_at TEXT NOT NULL, rating INTEGER NOT NULL, mode TEXT NOT NULL,
              old_box INTEGER NOT NULL, new_box INTEGER NOT NULL, retrievability REAL NOT NULL);
            """)

    @staticmethod
    def now():
        return datetime.now(timezone.utc)

    def add_card(self, front: str, back: str, source_name: str, page_num: int = 1,
                 rect=(0, 0, 1, 1), card_id: str | None = None) -> str:
        if not front.strip() or not back.strip() or not source_name.strip():
            raise ValueError("Front, back, and source document are required.")
        card_id = card_id or str(uuid.uuid4())
        now = self.now().isoformat()
        with self.connect() as db:
            db.execute("""INSERT INTO cards(id,front,back,source_name,page_num,rect_json,due_at,created_at)
                          VALUES(?,?,?,?,?,?,?,?)""",
                       (card_id, front.strip(), back.strip(), source_name, int(page_num),
                        json.dumps(list(rect)), now, now))
        return card_id

    def due_cards(self, limit: int = 100) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM cards WHERE due_at<=? ORDER BY due_at LIMIT ?",
                              (self.now().isoformat(), max(1, limit))).fetchall()
        result = []
        for row in rows:
            item = dict(row); item["rect"] = json.loads(item.pop("rect_json"))
            result.append(item)
        return result

    @staticmethod
    def retrievability(stability: float, elapsed_days: float) -> float:
        # FSRS-family power-law forgetting curve; stability is measured in days.
        s = max(0.05, float(stability))
        return float((1.0 + max(0.0, elapsed_days) / (9.0 * s)) ** -1.0)

    @staticmethod
    def _fsrs_update(stability: float, difficulty: float, rating: int, elapsed_days: float):
        # Transparent FSRS-inspired heuristic, not a claim of bit-for-bit FSRS 4.5 parity.
        r = CognitiveScheduler.retrievability(stability, elapsed_days)
        difficulty = min(10.0, max(1.0, difficulty + (3 - rating) * 0.55))
        if rating == 1:
            stability = max(0.1, stability * (0.45 + 0.1 * r))
        else:
            gain = {2: 1.15, 3: 1.8, 4: 2.5}[rating]
            stability = max(0.1, stability * (gain + (10 - difficulty) * 0.08) * (1.1 - r * 0.25))
        return stability, difficulty, r

    def review(self, card_id: str, rating: int, mode: str = "leitner") -> dict:
        """rating 1=again, 2=hard, 3=good, 4=easy."""
        if rating not in (1, 2, 3, 4):
            raise ValueError("rating must be 1 (again), 2 (hard), 3 (good), or 4 (easy)")
        now = self.now()
        with self.connect() as db:
            row = db.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
            if row is None:
                raise KeyError(f"Unknown card: {card_id}")
            old_box = int(row["box"])
            last = db.execute("SELECT reviewed_at FROM reviews WHERE card_id=? ORDER BY reviewed_at DESC LIMIT 1",
                              (card_id,)).fetchone()
            elapsed = max(0.0, (now - datetime.fromisoformat(last["reviewed_at"])).total_seconds()/86400) if last else 0
            stability, difficulty, r = self._fsrs_update(row["stability"], row["difficulty"], rating, elapsed)
            if mode == "leitner":
                new_box = 1 if rating == 1 else min(5, old_box + (1 if rating >= 3 else 0))
                days = LEITNER_DAYS[new_box]
            elif mode == "fsrs":
                new_box = old_box if rating > 1 else 1
                days = max(1, min(365, int(round(stability * (1.0 / max(0.1, difficulty / 10.0))))))
            else:
                raise ValueError("mode must be 'leitner' or 'fsrs'")
            due = now + timedelta(days=days)
            db.execute("""UPDATE cards SET box=?,due_at=?,stability=?,difficulty=?,reps=reps+1,
                          lapses=lapses+?,page_num=page_num WHERE id=?""",
                       (new_box, due.isoformat(), stability, difficulty, int(rating == 1), card_id))
            db.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?)",
                       (str(uuid.uuid4()), card_id, now.isoformat(), rating, mode, old_box, new_box, r))
            self._update_streak(db, now.date().isoformat())
            return {"card_id": card_id, "old_box": old_box, "new_box": new_box,
                    "due_at": due.isoformat(), "stability": stability,
                    "difficulty": difficulty, "retrievability": r}

    @staticmethod
    def _update_streak(db, day: str):
        row = db.execute("SELECT current_streak,best_streak,last_review_date FROM streaks WHERE id=1").fetchone()
        last = row["last_review_date"]
        if last != day:
            if last and (datetime.fromisoformat(day).date() - datetime.fromisoformat(last).date()).days == 1:
                current = row["current_streak"] + 1
            else:
                current = 1
            db.execute("UPDATE streaks SET current_streak=?,best_streak=?,last_review_date=? WHERE id=1",
                       (current, max(current, row["best_streak"]), day))

    def add_todo(self, text: str) -> str:
        if not text.strip():
            raise ValueError("To-do text cannot be empty.")
        item_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO todo_items(id,text,created_at) VALUES(?,?,?)",
                       (item_id, text.strip(), self.now().isoformat()))
        return item_id

    def list_todos(self, include_done: bool = False) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM todo_items " + ("" if include_done else "WHERE done=0 ") +
                              "ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def complete_todo(self, item_id: str, done: bool = True):
        with self.connect() as db:
            cur = db.execute("UPDATE todo_items SET done=?,completed_at=? WHERE id=?",
                             (int(done), self.now().isoformat() if done else None, item_id))
            if not cur.rowcount:
                raise KeyError(item_id)

    def start_focus(self, planned_minutes: int, note: str = "") -> str:
        if not 1 <= planned_minutes <= 480:
            raise ValueError("Focus duration must be between 1 and 480 minutes.")
        item_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO focus_blocks(id,started_at,planned_minutes,note) VALUES(?,?,?,?)",
                       (item_id, self.now().isoformat(), planned_minutes, note))
        return item_id

    def end_focus(self, block_id: str, completed: bool = True):
        with self.connect() as db:
            cur = db.execute("UPDATE focus_blocks SET ended_at=?,completed=? WHERE id=? AND ended_at IS NULL",
                             (self.now().isoformat(), int(completed), block_id))
            if not cur.rowcount:
                raise KeyError(f"Unknown or already ended focus block: {block_id}")
