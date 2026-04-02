from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix


BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "todo.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        DATABASE.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(DATABASE, timeout=10)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_: object | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE, timeout=10)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            priority TEXT NOT NULL DEFAULT 'Medium',
            is_complete INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    db.commit()
    db.close()


def fetch_task(task_id: int) -> sqlite3.Row | None:
    return get_db().execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


@app.before_request
def log_request() -> None:
    app.logger.info("Request received: %s %s", request.method, request.path)


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/")
def index():
    status = request.args.get("status", "all")
    priority = request.args.get("priority", "all")
    search = request.args.get("search", "").strip()

    query = "SELECT * FROM tasks WHERE 1=1"
    params: list[str] = []

    if status == "open":
        query += " AND is_complete = 0"
    elif status == "completed":
        query += " AND is_complete = 1"

    if priority in {"Low", "Medium", "High"}:
        query += " AND priority = ?"
        params.append(priority)

    if search:
        query += " AND (title LIKE ? OR description LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term])

    query += """
        ORDER BY
            CASE priority
                WHEN 'High' THEN 1
                WHEN 'Medium' THEN 2
                ELSE 3
            END,
            CASE
                WHEN due_date IS NULL OR due_date = '' THEN 1
                ELSE 0
            END,
            due_date ASC,
            created_at DESC
    """

    tasks = get_db().execute(query, params).fetchall()
    stats = get_db().execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN is_complete = 1 THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN is_complete = 0 THEN 1 ELSE 0 END) AS open
        FROM tasks
        """
    ).fetchone()

    return render_template(
        "index.html",
        tasks=tasks,
        status=status,
        priority=priority,
        search=search,
        stats=stats,
        today=datetime.today().date().isoformat(),
    )


@app.post("/tasks")
def create_task():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    due_date = request.form.get("due_date", "").strip() or None
    priority = request.form.get("priority", "Medium")

    if not title:
        flash("Task title is required.", "error")
        return redirect(url_for("index"))

    if priority not in {"Low", "Medium", "High"}:
        priority = "Medium"

    get_db().execute(
        """
        INSERT INTO tasks (title, description, due_date, priority, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (title, description, due_date, priority, datetime.utcnow().isoformat(timespec="seconds")),
    )
    get_db().commit()
    flash("Task added successfully.", "success")
    return redirect(url_for("index"))


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id: int):
    task = fetch_task(task_id)
    if task is None:
        flash("Task not found.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date = request.form.get("due_date", "").strip() or None
        priority = request.form.get("priority", "Medium")

        if not title:
            flash("Task title is required.", "error")
            return render_template("edit.html", task=task)

        if priority not in {"Low", "Medium", "High"}:
            priority = "Medium"

        get_db().execute(
            """
            UPDATE tasks
            SET title = ?, description = ?, due_date = ?, priority = ?
            WHERE id = ?
            """,
            (title, description, due_date, priority, task_id),
        )
        get_db().commit()
        flash("Task updated successfully.", "success")
        return redirect(url_for("index"))

    return render_template("edit.html", task=task)


@app.post("/tasks/<int:task_id>/toggle")
def toggle_task(task_id: int):
    task = fetch_task(task_id)
    if task is None:
        flash("Task not found.", "error")
        return redirect(url_for("index"))

    new_status = 0 if task["is_complete"] else 1
    get_db().execute("UPDATE tasks SET is_complete = ? WHERE id = ?", (new_status, task_id))
    get_db().commit()

    message = "Task marked as complete." if new_status else "Task marked as open."
    flash(message, "success")
    return redirect(url_for("index"))


@app.post("/tasks/<int:task_id>/delete")
def delete_task(task_id: int):
    task = fetch_task(task_id)
    if task is None:
        flash("Task not found.", "error")
        return redirect(url_for("index"))

    get_db().execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    get_db().commit()
    flash("Task deleted.", "success")
    return redirect(url_for("index"))


@app.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    app.logger.exception("Unhandled application error: %s", error)
    return render_template("error.html"), 500

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="0.0.0.0", port=port, debug=debug)
