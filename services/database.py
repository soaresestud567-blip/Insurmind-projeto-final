import sqlite3
import json
from pathlib import Path


DB_PATH = Path("data/policies.db")


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    return conn


def init_db():
    with connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            structured_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)


def find_existing_policy(filename, raw_text):
    """
    Procura uma apólice já cadastrada com o mesmo nome de arquivo
    e exatamente o mesmo texto extraído.

    Retorna o ID caso exista.
    Retorna None caso não exista.
    """

    with connect() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM policies
            WHERE filename = ?
              AND raw_text = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (filename, raw_text)
        ).fetchone()

        if row:
            return row["id"]

        return None


def save_policy(filename, raw_text, structured):
    """
    Salva uma nova apólice.

    Se o mesmo arquivo, com o mesmo conteúdo extraído,
    já estiver cadastrado, retorna o ID existente em vez
    de criar uma duplicata.
    """

    existing_id = find_existing_policy(
        filename,
        raw_text
    )

    if existing_id is not None:
        return existing_id

    structured_json = json.dumps(
        structured,
        ensure_ascii=False
    )

    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO policies (
                filename,
                raw_text,
                structured_json
            )
            VALUES (?, ?, ?)
            """,
            (
                filename,
                raw_text,
                structured_json
            )
        )

        return cur.lastrowid


def list_policies():
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                filename,
                created_at
            FROM policies
            ORDER BY id DESC
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]


def get_policy(policy_id):
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM policies
            WHERE id = ?
            """,
            (policy_id,)
        ).fetchone()

        if not row:
            return None

        data = dict(row)

        try:
            data["structured"] = json.loads(
                data["structured_json"]
            )
        except json.JSONDecodeError:
            data["structured"] = {}

        return data