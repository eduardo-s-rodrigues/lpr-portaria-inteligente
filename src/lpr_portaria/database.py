import sqlite3
from pathlib import Path

from lpr_portaria.opcoes import (
    STATUS_EVENTO,
    TIPOS_CADASTRO,
    TIPOS_TELEFONE,
    TIPOS_VEICULO,
)

DB_PATH = Path(__file__).resolve().parents[2] / "placas.db"


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def normalizar_valor(valor: str) -> str:
    valor = valor.strip().lower()

    tabela = str.maketrans(
        "áàâãéêíóôõúç",
        "aaaaeeiooouc",
    )

    valor = valor.translate(tabela)
    valor = valor.replace(" ", "_")
    valor = valor.replace("-", "_")

    return valor


def validar_opcao(valor: str, opcoes: tuple[str, ...], campo: str) -> str:
    valor_normalizado = normalizar_valor(valor)

    if valor_normalizado not in opcoes:
        raise ValueError(
            f"Valor inválido para {campo}: {valor}. " f"Opções permitidas: {', '.join(opcoes)}"
        )

    return valor_normalizado


def valores_sql(opcoes: tuple[str, ...]) -> str:
    return ", ".join(f"'{opcao}'" for opcao in opcoes)


def criar_tabelas():
    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS cadastros (
                id_cadastro INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                documento TEXT,
                email TEXT,
                tipo_cadastro TEXT NOT NULL CHECK (
                    tipo_cadastro IN ({valores_sql(TIPOS_CADASTRO)})
                ),
                ativo INTEGER NOT NULL DEFAULT 1,
                bloco TEXT,
                apartamento TEXT,
                setor TEXT,
                observacao TEXT
            )
            """)

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS telefones (
                id_telefone INTEGER PRIMARY KEY AUTOINCREMENT,
                id_cadastro INTEGER NOT NULL,
                tipo_telefone TEXT NOT NULL CHECK (
                    tipo_telefone IN ({valores_sql(TIPOS_TELEFONE)})
                ),
                numero TEXT NOT NULL,

                FOREIGN KEY (id_cadastro) REFERENCES cadastros(id_cadastro)
            )
            """)

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS veiculos (
                id_veiculo INTEGER PRIMARY KEY AUTOINCREMENT,
                id_cadastro INTEGER NOT NULL,
                placa TEXT NOT NULL UNIQUE,
                marca TEXT,
                modelo TEXT,
                cor TEXT,
                tipo_veiculo TEXT NOT NULL CHECK (
                    tipo_veiculo IN ({valores_sql(TIPOS_VEICULO)})
                ),
                ativo INTEGER NOT NULL DEFAULT 1,
                observacao TEXT,

                FOREIGN KEY (id_cadastro) REFERENCES cadastros(id_cadastro)
            )
            """)

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS eventos (
                id_evento INTEGER PRIMARY KEY AUTOINCREMENT,
                id_veiculo INTEGER,
                placa_lida TEXT NOT NULL,
                data_hora TEXT NOT NULL,
                confianca REAL NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ({valores_sql(STATUS_EVENTO)})
                ),
                nome TEXT,
                tipo_cadastro TEXT,

                FOREIGN KEY (id_veiculo) REFERENCES veiculos(id_veiculo)
            )
            """)


def garantir_colunas_eventos():
    """
    Mantida para o main.py atual continuar funcionando.

    No modelo novo, a tabela eventos já nasce completa.
    Então esta função apenas garante que as tabelas existam.
    """
    criar_tabelas()


def inserir_cadastro(
    nome: str,
    documento: str | None = None,
    email: str | None = None,
    tipo_cadastro: str = "morador",
    ativo: int = 1,
    bloco: str | None = None,
    apartamento: str | None = None,
    setor: str | None = None,
    observacao: str | None = None,
):
    tipo_cadastro = validar_opcao(
        tipo_cadastro,
        TIPOS_CADASTRO,
        "tipo_cadastro",
    )

    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO cadastros
            (
                nome,
                documento,
                email,
                tipo_cadastro,
                ativo,
                bloco,
                apartamento,
                setor,
                observacao
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nome,
                documento,
                email,
                tipo_cadastro,
                ativo,
                bloco,
                apartamento,
                setor,
                observacao,
            ),
        )

        return cursor.lastrowid


