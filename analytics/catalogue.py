
"""SQLite event catalogue for Neo behaviour analytics."""
import sqlite3
import uuid
from pathlib import Path

DEFAULT_DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "neo_behaviour.db"
)


class BehaviourCatalogue:
    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _create_schema(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL DEFAULT
                        (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    ended_at TEXT,
                    app_mode TEXT NOT NULL DEFAULT 'regular'
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL DEFAULT
                        (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    elapsed_seconds REAL,
                    event_type TEXT NOT NULL,
                    source TEXT,
                    previous_mood TEXT,
                    mood TEXT,
                    affection_before INTEGER,
                    affection_after INTEGER,
                    total_pets INTEGER,
                    seconds_since_last_pet REAL,
                    accepted INTEGER,
                    mood_changed INTEGER,
                    details TEXT,
                    FOREIGN KEY(session_id)
                        REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS mood_spans (
                    span_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    mood TEXT NOT NULL,
                    source TEXT NOT NULL,
                    started_elapsed REAL NOT NULL,
                    ended_elapsed REAL,
                    duration_seconds REAL,
                    FOREIGN KEY(session_id)
                        REFERENCES sessions(session_id)
                );

                CREATE INDEX IF NOT EXISTS idx_events_time
                    ON events(session_id, timestamp);

                CREATE INDEX IF NOT EXISTS idx_spans_mood
                    ON mood_spans(session_id, mood);
            """)

            # Migrate an existing database without deleting old data.
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(events)")
            }
            if "mood_changed" not in columns:
                conn.execute(
                    "ALTER TABLE events ADD COLUMN mood_changed INTEGER"
                )

    def start_session(self, app_mode="regular"):
        session_id = uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, app_mode) VALUES (?, ?)",
                (session_id, app_mode),
            )
        return session_id

    def end_session(self, session_id):
        with self._connect() as conn:
            conn.execute(
                """UPDATE sessions
                   SET ended_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
                   WHERE session_id = ?""",
                (session_id,),
            )

    def log_event(
        self,
        session_id,
        event_type,
        *,
        elapsed_seconds=None,
        source=None,
        previous_mood=None,
        mood=None,
        affection_before=None,
        affection_after=None,
        total_pets=None,
        seconds_since_last_pet=None,
        accepted=None,
        mood_changed=None,
        details=None,
    ):
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO events (
                    session_id, elapsed_seconds, event_type, source,
                    previous_mood, mood, affection_before, affection_after,
                    total_pets, seconds_since_last_pet, accepted,
                    mood_changed, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id, elapsed_seconds, event_type, source,
                    previous_mood, mood, affection_before, affection_after,
                    total_pets, seconds_since_last_pet,
                    None if accepted is None else int(accepted),
                    None if mood_changed is None else int(mood_changed),
                    details,
                ),
            )

    def start_mood_span(
        self, session_id, mood, source, elapsed_seconds
    ):
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO mood_spans
                   (session_id, mood, source, started_elapsed)
                   VALUES (?, ?, ?, ?)""",
                (session_id, mood, source, elapsed_seconds),
            )

    def close_mood_span(self, session_id, elapsed_seconds):
        with self._connect() as conn:
            row = conn.execute(
                """SELECT span_id, started_elapsed
                   FROM mood_spans
                   WHERE session_id = ? AND ended_elapsed IS NULL
                   ORDER BY span_id DESC LIMIT 1""",
                (session_id,),
            ).fetchone()

            if row is not None:
                duration = max(
                    0.0, elapsed_seconds - row["started_elapsed"]
                )
                conn.execute(
                    """UPDATE mood_spans
                       SET ended_elapsed = ?, duration_seconds = ?
                       WHERE span_id = ?""",
                    (elapsed_seconds, duration, row["span_id"]),
                )

    def transition_mood(
        self,
        session_id,
        *,
        elapsed_seconds,
        previous_mood,
        mood,
        source,
        affection,
        total_pets,
    ):
        """Log a genuine state transition exactly once."""
        if previous_mood == mood:
            return

        self.log_event(
            session_id,
            "mood_change",
            elapsed_seconds=elapsed_seconds,
            source=source,
            previous_mood=previous_mood,
            mood=mood,
            affection_before=affection,
            affection_after=affection,
            total_pets=total_pets,
            mood_changed=True,
        )

        self.close_mood_span(session_id, elapsed_seconds)
        self.start_mood_span(
            session_id, mood, source, elapsed_seconds
        )
