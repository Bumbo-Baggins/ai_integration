"""
Module 8 Student Enrollment backend.

Refactored to use a multi-layer design:
- EnrollmentDB: Handles SQLite queries and returns data dictionaries.
- EnrollmentManager: Contains business logic and validation.

Run with:
    enrollment_starter.py
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional


DB_PATH = Path(__file__).with_name("student_enrollment_practice.db")
SNAPSHOT_PATH = Path(__file__).with_name("student_enrollment_snapshot.json")

CURRENT_STUDENT = {
    "user_id": "u100",
    "name": "Maya Patel",
    "email": "maya.patel@example.edu",
}

STATUS_ENROLLED = "enrolled"
STATUS_UNENROLLED = "unenrolled"

AVAILABLE_COURSE_KEYS = [
    {
        "course_id": "MISY350",
        "course_name": "Python for Business Analytics",
        "instructor": "Dr. Rivera",
        "enrollment_key": "MISY350-SPRING",
    },
    {
        "course_id": "DATA210",
        "course_name": "Data Storytelling",
        "instructor": "Prof. Morgan",
        "enrollment_key": "DATA210-SPRING",
    },
    {
        "course_id": "WEB220",
        "course_name": "Web Apps With Streamlit",
        "instructor": "Dr. Chen",
        "enrollment_key": "WEB220-SPRING",
    },
]

SAMPLE_ENROLLMENTS = [
    ("u100", "maya.patel@example.edu", "MISY350", STATUS_ENROLLED),
    ("u100", "maya.patel@example.edu", "DATA210", STATUS_UNENROLLED),
    ("u101", "alex@example.edu", "MISY350", STATUS_ENROLLED),
    ("u102", "blair@example.edu", "WEB220", STATUS_ENROLLED),
]


class EnrollmentDB:
    """Database layer for executing raw SQLite queries."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _rows_to_dicts(self, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    def create_tables(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS courses (
                    course_id TEXT PRIMARY KEY,
                    course_name TEXT NOT NULL,
                    instructor TEXT NOT NULL,
                    enrollment_key TEXT NOT NULL UNIQUE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enrollments (
                    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    email TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'enrolled',
                    enrolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, course_id),
                    FOREIGN KEY(course_id) REFERENCES courses(course_id)
                )
                """
            )

    def seed_data(self, courses: list[dict], enrollments: list[tuple]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO courses (
                    course_id, course_name, instructor, enrollment_key
                )
                VALUES (?, ?, ?, ?)
                """,
                [
                    (c["course_id"], c["course_name"], c["instructor"], c["enrollment_key"])
                    for c in courses
                ],
            )
            conn.executemany(
                """
                INSERT OR IGNORE INTO enrollments (user_id, email, course_id, status)
                VALUES (?, ?, ?, ?)
                """,
                enrollments,
            )

    def get_all_courses(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM courses ORDER BY course_id"
            ).fetchall()
        return self._rows_to_dicts(rows)

    def get_course_by_key(self, enrollment_key: str) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM courses
                WHERE enrollment_key = ?
                """,
                (enrollment_key.strip().upper(),),
            ).fetchone()
        return dict(row) if row else None

    def get_enrollments(self, user_id: str, status: Optional[str] = None) -> list[dict[str, Any]]:
        query = """
            SELECT
                e.enrollment_id, e.user_id, e.email, e.course_id,
                c.course_name, c.instructor, e.status, e.enrolled_at
            FROM enrollments e
            JOIN courses c ON c.course_id = e.course_id
            WHERE e.user_id = ?
        """
        params = [user_id]
        
        if status:
            query += " AND e.status = ?"
            params.append(status)
            
        query += " ORDER BY c.course_id"

        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return self._rows_to_dicts(rows)

    def get_all_enrollment_records(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    e.enrollment_id, e.user_id, e.email, e.course_id,
                    c.course_name, c.instructor, e.status, e.enrolled_at
                FROM enrollments e
                JOIN courses c ON c.course_id = e.course_id
                ORDER BY e.user_id, e.course_id
                """
            ).fetchall()
        return self._rows_to_dicts(rows)

    def get_enrollment_record(self, user_id: str, course_id: str) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM enrollments
                WHERE user_id = ? AND course_id = ?
                """,
                (user_id, course_id),
            ).fetchone()
        return dict(row) if row else None

    def upsert_enrollment(self, user_id: str, email: str, course_id: str, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO enrollments (user_id, email, course_id, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, course_id)
                DO UPDATE SET
                    email = excluded.email,
                    status = excluded.status,
                    enrolled_at = CURRENT_TIMESTAMP
                """,
                (user_id, email, course_id, status),
            )

    def update_enrollment_status(self, user_id: str, course_id: str, status: str) -> bool:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE enrollments
                SET status = ?
                WHERE user_id = ? AND course_id = ?
                """,
                (status, user_id, course_id),
            )
        return cursor.rowcount > 0


class EnrollmentManager:
    """Service layer for business logic and validation."""

    def __init__(self, db: EnrollmentDB):
        self.db = db

    def get_active_classes(self, user_id: str) -> list[dict[str, Any]]:
        if not user_id:
            return []
        return self.db.get_enrollments(user_id, status=STATUS_ENROLLED)

    def enroll_with_key(self, user_id: str, email: str, enrollment_key: str) -> Optional[dict[str, Any]]:
        if not user_id or not email or "@" not in email or not enrollment_key:
            return None

        course = self.db.get_course_by_key(enrollment_key)
        if not course:
            return None

        course_id = course["course_id"]
        self.db.upsert_enrollment(user_id, email, course_id, STATUS_ENROLLED)
        return self.db.get_enrollment_record(user_id, course_id)

    def soft_unenroll_student(self, user_id: str, course_id: str) -> bool:
        if not user_id or not course_id:
            return False
        return self.db.update_enrollment_status(user_id, course_id, STATUS_UNENROLLED)

    def get_student_summary(self, user_id: str) -> dict[str, int]:
        summary = {
            "total_records": 0,
            STATUS_ENROLLED: 0,
            STATUS_UNENROLLED: 0,
        }

        records = self.db.get_enrollments(user_id)
        for record in records:
            summary["total_records"] += 1
            status = record["status"]
            if status in summary:
                summary[status] += 1

        return summary

    def export_database_snapshot(self, path: Path) -> None:
        snapshot = {
            "current_student": CURRENT_STUDENT,
            "available_course_keys": self.db.get_all_courses(),
            "enrollment_table": self.db.get_all_enrollment_records(),
        }
        path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


def main() -> None:
    db = EnrollmentDB(DB_PATH)
    db.create_tables()
    db.seed_data(AVAILABLE_COURSE_KEYS, SAMPLE_ENROLLMENTS)

    manager = EnrollmentManager(db)

    user_id = CURRENT_STUDENT["user_id"]