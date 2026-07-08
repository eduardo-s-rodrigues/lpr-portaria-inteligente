from lpr_portaria.database import buscar_placa


def verificar_acesso(placa: str):
    registro = buscar_placa(placa.upper())

    if registro is None:
        return "NÃO CADASTRADO", None

    placa_db, nome, tipo, ativo = registro

    if not ativo:
        return "INATIVO", {
            "placa": placa_db,
            "nome": nome,
            "tipo": tipo,
        }

    return "AUTORIZADO", {
        "placa": placa_db,
        "nome": nome,
        "tipo": tipo,
    }
