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
