import pytest

from po.numeros import formatar_brl, formatar_canonico, parse_valor


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
    assert formatar_canonico(40.0) == "40"
    assert formatar_canonico(30.75) == "30.75"
    assert formatar_canonico(5.4321) == "5.4321"
    assert formatar_canonico(0.00012345) == "0.00012345"     # qty de cripto sobrevive (8 casas por default)
    assert formatar_canonico(1.00050788) == "1.00050788"     # fator diário de CDI
    assert formatar_canonico(5.432191234, casas=4) == "5.4322"
    assert formatar_canonico(-0.0) == "0" and formatar_canonico(0.0) == "0"
    assert formatar_canonico(1234567.5) == "1234567.5"       # sem milhar
    assert formatar_canonico(2.5, casas=2) == "2.5"


def test_formatar_canonico_nunca_zera_nem_grava_nao_finito():
    with pytest.raises(ValueError, match="arredondado a zero"):
        formatar_canonico(0.00004, casas=4)
    for v in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="não finito"):
            formatar_canonico(v)


@pytest.mark.parametrize("v", [0.00004, 40.0, 30.75, 5.4321, 1234567.5, 1e12, -1.5, 0.0, 123456.789012])
def test_formatar_canonico_fecha_com_o_leitor_canonico(v):
    from po.csvs import NUMERO_CANONICO
    texto = formatar_canonico(v)
    assert NUMERO_CANONICO.match(texto)
    assert float(texto) == pytest.approx(v)