def inserir_telefone(
    id_cadastro: int,
    tipo_telefone: str,
    numero: str,
):
    tipo_telefone = validar_opcao(
        tipo_telefone,
        TIPOS_TELEFONE,
        "tipo_telefone",
    )

    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO telefones
            (id_cadastro, tipo_telefone, numero)
            VALUES (?, ?, ?)
            """,
            (id_cadastro, tipo_telefone, numero),
        )

        return cursor.lastrowid


def inserir_veiculo(
    id_cadastro: int,
    placa: str,
    marca: str | None = None,
    modelo: str | None = None,
    cor: str | None = None,
    tipo_veiculo: str = "carro",
    ativo: int = 1,
    observacao: str | None = None,
):
    tipo_veiculo = validar_opcao(
        tipo_veiculo,
        TIPOS_VEICULO,
        "tipo_veiculo",
    )

    placa = placa.upper().strip()

    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO veiculos
            (
                id_cadastro,
                placa,
                marca,
                modelo,
                cor,
                tipo_veiculo,
                ativo,
                observacao
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(placa) DO UPDATE SET
                id_cadastro = excluded.id_cadastro,
                marca = excluded.marca,
                modelo = excluded.modelo,
                cor = excluded.cor,
                tipo_veiculo = excluded.tipo_veiculo,
                ativo = excluded.ativo,
                observacao = excluded.observacao
            """,
            (
                id_cadastro,
                placa,
                marca,
                modelo,
                cor,
                tipo_veiculo,
                ativo,
                observacao,
            ),
        )

        cursor.execute(
            """
            SELECT id_veiculo
            FROM veiculos
            WHERE placa = ?
            """,
            (placa,),
        )

        return cursor.fetchone()["id_veiculo"]


def buscar_veiculo_por_placa(placa: str):
    placa = placa.upper().strip()

    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                v.id_veiculo,
                v.placa,
                v.marca,
                v.modelo,
                v.cor,
                v.tipo_veiculo,
                v.ativo AS veiculo_ativo,
                v.observacao AS observacao_veiculo,
                c.id_cadastro,
                c.nome,
                c.documento,
                c.email,
                c.tipo_cadastro,
                c.ativo AS cadastro_ativo,
                c.bloco,
                c.apartamento,
                c.setor,
                c.observacao AS observacao_cadastro
            FROM veiculos v
            JOIN cadastros c ON v.id_cadastro = c.id_cadastro
            WHERE v.placa = ?
            """,
            (placa,),
        )

        resultado = cursor.fetchone()

        if resultado is None:
            return None

        return dict(resultado)


def buscar_placa(placa: str):
    """
    Compatibilidade com o acesso.py atual.

    O acesso.py espera:
    (placa, nome, tipo, ativo)

    Por baixo, agora buscamos em veiculos + cadastros.
    """
    dados = buscar_veiculo_por_placa(placa)

    if dados is None:
        return None

    ativo = 1 if dados["cadastro_ativo"] and dados["veiculo_ativo"] else 0

    return (
        dados["placa"],
        dados["nome"],
        dados["tipo_cadastro"],
        ativo,
    )


def inserir_placa(placa: str, nome: str, tipo: str):
    """
    Compatibilidade com comandos antigos.

    Antes cadastrávamos direto na tabela placas.
    Agora criamos um cadastro e ligamos um veículo a ele.
    """
    dados = buscar_veiculo_por_placa(placa)

    if dados:
        return inserir_veiculo(
            dados["id_cadastro"],
            placa,
            tipo_veiculo="carro",
            ativo=1,
        )

    id_cadastro = inserir_cadastro(
        nome=nome,
        tipo_cadastro=tipo,
    )

    return inserir_veiculo(
        id_cadastro,
        placa,
        tipo_veiculo="carro",
        ativo=1,
    )


def normalizar_status(status: str) -> str:
    return validar_opcao(
        status,
        STATUS_EVENTO,
        "status",
    )


def inserir_evento(
    placa: str,
    confianca: float,
    status: str,
    nome: str | None = None,
    tipo: str | None = None,
):
    placa = placa.upper().strip()
    status = normalizar_status(status)

    dados = buscar_veiculo_por_placa(placa)

    id_veiculo = None

    if dados:
        id_veiculo = dados["id_veiculo"]

        if nome is None:
            nome = dados["nome"]

        if tipo is None:
            tipo = dados["tipo_cadastro"]

    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO eventos
            (
                id_veiculo,
                placa_lida,
                data_hora,
                confianca,
                status,
                nome,
                tipo_cadastro
            )
            VALUES (?, ?, datetime('now', 'localtime'), ?, ?, ?, ?)
            """,
            (
                id_veiculo,
                placa,
                confianca,
                status,
                nome,
                tipo,
            ),
        )


def listar_veiculos(limite: int = 20):
    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """ 
            SELECT
                v.id_veiculo,
                v.placa,
                v.marca,
                v.modelo,
                v.cor,
                v.tipo_veiculo,
                v. ativo AS veiculo_ativo,
                c.nome,
                c.tipo_cadastro,
                c.ativo AS cadastro_ativo
            FROM veiculos v
            JOIN cadastros c ON v.id_veiculo = c.id_cadastro
            ORDER BY v.id_veiculo DESC
            LIMIT ?
            """,
            (limite,),
        )
    return [dict(linha) for linha in cursor.fetchall()]


def listar_eventos(limite: int = 10):
    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id_evento,
                data_hora,
                placa_lida,
                confianca,
                status,
                nome,
                tipo_cadastro
            FROM eventos
            ORDER BY id_evento DESC
            LIMIT ?
            """,
            (limite,),
        )

        return [dict(linha) for linha in cursor.fetchall()]
