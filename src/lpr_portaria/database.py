import sqlite3


def conectar():
    return sqlite3.connect("placas.db")


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
                confianca REAL NOT NULL
            )
            """)


def inserir_placa(placa, nome, tipo):
    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO placas(placa, nome, tipo)
            Values (?, ?, ?)
            """,
            (placa, nome, tipo),
        )


def buscar_placa(placa):
    with conectar() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM placas
            WHERE placa = ?
            """,
            (placa,),
        )
        return cursor.fetchone()


def inserir_evento(placa: str, confianca: float):
    with conectar() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO eventos
            (data_hora, placa, confianca)
            VALUES (datetime('now'), ?, ?)""",
            (placa, confianca),
        )
