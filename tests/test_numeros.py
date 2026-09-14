import pytest

from po.numeros import formatar_brl, formatar_canonico, formatar_decimal_brl, parse_valor


@pytest.mark.parametrize("texto,esperado", [
    ("1.234,56", 1234.56),      # pt-BR com milhar
    ("1.234", 1234.0),          # grupo de milhar pt-BR
    ("1,23", 1.23),             # decimal pt-BR
    ("1.23", 1.23),             # decimal US
    ("R$ 16.713,00", 16713.0),
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


@pytest.mark.parametrize("valor,esperado", [
    (0.03, "0,03"),                 # cripto: aqui formatar_brl coincide; na linha abaixo, não
    (0.00000001, "0,00000001"),     # 1 satoshi: formatar_brl daria "0,00" e `:g` daria "1e-08"
    (1500.0, "1.500"),              # sem zeros à direita, com milhar pt-BR
    (350000.5, "350.000,5"),        # `:g` daria "350000" — os centavos sumiam
    (1234567.89, "1.234.567,89"),   # `:g` daria "1.23457e+06"
    (0.0, "0"),
    (-0.5, "-0,5"),
])
def test_formatar_decimal_brl(valor, esperado):
    """Quantidade em mensagem para humano: pt-BR, sem zeros à direita, sem notação científica e
    sem truncar. É o formatador que faltava entre `formatar_brl` (dinheiro, 2 casas fixas) e
    `formatar_canonico` (exato, mas decimal com ponto)."""
    assert formatar_decimal_brl(valor) == esperado


def test_formatar_decimal_brl_nunca_escreve_ponto_como_decimal():
    """O ponto só pode aparecer como separador de MILHAR. Uma implementação que esquecesse o
    translate final passaria nos casos sem milhar e mentiria em todos os outros."""
    assert formatar_decimal_brl(1234.5) == "1.234,5"
    assert formatar_decimal_brl(0.25).count(",") == 1
    assert "." not in formatar_decimal_brl(0.25)


def test_sinal_antes_da_moeda():
    assert parse_valor("-R$ 5,00") == -5.0
    assert parse_valor("-$1.53") == -1.53
    assert parse_valor("R$ -5,00") == -5.0      # sinal depois da moeda continua valendo


def test_mais_com_milhar():
    assert parse_valor("+1.234") == 1234.0
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


def test_virgula_e_sempre_decimal_em_pt_br():
    """O defeito que esta fase não pode carregar: a heurística de milhar lia 0,030 como 30.
    Sob derivação, esse número entra no livro e vira a verdade de todo o resto, com o validador
    verde — porque a posicoes.csv que hoje denunciaria a divergência deixa de existir."""
    assert parse_valor("0,030") == pytest.approx(0.03)
    assert parse_valor("0,001") == pytest.approx(0.001)
    assert parse_valor("2,125") == pytest.approx(2.125)
    assert parse_valor("1,234") == pytest.approx(1.234)


def test_ponto_so_e_milhar_em_pt_br_quando_o_agrupamento_e_bem_formado():
    """1.500 é mil e quinhentos; 10750.00 é dez mil setecentos e cinquenta, porque .00 não é um
    grupo de milhar. A leniência é deliberada: export real mistura os dois o tempo todo.

    `0.030` é o gêmeo-do-ponto de `0,030 -> 30` que motivou esta task: o grupo de milhar não pode
    começar com zero, e é o `[1-9]` do _MILHAR que garante isso. Sem ele, três centésimos de um
    ETF viram trinta unidades."""
    assert parse_valor("1.500") == 1500.0
    assert parse_valor("1.234.567,89") == pytest.approx(1234567.89)
    assert parse_valor("10750.00") == 10750.0
    assert parse_valor("-$1.53") == pytest.approx(-1.53)
    assert parse_valor("0.030") == pytest.approx(0.03)
    assert parse_valor("0.001") == pytest.approx(0.001)


@pytest.mark.parametrize("texto,esperado", [
    ("1,234.56", 1234.56), ("1,234", 1234.0), ("US$ 1,000.50", 1000.5),
    ("+US$ 1,234.56", 1234.56), ("0.030", 0.03), ("1.234", 1.234),
    ("2,125", 2125.0), ("10750.00", 10750.0),
    ("0,030", 0.03),            # espelho en-US do zero à esquerda: grupo de milhar não começa em 0
])
def test_parse_en_us_valores_validos(texto, esperado):
    assert parse_valor(texto, formato="en-US") == pytest.approx(esperado)


@pytest.mark.parametrize("texto,formato", [
    ("1,234.56", "pt-BR"), ("1.234,56", "en-US"),
    ("1.000.000", "en-US"), ("1,2,3", "pt-BR"), ("1.2.3", "pt-BR"),
    # agrupamento mal formado À ESQUERDA do decimal: os cinco de cima morrem na guarda do `resto`
    # ou no regex final e nunca alcançam esse ramo. Sem ele, `1.23,45` vira 123,45 — o separador
    # sobrando some por concatenação em vez de ser recusado.
    ("1.23,45", "pt-BR"), ("12.34.567,89", "pt-BR"), ("1,23.45", "en-US"),
])
def test_numero_do_outro_formato_e_recusado(texto, formato):
    """Recusar é o ponto: o único caso None é a string genuinamente malformada PARA O FORMATO
    DECLARADO. Quem declarou errado vê o erro na primeira linha, não um número mil vezes maior."""
    assert parse_valor(texto, formato=formato) is None


def test_formato_desconhecido_levanta():
    with pytest.raises(ValueError, match="formato de número desconhecido"):
        parse_valor("1,00", formato="pt_BR")
