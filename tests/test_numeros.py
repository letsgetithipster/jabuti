import pytest

from po.numeros import formatar_brl, parse_valor


@pytest.mark.parametrize("texto,esperado", [
    ("1.234,56", 1234.56),      # pt-BR com milhar
    ("1,234.56", 1234.56),      # US com milhar
    ("1.234", 1234.0),          # grupo de milhar pt-BR
    ("1,234", 1234.0),          # grupo de milhar US
    ("1,23", 1.23),             # decimal pt-BR
    ("1.23", 1.23),             # decimal US
    ("R$ 16.713,00", 16713.0),
    ("US$ 1,000.50", 1000.5),
    ("42", 42.0),
    ("-3,5%", -3.5),
    ("0,00", 0.0),
    ("12.345.678,90", 12345678.9),
    ("-1.234,56", -1234.56),
    ("1 234,56", 1234.56),   # milhar com espaço
    ("+42", 42.0),
])
def test_parse_valores_validos(texto, esperado):
    assert parse_valor(texto) == pytest.approx(esperado)


@pytest.mark.parametrize("texto", [
    "", "abc", "n/d", "—", None,
    "nan", "inf", "Infinity", "1e5", "1_000", "5.", ".5", "R$1R$2", "12%34%", 42,
])
def test_parse_invalido_retorna_none(texto):
    assert parse_valor(texto) is None


@pytest.mark.parametrize("valor,esperado", [
    (12000.0, "12.000,00"),
    (0.0, "0,00"),
    (1234567.891, "1.234.567,89"),
    (-3.5, "-3,50"),
])
def test_formatar_brl(valor, esperado):
    assert formatar_brl(valor) == esperado


def test_sinal_antes_da_moeda():
    assert parse_valor("-R$ 5,00") == -5.0
    assert parse_valor("-$1.53") == -1.53
    assert parse_valor("+US$ 1,234.56") == 1234.56
    assert parse_valor("R$ -5,00") == -5.0      # sinal depois da moeda continua valendo


def test_mais_com_milhar():
    assert parse_valor("+1.234") == 1234.0
    assert parse_valor("+1,234") == 1234.0
    assert parse_valor("+12.345.678") == 12345678.0


def test_formatar_canonico():
    from po.numeros import formatar_canonico
    assert formatar_canonico(40.0) == "40"
    assert formatar_canonico(30.75) == "30.75"
    assert formatar_canonico(5.4321) == "5.4321"
    assert formatar_canonico(5.43219) == "5.4322"       # 4 casas por default
    assert formatar_canonico(-0.0) == "0"
    assert formatar_canonico(1234567.5) == "1234567.5"  # sem milhar
    assert formatar_canonico(2.5, casas=2) == "2.5"
