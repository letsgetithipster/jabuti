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
    assert erros == [] and "1 linha(s) conferidas" in desc and "1 provento(s) apenas transcrito" in desc


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


def test_ajuste_que_invalida_o_registro_e_erro():
    """O registro passou pelo validar_linha ANTES do ajuste; depois dele pode ter saído da regra.
    Sem reconferir, o erro só apareceria no anexar_csv, como exceção e sem a linha do documento."""
    m = dict(MAPA_OK, linhas=[
        {"quando": {"descricao": r"^COMPRA (?P<ticker>[A-Z0-9]+) (?P<qty>\d+) (?P<preco>[\d,\.]+)$"},
         "destino": "fills", "campos": {"tipo": "compra", "taxa": "0"}},
        {"quando": {"descricao": r"^ESTORNO (?P<ticker>[A-Z0-9]+)$"}, "destino": "ajuste",
         "aplica-em": "fills", "campo": "qty", "chave": ["data", "ticker"], "valor": "{valor}"}],
        conciliacao={"tipo": "valor-da-linha"})
    r = executar(m, _tab([["20/08/2026", "COMPRA PETR4 10 30,00", "300,00", "1"],
                          ["20/08/2026", "ESTORNO PETR4", "-10", "1"]]))
    assert any("depois do ajuste" in e and "positiva" in e for e in r.erros)


def test_saldo_anterior_sem_valor_ancora_a_cadeia():
    """Linha de saldo de abertura (Valor vazio, Saldo preenchido) é o formato real de Clear e B3."""
    m = dict(MAPA_OK, linhas=list(MAPA_OK["linhas"]) + [
        {"quando": {"descricao": "^SALDO ANTERIOR$"}, "destino": "ignorar", "motivo": "saldo de abertura"}])
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "99,00", "1.099,00"],
              ["19/08/2026", "TED SAIDA", "-500,00", "1.000,00"],
              ["18/08/2026", "SALDO ANTERIOR", "", "1.500,00"]])
    erros, desc = conciliar(m, t, executar(m, t))
    assert erros == [] and "âncora" in desc


def test_ancora_no_meio_da_cadeia_tem_que_repetir_o_saldo_anterior():
    """A primeira linha da cadeia abre saldo do nada (é a abertura). Da segunda em diante, linha
    sem valor que muda o saldo é lançamento fora do documento, e passava limpo."""
    m = dict(MAPA_OK, linhas=list(MAPA_OK["linhas"]) + [
        {"quando": {"descricao": "^SALDO EM"}, "destino": "ignorar", "motivo": "saldo intermediário"}])
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "99,00", "1.099,00"],
              ["19/08/2026", "SALDO EM 19/08", "", "1.000,00"],
              ["18/08/2026", "TED SAIDA", "-500,00", "1.000,00"]])
    erros, desc = conciliar(m, t, executar(m, t))
    assert erros == [] and "1 âncora(s)" in desc
    t.linhas[1][3] = "9.998,00"
    erros, _ = conciliar(m, t, executar(m, t))
    assert any("âncora" in e and "salto de 8998.00" in e for e in erros)


