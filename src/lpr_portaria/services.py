from lpr_portaria.database import (
    criar_tabelas,
    inserir_cadastro,
    inserir_telefone,
    inserir_veiculo,
    listar_eventos,
)


def cadastrar_acesso_completo(
    nome: str,
    email: str | None,
    tipo_cadastro: str,
    telefone: str | None,
    placa: str,
    marca: str | None,
    modelo: str | None,
    cor: str | None,
    tipo_veiculo: str,
):
    criar_tabelas()

    id_cadastro = inserir_cadastro(nome=nome, email=email, tipo_cadastro=tipo_cadastro)

    if telefone:
        inserir_telefone(
            id_cadastro=id_cadastro,
            tipo_telefone="celular",
            numero=telefone,
        )

    id_veiculo = inserir_veiculo(
        id_cadastro=id_cadastro,
        placa=placa,
        marca=marca,
        modelo=modelo,
        cor=cor,
        tipo_veiculo=tipo_veiculo,
    )

    return {
        "id_cadastro": id_cadastro,
        "id_veiculo": id_veiculo,
        "nome": nome,
        "placa": placa.upper().strip(),
        "tipo_cadastro": tipo_cadastro,
        "tipo_veiculo": tipo_veiculo,
    }


def buscar_ultimos_eventos(limite: int = 10):
    criar_tabelas()
    return listar_eventos(limite=limite)
