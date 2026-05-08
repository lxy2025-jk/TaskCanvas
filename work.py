#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TaskCanvas 后端服务 - 学习任务管理 Web 应用基础 API。"""

import hashlib
import sqlite3
import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request, abort
from flask_cors import CORS

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "taskcanvas.db"

app = Flask(__name__)
CORS(app)


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(exam_date: Optional[str] = None) -> None:
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            FOREIGN KEY(owner_id) REFERENCES users(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            joined_at TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            UNIQUE(team_id, user_id),
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            team_id INTEGER,
            category TEXT NOT NULL DEFAULT 'daily',
            priority INTEGER NOT NULL DEFAULT 3,
            status TEXT NOT NULL DEFAULT 'pending',
            due_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            order_index INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            FOREIGN KEY(owner_id) REFERENCES users(id),
            FOREIGN KEY(team_id) REFERENCES teams(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS configs (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    if exam_date:
        cursor.execute(
            "INSERT OR REPLACE INTO configs (key, value) VALUES (?, ?)",
            ("exam_date", exam_date),
        )
    cursor.execute(
        "INSERT OR IGNORE INTO configs (key, value) VALUES (?, ?)",
        ("exam_date", exam_date or (datetime.date.today() + datetime.timedelta(days=180)).isoformat()),
    )

    connection.commit()
    connection.close()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()} if row is not None else {}


def get_config_value(key: str, default: Optional[str] = None) -> str:
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT value FROM configs WHERE key = ?", (key,))
    row = cursor.fetchone()
    connection.close()
    return row[0] if row else (default or "")


def parse_iso_date(value: Optional[str]) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok", "message": "TaskCanvas API is running"})


@app.route("/api/init", methods=["POST"])
def api_init():
    payload = request.get_json(silent=True) or {}
    exam_date = payload.get("exam_date")

    if exam_date:
        if not parse_iso_date(exam_date):
            return jsonify({"error": "exam_date must be YYYY-MM-DD"}), 400

    init_db(exam_date=exam_date)
    return jsonify({"status": "initialized", "exam_date": get_config_value("exam_date")})


@app.route("/api/users/register", methods=["POST"])
def register_user():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"error": "name, email, password are required"}), 400

    password_hash = hash_password(password)
    created_at = datetime.datetime.utcnow().isoformat() + "Z"

    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name, email, password_hash, created_at),
        )
        connection.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        connection.close()
        return jsonify({"error": "email already exists"}), 409

    connection.close()
    return jsonify({"id": user_id, "name": name, "email": email, "created_at": created_at})


@app.route("/api/users/login", methods=["POST"])
def login_user():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    password_hash = hash_password(password)
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT id, name, email, created_at FROM users WHERE email = ? AND password_hash = ?",
        (email, password_hash),
    )
    row = cursor.fetchone()
    connection.close()

    if not row:
        return jsonify({"error": "invalid credentials"}), 401

    return jsonify(row_to_dict(row))


@app.route("/api/teams", methods=["POST"])
def create_team():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    description = data.get("description", "")
    owner_id = data.get("owner_id")

    if not name or not owner_id:
        return jsonify({"error": "name and owner_id are required"}), 400

    created_at = datetime.datetime.utcnow().isoformat() + "Z"
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO teams (name, description, created_at, owner_id) VALUES (?, ?, ?, ?)",
        (name, description, created_at, owner_id),
    )
    team_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO team_members (team_id, user_id, joined_at, role) VALUES (?, ?, ?, ?)",
        (team_id, owner_id, created_at, "owner"),
    )
    connection.commit()
    connection.close()

    return jsonify({"id": team_id, "name": name, "description": description, "owner_id": owner_id, "created_at": created_at})


@app.route("/api/teams/<int:team_id>", methods=["GET"])
def get_team(team_id: int):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM teams WHERE id = ?", (team_id,))
    team = cursor.fetchone()
    if not team:
        connection.close()
        return jsonify({"error": "team not found"}), 404

    cursor.execute(
        "SELECT user_id, role, joined_at FROM team_members WHERE team_id = ?",
        (team_id,),
    )
    members = [dict(member) for member in cursor.fetchall()]
    connection.close()

    team_data = row_to_dict(team)
    team_data["members"] = members
    return jsonify(team_data)


@app.route("/api/teams/<int:team_id>/invite", methods=["POST"])
def invite_team_member(team_id: int):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    role = data.get("role", "member")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    joined_at = datetime.datetime.utcnow().isoformat() + "Z"
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO team_members (team_id, user_id, joined_at, role) VALUES (?, ?, ?, ?)",
            (team_id, user_id, joined_at, role),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.close()
        return jsonify({"error": "member already exists or invalid team/user"}), 409

    connection.close()
    return jsonify({"team_id": team_id, "user_id": user_id, "role": role, "joined_at": joined_at})