def test_tolerancia_declarada_vale_em_saldo_corrente_e_valor_da_linha():
    """Tolerância declarada é honrada nos três tipos, não só em total-declarado: mapeamento que
    a declara e não é obedecido é pior que mapeamento sem a chave."""
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "99,00", "1.099,50"],
              ["19/08/2026", "TED SAIDA", "-500,00", "1.000,00"]])
    assert any("saldo 1099.50" in e for e in conciliar(MAPA_OK, t, executar(MAPA_OK, t))[0])
    m = dict(MAPA_OK, conciliacao=dict(MAPA_OK["conciliacao"], tolerancia=1.0))
    erros, desc = conciliar(m, t, executar(m, t))
    assert erros == [] and "tolerância 1 (declarada no mapeamento)" in desc

    # E em valor-da-linha, que o nome deste teste promete e que antes ele não tocava. A compra
    # declara 461,50 e o produto dá 461,00: reprova no default de um centavo, passa com 1,00.
    linhas = [{"quando": {"descricao": r"^COMPRA (?P<ticker>[A-Z0-9]+) (?P<qty>\d+) (?P<preco>[\d,\.]+)$"},
               "destino": "fills", "campos": {"tipo": "compra", "taxa": "0"}}]
    doc = [["20/08/2026", "COMPRA AAPL 2 230,50", "461,50", "1"]]
    apertado = dict(MAPA_OK, linhas=linhas, conciliacao={"tipo": "valor-da-linha"})
    t2 = _tab(doc)
    assert any("461.00" in e and "461.50" in e for e in conciliar(apertado, t2, executar(apertado, t2))[0])
    frouxo = dict(apertado, conciliacao={"tipo": "valor-da-linha", "tolerancia": 1.0})
    erros2, desc2 = conciliar(frouxo, t2, executar(frouxo, t2))
    assert erros2 == [] and "tolerância 1 (declarada no mapeamento)" in desc2


def test_documento_de_uma_linha_nao_passa_vazio():
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "99,00", "1.099,00"]])
    erros, _ = conciliar(MAPA_OK, t, executar(MAPA_OK, t))
    assert any("não provou" in e for e in erros)


def test_tolerancia_do_total_escala_com_arredondamento_do_preco():
    """A corretora exibe PM com 2 casas e calcula o total com o PM cheio: em 300 posições de
    1.000 ações a diferença legítima chega a alguns reais, e um centavo reprovaria."""
    m = dict(MAPA_OK, colunas={"ticker": "Ativo", "classe": "Classe", "qty": "Qtd", "pm": "PM"},
             linhas=[{"quando": {"ticker": "^[A-Z0-9]{4,6}$"}, "destino": "posicoes"}],
             conciliacao={"tipo": "total-declarado", "soma": "qty*pm", "origem": "flag"})
    t = _tab([[f"AAA{i % 10}", "acoes-br", "1000", "10,50"] for i in range(300)],
             cab=["Ativo", "Classe", "Qtd", "PM"])
    r = executar(m, t, data_padrao="2026-08-01")
    assert conciliar(m, t, r, total_declarado=3150005.38)[0] == []
    assert any("passa da tolerância" in e for e in conciliar(m, t, r, total_declarado=3200000.00)[0])


def test_acertos_contam_linhas_por_regra():
    """Sem isso, uma regra genérica acima de uma específica engole linhas sem ninguém notar."""
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "99,00", "1.099,00"],
              ["19/08/2026", "TED SAIDA", "-500,00", "1.000,00"]])
    r = executar(MAPA_OK, t)
    assert r.acertos == {1: 1, 2: 1}


def test_acertos_comeca_zerado_para_regra_que_nunca_casa():
    """Regra 2 nunca casa nesse documento: acertos tem que declarar 0, não omitir a chave."""
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "99,00", "1.300,00"]])
    r = executar(MAPA_OK, t)
    assert r.acertos == {1: 1, 2: 0}


def test_contagem_de_linhas_tambem_vale_no_caminho_de_erro():
    """A conta 'nenhuma linha some em silêncio' rodava só quando res.erros já estava vazio,
    verificando exatamente o caso que menos precisa: o run limpo. Com erro, tem que continuar
    batendo (linha com erro nunca vira registro em tabela nenhuma) e não pode acrescentar um
    'erro interno da ingestão' espúrio por cima do erro real."""
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "abc", "1,00"],
              ["19/08/2026", "TED SAIDA", "-500,00", "1.201,00"]])
    r = executar(MAPA_OK, t)
    assert any("valor_bruto não numérico" in e for e in r.erros)
    assert not any("erro interno da ingestão" in e for e in r.erros)


def test_saldo_corrente_documento_vazio_e_no_op():
    t = _tab([])
    r = executar(MAPA_OK, t)
    assert r.erros == [] and r.linhas_lidas == 0
    erros, desc = conciliar(MAPA_OK, t, r)
    assert erros == [] and "no-op" in desc


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


