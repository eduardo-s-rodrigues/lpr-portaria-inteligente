from lpr_portaria.validacao import placa_valida


def test_placa_mercosul_valida() -> None:
    assert placa_valida("ABC1D23") is True


def test_placa_antiga_valida() -> None:
    assert placa_valida("ABC1234") is True


def test_placa_com_formato_invalido() -> None:
    assert placa_valida("ABC123") is False


def test_texto_aleatorio_nao_e_placa() -> None:
    assert placa_valida("TESTE") is False


def test_placa_com_espacos_e_minusculas() -> None:
    assert placa_valida("  abc1d23  ") is True
