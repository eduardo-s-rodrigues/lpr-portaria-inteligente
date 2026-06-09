import re

PADRAO_MERCOSUL = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")
PADRAO_ANTIGA = re.compile(r"^[A-Z]{3}[0-9]{4}$")


def placa_valida(txt: str) -> bool:
    txt = txt.strip().upper()
    return bool(PADRAO_MERCOSUL.match(txt) or PADRAO_ANTIGA.match(txt))
