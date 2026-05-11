import os
import sqlite3
import subprocess
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder="templates")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_SCRIPT = os.path.join(BASE_DIR, "agent", "research_outreach_agent.py")
DB_FILE = os.path.join(BASE_DIR, "data", "outreach.db")
DRAFTS_FILE = os.path.join(BASE_DIR, "data", "drafts.csv")

agent_running = False
agent_log = []


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            title TEXT,
            institution TEXT,
            email TEXT,
            lab_url TEXT,
            research_focus TEXT,
            subject TEXT,
            email_drafted TEXT,
            status TEXT DEFAULT 'New',
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/leads")
def get_leads():
    conn = get_db()
    rows = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/leads/<int:lead_id>", methods=["PATCH"])
def update_lead(lead_id):
    data = request.get_json()
    allowed = {"subject", "email_drafted", "status", "name", "title", "institution", "email", "lab_url"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid fields"}), 400
    fields = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [lead_id]
    conn = get_db()
    conn.execute(f"UPDATE leads SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/leads/<int:lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    conn = get_db()
    conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/agent/run", methods=["POST"])
def run_agent():
    global agent_running, agent_log
    if agent_running:
        return jsonify({"error": "Agent already running"}), 409
    agent_running = True
    agent_log = []

    def run():
        global agent_running, agent_log
        try:
            env = os.environ.copy()
            env["DB_FILE"] = DB_FILE
            env["DRAFTS_FILE"] = DRAFTS_FILE
            proc = subprocess.Popen(
                ["python3", AGENT_SCRIPT],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            for line in proc.stdout:
                agent_log.append(line.rstrip())
            proc.wait()
        except Exception as e:
            agent_log.append(f"[ERROR] {e}")
        finally:
            agent_running = False

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/agent/status")
def agent_status():
    return jsonify({"running": agent_running, "log": agent_log[-80:]})


@app.route("/stats")
def stats():
    conn = get_db()
    rows = conn.execute("SELECT status, COUNT(*) as count FROM leads GROUP BY status").fetchall()
    conn.close()
    counts = {r["status"]: r["count"] for r in rows}
    return jsonify({"total": sum(counts.values()), "by_status": counts})


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
