import datetime

from po.ingestao.conciliacao import conciliar
from po.ingestao.engine import executar
from po.ingestao.leitores import Tabela
from test_ingestao_mapeamento import MAPA_OK

CAB = ["Data", "Histórico", "Valor", "Saldo"]


def _tab(linhas, cab=CAB):
    return Tabela(cab, linhas, 1)


def test_classifica_extrai_grupo_e_converte():
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "99,00", "1.300,00"],
              ["19/08/2026", "TED SAIDA", "-500,00", "1.201,00"]])
    r = executar(MAPA_OK, t)
    assert r.erros == [] and r.linhas_lidas == 2 and r.classificadas == 1
    p = r.registros["proventos"][0]
    assert (p["data"], p["ticker"], p["tipo"], p["valor_bruto"], p["conta"], p["moeda"], p["_linha"]) == \
        ("2026-08-20", "HGLG11", "rendimento", 99.0, "corretora-br", "BRL", 2)
    assert p["cnpj"] == ""                       # opcional não mapeado fica vazio
    assert r.ignoradas == [(3, "caixa")]


def test_linha_sem_regra_e_erro_nunca_descarte():
    t = _tab([["20/08/2026", "COISA NOVA XPTO", "1,00", "1,00"]])
    r = executar(MAPA_OK, t)
    assert any("linha 2" in e and "não classificada" in e and "COISA NOVA" in e for e in r.erros)
    assert r.classificadas == 0


def test_numero_ilegivel_e_data_ilegivel_sao_erros():
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "abc", "1,00"],
              ["ontem", "RENDIMENTO HGLG11", "1,00", "1,00"]])
    r = executar(MAPA_OK, t)
    assert any("linha 2" in e and "valor_bruto não numérico" in e for e in r.erros)
    assert any("linha 3" in e and "data ilegível" in e for e in r.erros)


def test_coluna_ausente_no_documento():
    t = _tab([["20/08/2026", "x"]], cab=["Data", "Lançamento"])
    r = executar(MAPA_OK, t)
    assert any("'Histórico'" in e and "não encontrada" in e for e in r.erros)


def test_conta_da_cli_sobrepoe_e_celula_datetime_passa():
    t = _tab([[datetime.datetime(2026, 8, 20), "RENDIMENTO HGLG11", 99.0, 1300.0]])
    r = executar(MAPA_OK, t, conta="outra")
    assert r.erros == [] and r.registros["proventos"][0]["conta"] == "outra"
    assert r.registros["proventos"][0]["data"] == "2026-08-20"


def test_template_com_padrao_e_ajuste_por_chave():
    mapa = dict(MAPA_OK, colunas={"data": "Date", "acao": "Action", "ticker": "Symbol", "qty": "Quantity",
                                  "preco": "Price", "taxa": "Fees", "valor": "Amount"},
                datas={"formatos": ["%m/%d/%Y"], "extrair": r"^(\S+)"},
                moeda="USD", conta="corretora-us",
                linhas=[
                    {"quando": {"acao": "^Qualified Dividend$"}, "destino": "proventos",
                     "campos": {"tipo": "dividendo", "valor_bruto": "{valor}", "valor_liquido": "{valor}"}},
                    {"quando": {"acao": "^NRA Tax Adj$"}, "destino": "ajuste", "aplica-em": "proventos",
                     "campo": "valor_liquido", "chave": ["data", "ticker"], "valor": "{valor}"},
                    {"quando": {"acao": "^Buy$"}, "destino": "fills",
                     "campos": {"tipo": "compra", "taxa": "{taxa|0}"}},
                ],
                conciliacao={"tipo": "valor-da-linha"})
    cab = ["Date", "Action", "Symbol", "Quantity", "Price", "Fees", "Amount"]
    t = _tab([["08/13/2026", "NRA Tax Adj", "AAPL", "", "", "", "-$0.57"],
              ["08/13/2026", "Qualified Dividend", "AAPL", "", "", "", "$1.89"],
              ["08/05/2026 as of 08/04/2026", "Buy", "AAPL", "2", "$230.50", "", "-$461.00"]], cab=cab)
    r = executar(mapa, t)
    assert r.erros == []
    p = r.registros["proventos"][0]
    assert (p["valor_bruto"], round(p["valor_liquido"], 2), p["moeda"]) == (1.89, 1.32, "USD")
    f = r.registros["fills"][0]
    assert (f["data"], f["tipo"], f["qty"], f["preco"], f["taxa"], f["ticker"]) == ("2026-08-05", "compra", 2.0, 230.5, 0.0, "AAPL")
    erros, desc = conciliar(mapa, t, r)
    assert erros == [] and "2 linha(s)" in desc


def test_ajuste_sem_principal_e_erro():
    mapa = dict(MAPA_OK, linhas=[
        {"quando": {"descricao": "^IMPOSTO (?P<ticker>[A-Z0-9]+)$"}, "destino": "ajuste", "aplica-em": "proventos",
         "chave": ["data", "ticker"], "valor": "{valor}"}])
    t = _tab([["20/08/2026", "IMPOSTO HGLG11", "-1,00", "1,00"]])
    r = executar(mapa, t)
    assert any("ajuste sem linha principal" in e for e in r.erros)


