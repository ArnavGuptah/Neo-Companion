
import argparse
import csv
import sqlite3
from pathlib import Path

from .catalogue import DEFAULT_DB_PATH


def build_report(db_path=DEFAULT_DB_PATH):
    db_path = Path(db_path)

    if not db_path.exists():
        return (
            f"No behaviour database found at: {db_path}\n"
            "Run Neo first to collect data."
        )

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        sessions = conn.execute(
            "SELECT COUNT(*) FROM sessions"
        ).fetchone()[0]

        events = conn.execute(
            "SELECT COUNT(*) FROM events"
        ).fetchone()[0]

        pets = conn.execute("""
            SELECT
                COALESCE(SUM(
                    CASE WHEN accepted = 1 THEN 1 ELSE 0 END
                ), 0) AS accepted,

                COALESCE(SUM(
                    CASE WHEN accepted = 0 THEN 1 ELSE 0 END
                ), 0) AS rejected,

                COALESCE(SUM(
                    CASE
                        WHEN accepted = 1 AND mood_changed = 1
                        THEN 1 ELSE 0
                    END
                ), 0) AS changed

            FROM events
            WHERE event_type = 'pet'
        """).fetchone()

        moods = conn.execute("""
            SELECT mood, COUNT(*) AS n
            FROM events
            WHERE event_type = 'mood_change'
            AND mood IS NOT NULL
            GROUP BY mood
            ORDER BY n DESC
        """).fetchall()

        pet_responses = conn.execute("""
            SELECT mood, COUNT(*) AS n
            FROM events
            WHERE event_type = 'pet'
            AND accepted = 1
            AND mood IS NOT NULL
            GROUP BY mood
            ORDER BY n DESC
        """).fetchall()

        durations = conn.execute("""
            SELECT mood,
                   COUNT(*) AS n,
                   AVG(duration_seconds) AS avg_duration,
                   MIN(duration_seconds) AS min_duration,
                   MAX(duration_seconds) AS max_duration
            FROM mood_spans
            WHERE duration_seconds IS NOT NULL
            GROUP BY mood
            ORDER BY avg_duration DESC
        """).fetchall()

        lines = [
        "NEO BEHAVIOUR REPORT V3",
        "=" * 45,
        f"Database: {db_path}",
        f"Sessions recorded: {sessions}",
        f"Events recorded: {events}",
        f"Accepted pet attempts: {pets['accepted'] or 0}",
        f"Rejected pet attempts: {pets['rejected'] or 0}",
        f"Accepted pets followed by a mood change: "
        f"{pets['changed'] or 0}",
        "",
        "MOOD TRANSITIONS",
        "-" * 45,
    ]

    if moods:
        lines.extend(
            f"{row['mood']:<14} {row['n']}"
            for row in moods
        )
    else:
        lines.append("No mood transitions recorded yet.")

    lines.extend([
        "",
        "ACCEPTED PET RESPONSE HISTORY",
        "-" * 45,
    ])

    if pet_responses:
        lines.extend(
            f"{row['mood']:<14} {row['n']}"
            for row in pet_responses
        )
    else:
        lines.append("No accepted pet responses recorded yet.")

    lines.extend([
        "",
        "COMPLETED MOOD DURATIONS",
        "-" * 45,
    ])

    if durations:
        lines.extend(
            f"{row['mood']:<14} n={row['n']}  "
            f"avg={row['avg_duration']:.2f}s  "
            f"min={row['min_duration']:.2f}s  "
            f"max={row['max_duration']:.2f}s"
            for row in durations
        )
    else:
        lines.append("No completed mood durations recorded yet.")

    lines.extend([
        "",
        "Notes:",
        "- Historical records may contain duplicate events from older versions.",
        "- Pet response history uses accepted pet events.",
        "- Mood transitions count recorded mood-change events.",
        "- These are programmed behaviour states, not measurements "
        "of genuine emotions.",
    ])

    return "\n".join(lines)


def export_csv(db_path, output_path, table):
    db_path = Path(db_path)

    if not db_path.exists():
        print(f"Export skipped: database not found at {db_path}")
        return

    allowed_tables = {"events", "mood_spans"}
    if table not in allowed_tables:
        raise ValueError("Unsupported export table")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM {table} ORDER BY 1"
        ).fetchall()

    with Path(output_path).open(
        "w", newline="", encoding="utf-8"
    ) as file:
        if rows:
            fields = rows[0].keys()
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows([dict(row) for row in rows])
        else:
            print(f"No rows to export from table: {table}")
            return

    print(f"CSV exported to: {Path(output_path).resolve()}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--csv", dest="csv_path")
    parser.add_argument("--durations-csv")
    args = parser.parse_args()

    print(build_report(args.db))

    if args.csv_path:
        export_csv(args.db, args.csv_path, "events")

    if args.durations_csv:
        export_csv(args.db, args.durations_csv, "mood_spans")


if __name__ == "__main__":
    main()
