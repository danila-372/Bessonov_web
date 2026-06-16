import sqlite3
from datetime import datetime, timezone

from flask import current_app, g
from werkzeug.security import generate_password_hash


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


def close_db(error=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            last_name TEXT,
            first_name TEXT NOT NULL,
            middle_name TEXT,
            role_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE SET NULL
        );
        """
    )

    role_count = db.execute("SELECT COUNT(*) FROM roles").fetchone()[0]
    if role_count == 0:
        db.executemany(
            "INSERT INTO roles (name, description) VALUES (?, ?)",
            [
                ("Администратор", "Полный доступ к управлению пользователями"),
                ("Пользователь", "Обычная учетная запись пользователя"),
            ],
        )

    user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0:
        admin_role_id = db.execute(
            "SELECT id FROM roles WHERE name = ?", ("Администратор",)
        ).fetchone()["id"]
        db.execute(
            """
            INSERT INTO users
                (login, password_hash, last_name, first_name, middle_name, role_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "admin",
                generate_password_hash("Admin123!"),
                "Системный",
                "Администратор",
                "",
                admin_role_id,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )

    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