@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    owner_id = data.get("owner_id")
    category = data.get("category", "daily")
    priority = data.get("priority", 3)
    due_date = data.get("due_date")
    description = data.get("description", "")
    team_id = data.get("team_id")

    if not title or not owner_id:
        return jsonify({"error": "title and owner_id are required"}), 400

    created_at = datetime.datetime.utcnow().isoformat() + "Z"
    updated_at = created_at
    order_index = int(data.get("order_index", 0))

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO tasks (title, description, owner_id, team_id, category, priority, status, due_date, created_at, updated_at, order_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, description, owner_id, team_id, category, priority, "pending", due_date, created_at, updated_at, order_index),
    )
    task_id = cursor.lastrowid
    connection.commit()
    connection.close()

    return jsonify({"id": task_id, "title": title, "owner_id": owner_id, "team_id": team_id, "category": category, "priority": priority, "status": "pending", "due_date": due_date, "created_at": created_at, "updated_at": updated_at, "order_index": order_index})


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    owner_id = request.args.get("owner_id")
    team_id = request.args.get("team_id")
    status = request.args.get("status")
    category = request.args.get("category")

    conditions = []
    values = []
    if owner_id:
        conditions.append("owner_id = ?")
        values.append(owner_id)
    if team_id:
        conditions.append("team_id = ?")
        values.append(team_id)
    if status:
        conditions.append("status = ?")
        values.append(status)
    if category:
        conditions.append("category = ?")
        values.append(category)

    query = "SELECT * FROM tasks"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY order_index ASC, due_date IS NULL, due_date ASC"

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(query, values)
    tasks = [row_to_dict(row) for row in cursor.fetchall()]
    connection.close()

    return jsonify(tasks)


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id: int):
    data = request.get_json(silent=True) or {}
    fields = []
    values = []

    for key in ["title", "description", "category", "priority", "status", "due_date", "order_index", "team_id", "owner_id"]:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])

    if not fields:
        return jsonify({"error": "no fields to update"}), 400

    values.append(datetime.datetime.utcnow().isoformat() + "Z")
    values.append(task_id)

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        f"UPDATE tasks SET {', '.join(fields)}, updated_at = ? WHERE id = ?",
        values,
    )
    connection.commit()
    connection.close()

    return jsonify({"status": "updated", "task_id": task_id})


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id: int):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    connection.commit()
    connection.close()
    return jsonify({"status": "deleted", "task_id": task_id})


@app.route("/api/countdown", methods=["GET"])
def get_countdown():
    exam_date_str = get_config_value("exam_date")
    exam_date = parse_iso_date(exam_date_str)
    today = datetime.date.today()
    if exam_date:
        days_left = max((exam_date - today).days, 0)
    else:
        days_left = None

    return jsonify({
        "exam_date": exam_date_str,
        "days_left": days_left,
        "today": today.isoformat(),
    })


@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    owner_id = request.args.get("owner_id")
    team_id = request.args.get("team_id")
    today = datetime.date.today().isoformat()
    connection = get_db_connection()
    cursor = connection.cursor()

    filters = []
    values = []
    if owner_id:
        filters.append("owner_id = ?")
        values.append(owner_id)
    if team_id:
        filters.append("team_id = ?")
        values.append(team_id)

    base_where = " WHERE " + " AND ".join(filters) if filters else ""

    cursor.execute(f"SELECT COUNT(*) FROM tasks{base_where}", values)
    total_tasks = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT COUNT(*) FROM tasks{base_where} AND status = 'completed'" if filters else "SELECT COUNT(*) FROM tasks WHERE status = 'completed'",
        values,
    )
    completed = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT COUNT(*) FROM tasks{base_where} AND due_date = ? AND status = 'pending'" if filters else "SELECT COUNT(*) FROM tasks WHERE due_date = ? AND status = 'pending'",
        (*values, today) if filters else (today,),
    )
    due_today = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT COUNT(*) FROM tasks{base_where} AND due_date < ? AND status = 'pending'" if filters else "SELECT COUNT(*) FROM tasks WHERE due_date < ? AND status = 'pending'",
        (*values, today) if filters else (today,),
    )
    overdue = cursor.fetchone()[0]

    connection.close()
    return jsonify(
        {
            "total_tasks": total_tasks,
            "completed": completed,
            "due_today": due_today,
            "overdue": overdue,
        }
    )


if __name__ == "__main__":
    if not DB_PATH.exists():
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