def test_posicoes_exigem_data_e_geram_registro_com__data():
    mapa = dict(MAPA_OK, colunas={"ticker": "Ativo", "classe": "Classe", "qty": "Qtd", "pm": "PM"},
                linhas=[{"quando": {"ticker": "^[A-Z0-9]{4,6}$"}, "destino": "posicoes"}],
                conciliacao={"tipo": "total-declarado", "soma": "qty*pm", "origem": "flag"})
    t = _tab([["PETR4", "acoes-br", "100", "30,00"]], cab=["Ativo", "Classe", "Qtd", "PM"])
    r = executar(mapa, t)
    assert any("passe --data" in e for e in r.erros)
    r = executar(mapa, t, data_padrao="2026-08-01")
    assert r.erros == [] and r.registros["posicoes"][0]["_data"] == "2026-08-01"
    assert r.registros["posicoes"][0]["qty"] == 100.0
    erros, _ = conciliar(mapa, t, r, total_declarado=3000.0)
    assert erros == []
    erros, _ = conciliar(mapa, t, r, total_declarado=2999.0)
    assert any("≠ total declarado" in e for e in erros)
    erros, _ = conciliar(mapa, t, r)
    assert any("--total-declarado" in e for e in erros)


def test_vocabulario_da_linha_vale_no_engine():
    mapa = dict(MAPA_OK, linhas=[{"quando": {"descricao": "^RENDIMENTO (?P<ticker>[A-Z0-9]+)$"},
                                  "destino": "proventos", "campos": {"tipo": "bonus", "valor_bruto": "{valor}", "valor_liquido": "{valor}"}}])
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "1,00", "1,00"]])
    r = executar(mapa, t)
    assert any("tipo 'bonus' fora do vocabulário" in e for e in r.erros)


def test_saldo_corrente_decrescente_ok_e_quebrado():
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "99,00", "1.300,00"],
              ["19/08/2026", "TED SAIDA", "-500,00", "1.201,00"],
              ["18/08/2026", "RENDIMENTO PETR4", "1,00", "1.701,00"]])
    r = executar(MAPA_OK, t)
    erros, desc = conciliar(MAPA_OK, t, r)
    assert erros == [] and "2 par(es)" in desc
    t.linhas[1][3] = "1.200,00"
    erros, _ = conciliar(MAPA_OK, t, executar(MAPA_OK, t))
    assert any("linha 2" in e and "saldo 1300.00" in e for e in erros)


def test_valor_da_linha_fill_que_nao_fecha():
    mapa = dict(MAPA_OK, colunas={"data": "Data", "acao": "Ação", "ticker": "Ativo", "qty": "Qtd", "preco": "Preço", "taxa": "Taxa", "valor": "Valor"},
                linhas=[{"quando": {"acao": "^Compra$"}, "destino": "fills", "campos": {"tipo": "compra"}}],
                conciliacao={"tipo": "valor-da-linha"})
    cab = ["Data", "Ação", "Ativo", "Qtd", "Preço", "Taxa", "Valor"]
    t = _tab([["20/08/2026", "Compra", "PETR4", "10", "30,00", "1,00", "-350,00"]], cab=cab)
    r = executar(mapa, t)
    erros, _ = conciliar(mapa, t, r)
    assert any("301.00 ≠ valor declarado 350.00" in e for e in erros)


def test_coluna_duplicada_referenciada_pelo_mapa_e_erro():
    """Corretora que exporta duas colunas 'Valor' faria o índice resolver silenciosamente para
    a primeira, e o mapa leria a coluna errada em todas as linhas."""
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "99,00", "1.300,00"]],
             cab=["Data", "Histórico", "Valor", "Valor"])
    r = executar(MAPA_OK, t)
    assert any("'Valor'" in e and "2 vezes" in e for e in r.erros)
    assert r.registros["proventos"] == []


def test_linha_mais_larga_que_o_cabecalho_e_erro():
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "99,00", "1.300,00", "sobra"]])
    r = executar(MAPA_OK, t)
    assert any("5 células" in e and "4 colunas" in e for e in r.erros)


def test_total_declarado_de_linha_do_documento():
    mapa = dict(MAPA_OK, colunas={"ticker": "Ativo", "classe": "Classe", "qty": "Qtd", "pm": "PM", "total": "Investido"},
                linhas=[{"quando": {"ticker": "^Total$"}, "destino": "ignorar", "motivo": "linha de total"},
                        {"quando": {"ticker": "^[A-Z0-9]{4,6}$"}, "destino": "posicoes"}],
                conciliacao={"tipo": "total-declarado", "soma": "qty*pm", "origem": {"linha-contem": "Total", "coluna": "total"}})
    cab = ["Ativo", "Classe", "Qtd", "PM", "Investido"]
    t = _tab([["PETR4", "acoes-br", "100", "30,00", "3.000,00"], ["Total", "", "", "", "3.000,00"]], cab=cab)
    r = executar(mapa, t, data_padrao="2026-08-01")
    erros, desc = conciliar(mapa, t, r)
    assert erros == [] and "3000.00" in desc
