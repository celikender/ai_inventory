import sqlite3
from pathlib import Path
from datetime import datetime
import cv2

DB_PATH = Path("storage") / "inventory.db"


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    con.execute("PRAGMA foreign_keys = ON;")
    con.execute("PRAGMA journal_mode = WAL;")
    con.execute("PRAGMA synchronous = NORMAL;")
    con.execute("PRAGMA busy_timeout = 5000;")
    return con



def init_db():
    with _conn() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        con.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_bins_shelf_code
            ON bins(shelf_id, bin_code)
        """)


        con.execute("""
        CREATE TABLE IF NOT EXISTS shelves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS bins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shelf_id INTEGER NOT NULL,
            bin_code TEXT NOT NULL,
            label TEXT,
            product_name TEXT,
            description TEXT,
            qty INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(shelf_id) REFERENCES shelves(id)
        )
        """)
        
        con.execute("""
           CREATE UNIQUE INDEX IF NOT EXISTS idx_bins_shelf_code
           ON bins(shelf_id, bin_code)
        """)


        con.commit()


def create_project(name: str):
    created_at = datetime.utcnow().isoformat()
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO projects(name, created_at) VALUES(?, ?)",
            (name, created_at),
        )
        con.commit()
        return {"id": cur.lastrowid, "name": name, "created_at": created_at}


def list_projects():
    with _conn() as con:
        rows = con.execute(
            "SELECT id, name, created_at FROM projects ORDER BY id DESC"
        ).fetchall()
    return [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]


def create_shelf(project_id: int, name: str):
    created_at = datetime.utcnow().isoformat()
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO shelves(project_id, name, created_at) VALUES(?, ?, ?)",
            (project_id, name, created_at),
        )
        con.commit()
        return {"id": cur.lastrowid, "project_id": project_id, "name": name, "created_at": created_at}


def list_shelves(project_id: int):
    with _conn() as con:
        rows = con.execute(
            "SELECT id, project_id, name, created_at FROM shelves WHERE project_id=? ORDER BY id DESC",
            (project_id,),
        ).fetchall()
    return [{"id": r[0], "project_id": r[1], "name": r[2], "created_at": r[3]} for r in rows]


def create_bin(
    shelf_id: int,
    bin_code: str,
    label: str | None,
    product_name: str | None,
    description: str | None,
    qty: int | None,
):
    created_at = datetime.utcnow().isoformat()
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO bins(shelf_id, bin_code, label, product_name, description, qty, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
            (shelf_id, bin_code, label, product_name, description, qty, created_at),
        )
        con.commit()
        return {
            "id": cur.lastrowid,
            "shelf_id": shelf_id,
            "bin_code": bin_code,
            "label": label,
            "product_name": product_name,
            "description": description,
            "qty": qty,
            "created_at": created_at,
        }


def list_bins(shelf_id: int):
    with _conn() as con:
        rows = con.execute(
            "SELECT id, shelf_id, bin_code, label, product_name, description, qty, created_at FROM bins WHERE shelf_id=? ORDER BY id DESC",
            (shelf_id,),
        ).fetchall()
    return [
        {
            "id": r[0],
            "shelf_id": r[1],
            "bin_code": r[2],
            "label": r[3],
            "product_name": r[4],
            "description": r[5],
            "qty": r[6],
            "created_at": r[7],
        }
        for r in rows
    ]


def save_shelf_photo(project_id: int, shelf_id: int, frame):
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    folder = Path("storage") / "photos" / str(project_id) / str(shelf_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{ts}.jpg"
    cv2.imwrite(str(path), frame)
    return str(path)


def delete_bins_for_shelf(shelf_id: int):
    with _conn() as con:
        con.execute("DELETE FROM bins WHERE shelf_id=?", (shelf_id,))
        con.commit()


def create_bins_bulk(shelf_id: int, bins: list[dict]):
    created = []
    for b in bins:
        bin_code = (b.get("bin_code") or "").strip()
        if not bin_code:
            continue
        created.append(
            create_bin(
                shelf_id,
                bin_code,
                b.get("label"),
                b.get("product_name"),
                b.get("description"),
                b.get("qty"),
            )
        )
    return created


def replace_bins_for_shelf(shelf_id: int, bins: list[dict]):
    created_at = datetime.utcnow().isoformat()

    rows = []
    seen = set()

    for b in bins:
        bin_code = (b.get("bin_code") or "").strip()
        if not bin_code:
            continue
        if bin_code in seen:
            continue
        seen.add(bin_code)

        rows.append(
            (
                shelf_id,
                bin_code,
                b.get("label"),
                b.get("product_name"),
                b.get("description"),
                b.get("qty"),
                created_at,
            )
        )

    with _conn() as con:
        con.execute("DELETE FROM bins WHERE shelf_id=?", (shelf_id,))
        con.executemany(
            "INSERT INTO bins(shelf_id, bin_code, label, product_name, description, qty, created_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        con.commit()

    return list_bins(shelf_id)


def update_bin_qty_by_code(shelf_id: int, bin_code: str, qty: int | None):
    with _conn() as con:
        con.execute(
            "UPDATE bins SET qty=? WHERE shelf_id=? AND bin_code=?",
            (qty, shelf_id, bin_code),
        )
        con.commit()
    
def update_bin_by_id(bin_id: int, patch: dict):
    allowed = ["label", "product_name", "description", "qty"]
    if "sku" in patch:
        allowed.append("sku")

    fields = []
    vals = []

    for k in allowed:
        if k in patch:
            fields.append(f"{k}=?")
            vals.append(patch[k])

    if not fields:
        return None

    vals.append(bin_id)

    with _conn() as con:
        con.execute(f"UPDATE bins SET {', '.join(fields)} WHERE id=?", vals)
        con.commit()

        # return updated row
        # include sku if your table has it
        row = con.execute(
            "SELECT id, shelf_id, bin_code, label, product_name, description, qty, created_at FROM bins WHERE id=?",
            (bin_id,),
        ).fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "shelf_id": row[1],
        "bin_code": row[2],
        "label": row[3],
        "product_name": row[4],
        "description": row[5],
        "qty": row[6],
        "created_at": row[7],
    }

def project_exists(project_id: int) -> bool:
    with _conn() as con:
        row = con.execute("SELECT 1 FROM projects WHERE id=? LIMIT 1", (project_id,)).fetchone()
    return row is not None