def test_valor_da_linha_com_todo_provento_transcrito_nao_finge_conferencia():
    """`valor_bruto: "{valor}"` compara a célula com ela mesma. Um mapeamento em que TODO provento
    é assim e que não tem fill nenhum não prova aritmética alguma: dizer "1 linha conferida" era
    afirmar prova que não houve. Tem que parar e dizer o que fazer no lugar."""
    m = dict(MAPA_OK, linhas=[MAPA_OK["linhas"][0]], conciliacao={"tipo": "valor-da-linha"})
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "99,00", "1.300,00"],
              ["19/08/2026", "RENDIMENTO PETR4", "1,00", "1.301,00"]])
    r = executar(m, t)
    assert r.erros == []
    erros, desc = conciliar(m, t, r)
    assert any("não conferiu linha nenhuma" in e and "saldo-corrente" in e
               and "valor_liquido" in e for e in erros)
    assert "0 linha(s) conferidas" in desc and "2 provento(s) apenas transcrito" in desc


def test_provento_transcrito_nao_e_erro_quando_ha_conferencia_de_verdade():
    """Contra-prova da anterior: com um fill no mesmo documento, a conciliação tem o que provar.
    A linha transcrita continua não contando como conferida, mas não para a importação."""
    m = dict(MAPA_OK, linhas=[
        MAPA_OK["linhas"][0],
        {"quando": {"descricao": r"^COMPRA (?P<ticker>[A-Z0-9]+) (?P<qty>\d+) (?P<preco>[\d,.]+)$"},
         "destino": "fills", "campos": {"tipo": "compra", "taxa": "0"}}],
        conciliacao={"tipo": "valor-da-linha"})
    t = _tab([["20/08/2026", "RENDIMENTO HGLG11", "99,00", "1.300,00"],
              ["19/08/2026", "COMPRA PETR4 10 30,00", "-300,00", "1.000,00"]])
    erros, desc = conciliar(m, t, executar(m, t))
    assert erros == []
    assert "1 linha(s) conferidas" in desc and "1 provento(s) apenas transcrito" in desc


RODAPE = [["20/08/2026", "RENDIMENTO HGLG11", "99,00", "1.300,00"],
          ["19/08/2026", "TED SAIDA", "-500,00", "1.201,00"],
          ["", "SALDO DISPONIVEL", "", "5.000,00"]]


def _com_rodape(fora: bool):
    regra = {"quando": {"descricao": "^SALDO DISPONIVEL$"}, "destino": "ignorar",
             "motivo": "rodapé de saldo disponível, fora do extrato"}
    if fora:
        regra["fora-da-cadeia"] = True
    return dict(MAPA_OK, linhas=list(MAPA_OK["linhas"]) + [regra])


def test_rodape_de_saldo_dentro_da_tabela_sem_a_chave_acusa_o_salto():
    """`ignorar` é "não vira registro", não "não conta na aritmética": o rodapé continuava na
    cadeia de saldos e a quebrava. Sem escotilha, a única saída era subir a tolerância até
    engolir o salto, o que desliga a conferência do documento inteiro."""
    m = _com_rodape(fora=False)
    t = _tab(RODAPE)
    r = executar(m, t)
    assert r.erros == [] and len(r.ignoradas) == 2
    erros, _ = conciliar(m, t, r)
    assert any("5000.00" in e for e in erros)


def test_rodape_marcado_fora_da_cadeia_fecha_limpo():
    m = _com_rodape(fora=True)
    t = _tab(RODAPE)
    r = executar(m, t)
    assert r.erros == []
    erros, desc = conciliar(m, t, r)
    assert erros == [] and "1 par(es)" in desc
    # e o rodapé continua ignorado como qualquer outra linha de `ignorar`: fora da cadeia não
    # é fora do documento, ele segue contado e nomeado
    assert (4, "rodapé de saldo disponível, fora do extrato") in r.ignoradas
