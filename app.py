from datetime import datetime
import sqlite3
from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)
DB_NAME = "shopping_stock.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                action TEXT CHECK(action IN ('RESTOCK', 'USE', 'INITIAL')),
                quantity REAL NOT NULL,
                unit TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        # Seed baseline inventory if database is empty
        count = conn.execute("SELECT COUNT(*) FROM inventory_ledger").fetchone()[0]
        if count == 0:
            baseline = [
                ("Bar Soap (2kg)", "INITIAL", 3.25, "bars"),
                ("Classic Detergent (1kg)", "INITIAL", 2.0, "packs"),
                ("Utensils Sponge", "INITIAL", 4.0, "pieces"),
                ("Steel Sufuria Scrubber", "INITIAL", 2.0, "pieces"),
                ("Sawa Bathing Soap", "INITIAL", 4.0, "bars"),
                ("Pepsodent Toothpaste (150g)", "INITIAL", 2.0, "tubes"),
            ]
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.executemany(
                """
                INSERT INTO inventory_ledger (item_name, action, quantity, unit, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(i, a, q, u, now) for i, a, q, u in baseline],
            )
            conn.commit()


@app.route("/")
def index():
    with get_db() as conn:
        query = """
            SELECT 
                item_name,
                MAX(unit) AS unit,
                COALESCE(SUM(CASE WHEN action IN ('INITIAL', 'RESTOCK') THEN quantity ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN action = 'USE' THEN quantity ELSE 0 END), 0) AS balance
            FROM inventory_ledger
            GROUP BY item_name
            ORDER BY item_name ASC
        """
        stock = conn.execute(query).fetchall()

        history = conn.execute(
            """
            SELECT item_name, action, quantity, unit, timestamp 
            FROM inventory_ledger 
            ORDER BY id DESC LIMIT 10
            """
        ).fetchall()

    return render_template("index.html", stock=stock, history=history)


@app.route("/log", methods=["POST"])
def log_action():
    item_name = request.form.get("item_name", "").strip()
    action = request.form.get("action", "").strip().upper()
    quantity = float(request.form.get("quantity", 1.0))
    unit = request.form.get("unit", "").strip()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Map form actions if labeled differently (e.g., PURCHASE -> RESTOCK)
    if action == "PURCHASE":
        action = "RESTOCK"

    if item_name and action in ("RESTOCK", "USE"):
        with get_db() as conn:
            # If unit was left empty, fetch existing unit for this item
            if not unit:
                existing_unit = conn.execute(
                    "SELECT unit FROM inventory_ledger WHERE item_name = ? AND unit IS NOT NULL AND unit != '' LIMIT 1",
                    (item_name,),
                ).fetchone()
                if existing_unit:
                    unit = existing_unit["unit"]

            conn.execute(
                """
                INSERT INTO inventory_ledger (item_name, action, quantity, unit, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (item_name, action, quantity, unit, now),
            )
            conn.commit()

    return redirect(url_for("index"))


@app.route("/add_item", methods=["POST"])
def add_item():
    item_name = request.form.get("item_name", "").strip()
    unit = request.form.get("unit", "").strip()
    initial_qty = float(request.form.get("initial_qty", 0.0))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if item_name:
        with get_db() as conn:
            # Record initial balance entry in the ledger
            conn.execute(
                """
                INSERT INTO inventory_ledger (item_name, action, quantity, unit, timestamp)
                VALUES (?, 'INITIAL', ?, ?, ?)
                """,
                (item_name, initial_qty, unit, now),
            )
            conn.commit()

    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)