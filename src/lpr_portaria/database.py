import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "placas.db"


def conectar():
    return sqlite3.connect(DB_PATH)


def criar_tabelas():
    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS placas (
                placa TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                tipo TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1
            )
            """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TEXT NOT NULL,
                placa TEXT NOT NULL,
                confianca REAL NOT NULL,
                status TEXT,
                nome TEXT,
                tipo TEXT
            )
            """)


def garantir_colunas_eventos():
    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(eventos)")
        colunas = [coluna[1] for coluna in cursor.fetchall()]

        if "status" not in colunas:
            cursor.execute("ALTER TABLE eventos ADD COLUMN status TEXT")

        if "nome" not in colunas:
            cursor.execute("ALTER TABLE eventos ADD COLUMN nome TEXT")

        if "tipo" not in colunas:
            cursor.execute("ALTER TABLE eventos ADD COLUMN tipo TEXT")


def inserir_placa(placa: str, nome: str, tipo: str):
    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO placas
            (placa, nome, tipo, ativo)
            VALUES (?, ?, ?, 1)
            """,
            (placa.upper(), nome, tipo),
        )


def buscar_placa(placa: str):
    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT placa, nome, tipo, ativo
            FROM placas
            WHERE placa = ?
            """,
            (placa.upper(),),
        )

        return cursor.fetchone()


def inserir_evento(
    placa: str,
    confianca: float,
    status: str,
    nome: str | None = None,
    tipo: str | None = None,
):
    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO eventos
            (data_hora, placa, confianca, status, nome, tipo)
            VALUES (datetime('now', 'localtime'), ?, ?, ?, ?, ?)
            """,
            (placa.upper(), confianca, status, nome, tipo),
        )
