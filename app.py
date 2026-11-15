"""Fleet Management & Vehicle Maintenance Tracking Portal - Flask REST backend."""
import os
import sqlite3
from datetime import date, timedelta

from flask import Flask, jsonify, request, send_from_directory, g

DB_PATH = os.environ.get("DB_PATH", "fleet.db")
VEHICLE_STATUS = {"Active", "In Service", "Retired"}
MAINT_STATUS = {"Scheduled", "Completed"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS drivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    license_no TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reg_number TEXT UNIQUE NOT NULL,
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    year INTEGER,
    odometer INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Active',
    driver_id INTEGER REFERENCES drivers(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS maintenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    service_type TEXT NOT NULL,
    service_date TEXT NOT NULL,
    cost REAL DEFAULT 0,
    odometer INTEGER,
    status TEXT DEFAULT 'Scheduled',
    notes TEXT
);
"""


def create_app(db_path=None):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["DB_PATH"] = db_path or DB_PATH

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB_PATH"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db:
            db.close()

    with sqlite3.connect(app.config["DB_PATH"]) as con:
        con.executescript(SCHEMA)

    def rows(cur):
        return [dict(r) for r in cur.fetchall()]

    def bad(msg, code=400):
        return jsonify(error=msg), code

    def need(data, *fields):
        missing = [f for f in fields if not str(data.get(f, "")).strip()]
        return f"Missing required field(s): {', '.join(missing)}" if missing else None

    # ---------- pages / health ----------
    @app.get("/")
    def index():
        return send_from_directory("static", "index.html")

    @app.get("/api/health")
    def health():
        get_db().execute("SELECT 1")
        return jsonify(status="ok")

    # ---------- drivers ----------
    @app.get("/api/drivers")
    def list_drivers():
        return jsonify(rows(get_db().execute("SELECT * FROM drivers ORDER BY name")))

    @app.post("/api/drivers")
    def add_driver():
        d = request.get_json(silent=True) or {}
        if err := need(d, "name", "license_no"):
            return bad(err)
        try:
            db = get_db()
            cur = db.execute("INSERT INTO drivers(name,phone,license_no) VALUES(?,?,?)",
                             (d["name"].strip(), d.get("phone"), d["license_no"].strip()))
            db.commit()
        except sqlite3.IntegrityError:
            return bad("License number already exists", 409)
        return jsonify(id=cur.lastrowid), 201

    @app.delete("/api/drivers/<int:i>")
    def del_driver(i):
        db = get_db()
        db.execute("DELETE FROM drivers WHERE id=?", (i,))
        db.commit()
        return "", 204

    # ---------- vehicles ----------
    VEH_SQL = ("SELECT v.*, d.name AS driver_name FROM vehicles v "
               "LEFT JOIN drivers d ON d.id = v.driver_id")

    @app.get("/api/vehicles")
    def list_vehicles():
        q = request.args.get("q", "").strip()
        sql, args = VEH_SQL, []
        if q:
            sql += " WHERE v.reg_number LIKE ? OR v.make LIKE ? OR v.model LIKE ?"
            args = [f"%{q}%"] * 3
        return jsonify(rows(get_db().execute(sql + " ORDER BY v.reg_number", args)))

    @app.get("/api/vehicles/<int:i>")
    def get_vehicle(i):
        r = get_db().execute(VEH_SQL + " WHERE v.id=?", (i,)).fetchone()
        return jsonify(dict(r)) if r else bad("Vehicle not found", 404)

    def vehicle_values(d):
        status = d.get("status", "Active")
        if status not in VEHICLE_STATUS:
            return None, f"status must be one of {sorted(VEHICLE_STATUS)}"
        try:
            year = int(d["year"]) if d.get("year") not in (None, "") else None
            odo = int(d.get("odometer") or 0)
        except (TypeError, ValueError):
            return None, "year and odometer must be numbers"
        if odo < 0:
            return None, "odometer cannot be negative"
        driver = d.get("driver_id") or None
        return (d["reg_number"].strip().upper(), d["make"].strip(), d["model"].strip(),
                year, odo, status, driver), None

    @app.post("/api/vehicles")
    def add_vehicle():
        d = request.get_json(silent=True) or {}
        if err := need(d, "reg_number", "make", "model"):
            return bad(err)
        vals, err = vehicle_values(d)
        if err:
            return bad(err)
        try:
            db = get_db()
            cur = db.execute("INSERT INTO vehicles(reg_number,make,model,year,odometer,status,driver_id)"
                             " VALUES(?,?,?,?,?,?,?)", vals)
            db.commit()
        except sqlite3.IntegrityError as e:
            return bad("Registration number already exists" if "UNIQUE" in str(e)
                       else "Invalid driver", 409)
        return jsonify(id=cur.lastrowid), 201

    @app.put("/api/vehicles/<int:i>")
    def update_vehicle(i):
        d = request.get_json(silent=True) or {}
        if err := need(d, "reg_number", "make", "model"):
            return bad(err)
        vals, err = vehicle_values(d)
        if err:
            return bad(err)
        try:
            db = get_db()
            cur = db.execute("UPDATE vehicles SET reg_number=?,make=?,model=?,year=?,odometer=?,"
                             "status=?,driver_id=? WHERE id=?", (*vals, i))
            db.commit()
        except sqlite3.IntegrityError:
            return bad("Registration number already exists", 409)
        return jsonify(updated=cur.rowcount) if cur.rowcount else bad("Vehicle not found", 404)

    @app.delete("/api/vehicles/<int:i>")
    def del_vehicle(i):
        db = get_db()
        db.execute("DELETE FROM vehicles WHERE id=?", (i,))
        db.commit()
        return "", 204

    # ---------- maintenance ----------
    MAINT_SQL = ("SELECT m.*, v.reg_number FROM maintenance m "
                 "JOIN vehicles v ON v.id = m.vehicle_id")

    @app.get("/api/maintenance")
    def list_maintenance():
        sql, args = MAINT_SQL, []
        if vid := request.args.get("vehicle_id"):
            sql += " WHERE m.vehicle_id=?"
            args.append(vid)
        return jsonify(rows(get_db().execute(sql + " ORDER BY m.service_date DESC", args)))

    @app.post("/api/maintenance")
    def add_maintenance():
        d = request.get_json(silent=True) or {}
        if err := need(d, "vehicle_id", "service_type", "service_date"):
            return bad(err)
        try:
            date.fromisoformat(d["service_date"])
            cost = float(d.get("cost") or 0)
        except ValueError:
            return bad("service_date must be YYYY-MM-DD and cost a number")
        if cost < 0:
            return bad("cost cannot be negative")
        status = d.get("status", "Scheduled")
        if status not in MAINT_STATUS:
            return bad(f"status must be one of {sorted(MAINT_STATUS)}")
        try:
            db = get_db()
            cur = db.execute("INSERT INTO maintenance(vehicle_id,service_type,service_date,cost,odometer,status,notes)"
                             " VALUES(?,?,?,?,?,?,?)",
                             (d["vehicle_id"], d["service_type"].strip(), d["service_date"], cost,
                              d.get("odometer") or None, status, d.get("notes")))
            db.commit()
        except sqlite3.IntegrityError:
            return bad("Vehicle not found", 404)
        return jsonify(id=cur.lastrowid), 201

    @app.patch("/api/maintenance/<int:i>/complete")
    def complete_maintenance(i):
        db = get_db()
        cur = db.execute("UPDATE maintenance SET status='Completed' WHERE id=?", (i,))
        db.commit()
        return jsonify(updated=cur.rowcount) if cur.rowcount else bad("Record not found", 404)

    @app.delete("/api/maintenance/<int:i>")
    def del_maintenance(i):
        db = get_db()
        db.execute("DELETE FROM maintenance WHERE id=?", (i,))
        db.commit()
        return "", 204

    # ---------- dashboard ----------
    @app.get("/api/dashboard")
    def dashboard():
        db, today = get_db(), date.today()
        soon = (today + timedelta(days=14)).isoformat()
        one = lambda sql, *a: db.execute(sql, a).fetchone()[0]
        return jsonify(
            total_vehicles=one("SELECT COUNT(*) FROM vehicles"),
            active=one("SELECT COUNT(*) FROM vehicles WHERE status='Active'"),
            in_service=one("SELECT COUNT(*) FROM vehicles WHERE status='In Service'"),
            overdue=one("SELECT COUNT(*) FROM maintenance WHERE status='Scheduled' AND service_date<?",
                        today.isoformat()),
            total_cost=one("SELECT COALESCE(SUM(cost),0) FROM maintenance WHERE status='Completed'"),
            upcoming=rows(db.execute(
                MAINT_SQL + " WHERE m.status='Scheduled' AND m.service_date<=? ORDER BY m.service_date",
                (soon,))),
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
