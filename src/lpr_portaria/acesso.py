from lpr_portaria.database import buscar_veiculo_por_placa


def verificar_acesso(placa: str):
    dados = buscar_veiculo_por_placa(placa)

    if dados is None:
        return "nao_cadastrado", None

    cadastro_ativo = dados["cadastro_ativo"]
    veiculo_ativo = dados["veiculo_ativo"]

    dados_acesso = {
        "id_cadastro": dados["id_cadastro"],
        "id_veiculo": dados["id_veiculo"],
        "placa": dados["placa"],
        "nome": dados["nome"],
        "tipo": dados["tipo_cadastro"],
        "marca": dados["marca"],
        "modelo": dados["modelo"],
        "cor": dados["cor"],
        "tipo_veiculo": dados["tipo_veiculo"],
    }

    if not cadastro_ativo or not veiculo_ativo:
        return "inativo", dados_acesso

    return "autorizado", dados_acesso
