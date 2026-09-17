import datetime

import pytest

from po.csvs import ler_csv
from po.estado import gerar_estado
from po.frontmatter import extrair_frontmatter
from po.ingestao.engine import Resultado
from po.ingestao.escrita import GravacaoParcial, conferir, gravar
from po.validar import validar
from test_validar_dados import _anexa, copia_exemplo


def _res(**registros):
    r = Resultado(linhas_lidas=sum(len(v) for v in registros.values()))
    for nome, regs in registros.items():
        for i, reg in enumerate(regs, start=2):
            reg.setdefault("_linha", i)
        r.registros[nome] = regs
    return r


def _prov(data, ticker, bruto, liquido=None, conta="corretora-br"):
    return {"data": data, "ticker": ticker, "cnpj": "", "tipo": "rendimento", "valor_bruto": float(bruto),
            "valor_liquido": float(liquido if liquido is not None else bruto), "conta": conta, "moeda": "BRL"}


def _fill(data, ticker, qty, preco, tipo="compra", conta="corretora-br"):
    return {"data": data, "ticker": ticker, "tipo": tipo, "qty": float(qty), "preco": float(preco),
            "taxa": 0.0, "conta": conta, "moeda": "BRL"}


def _pos(ticker, qty, pm, data="2026-09-08", classe="acoes-br", conta="corretora-br"):
    # data default DEPOIS do último fill do exemplo (09-05): a conferência corta o ledger na data
    # da foto, e uma foto de 09-01 com PETR4 100 @ 30 diverge do livro de 09-01 (60 @ 29,50)
    return {"ticker": ticker, "classe": classe, "conta": conta, "qty": float(qty), "pm": float(pm),
            "moeda": "BRL", "_data": data}


def test_grava_proventos_e_log_com_frontmatter(tmp_path):
    ws = copia_exemplo(tmp_path)
    res = _res(proventos=[_prov("2026-09-05", "HGLG11", 55.00), _prov("2026-10-05", "HGLG11", 56.00)])
    r = gravar(ws, res, mapeamento="clear-extrato", arquivo="extrato.xlsx", conciliacao="saldo-corrente: 1 par",
               conta="corretora-br", hoje=datetime.date(2026, 10, 8))
    assert r["gravadas"]["proventos"] == 1 and r["duplicadas"]["proventos"] == 1   # a de 09-05 já existia
    linhas, erros = ler_csv("proventos", ws / "dados" / "proventos.csv")
    assert erros == [] and len(linhas) == 2 and linhas[-1]["valor_bruto"] == 56.0
    log = r["log"]
    assert log == ws / "logs" / "importacoes" / "2026-10-08-clear-extrato.md"
    meta, corpo = extrair_frontmatter(log.read_text(encoding="utf-8"))
    assert meta["tipo"] == "log-importacao" and meta["mapeamento"] == "clear-extrato" and meta["conta"] == "corretora-br"
    assert "| proventos | 1 | 1 |" in corpo
    erros, _ = validar(ws)
    assert erros == []


def test_log_nao_sobrescreve_no_mesmo_dia(tmp_path):
    ws = copia_exemplo(tmp_path)
    kw = dict(mapeamento="m", arquivo="a.csv", conciliacao="x", conta="corretora-br", hoje=datetime.date(2026, 10, 8))
    r1 = gravar(ws, _res(proventos=[_prov("2026-10-05", "HGLG11", 1.0)]), **kw)
    r2 = gravar(ws, _res(proventos=[_prov("2026-11-05", "HGLG11", 1.0)]), **kw)
    assert r1["log"].name == "2026-10-08-m.md" and r2["log"].name == "2026-10-08-m-2.md"


def test_terceira_importacao_no_mesmo_dia_continua_subindo(tmp_path):
    """Contraprova do helper compartilhado (`po.ingestao.artefatos.caminho_datado_livre`), que
    agora nomeia tanto o log de documento (aqui) quanto o payload de provider
    (`test_ingestao_provider.py`). Ela não impede re-duplicação — cada rodada continua gravando
    seu próprio log, igual antes. O que ela impede é DIVERGÊNCIA: enquanto a regra de sufixo
    vivia copiada nos dois arquivos, mudar o esquema de um lado (`-2`, `-3`, ...) podia deixar o
    outro para trás em silêncio. Com os dois lados chamando o mesmo helper, um teste que muda a
    regra em `artefatos.py` quebra esta ponta também, em vez de só a de provider."""
    ws = copia_exemplo(tmp_path)
    kw = dict(mapeamento="m", arquivo="a.csv", conciliacao="x", conta="corretora-br", hoje=datetime.date(2026, 10, 8))
    r1 = gravar(ws, _res(proventos=[_prov("2026-10-05", "HGLG11", 1.0)]), **kw)
    r2 = gravar(ws, _res(proventos=[_prov("2026-11-05", "HGLG11", 1.0)]), **kw)
    r3 = gravar(ws, _res(proventos=[_prov("2026-12-05", "HGLG11", 1.0)]), **kw)
    assert [r["log"].name for r in (r1, r2, r3)] == ["2026-10-08-m.md", "2026-10-08-m-2.md", "2026-10-08-m-3.md"]


def test_posicao_nova_nasce_com_saldo_inicial_e_valida(tmp_path):
    ws = copia_exemplo(tmp_path)
    pos = {"ticker": "VALE3", "classe": "acoes-br", "conta": "corretora-br", "qty": 10.0, "pm": 60.0, "moeda": "BRL",
           "_data": "2026-08-01"}
    r = gravar(ws, _res(posicoes=[pos]), mapeamento="m", arquivo="p.csv", conciliacao="x", conta="corretora-br")
    assert r["gravadas"] == {"fills": 1, "proventos": 0, "eventos": 0, "ativos": 1} and r["aberturas"] == 1
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    assert fills[-1]["tipo"] == "saldo-inicial" and fills[-1]["preco"] == 60.0 and fills[-1]["data"] == "2026-08-01"
    erros, _ = validar(ws)
    assert erros == ["cotacoes.csv: VALE3 sem nenhuma cotação — rode scripts/atualizar_cotacoes.py (ou passe --manual VALE3=PRECO)"]


def test_posicao_igual_e_duplicada_sem_saldo_inicial(tmp_path):
    ws = copia_exemplo(tmp_path)
    pos = {"ticker": "PETR4", "classe": "acoes-br", "conta": "corretora-br", "qty": 100.0, "pm": 30.0, "moeda": "BRL",
           "_data": "2026-09-08"}   # depois da compra de 09-05: em 09-01 o livro tinha 60 @ 29,50
    r = gravar(ws, _res(posicoes=[pos]), mapeamento="m", arquivo="p.csv", conciliacao="x", conta="corretora-br")
    assert r["gravadas"]["fills"] == 0 and r["gravadas"]["ativos"] == 0 and r["aberturas"] == 0


def test_posicao_divergente_barra_a_gravacao_inteira_inclusive_o_provento(tmp_path):
    """PETR4 já tem fill e o documento diz 120 contra os 100 do ledger: a diferença é a operação
    que o livro ainda não tem, e o motor não escolhe qual. Nada entra, nem o provento que veio no
    mesmo documento: gravar metade de um documento que contradiz o livro esconderia a contradição
    atrás de um "proventos +1". (O G1 dizia o contrário; a semântica de "não é conflito" morreu
    junto com a tabela contra a qual ela valia.)"""
    ws = copia_exemplo(tmp_path)
    antes = _dados(ws)
    res = _res(posicoes=[_pos("PETR4", 120, 30.0)], proventos=[_prov("2026-10-05", "HGLG11", 1.0)])
    linhas, divergiu, _ = conferir(ws, res)
    texto = "\n".join(linhas)
    assert divergiu and "PETR4 (corretora-br): o ledger tem 100 @ R$ 30,00 em 2026-09-08; o documento diz 120 @ R$ 30,00." in texto
    assert "preço implícito R$ 30,00" in texto
    with pytest.raises(ValueError, match="não bate com o seu livro"):
        gravar(ws, res, mapeamento="m", arquivo="p.csv", conciliacao="x", conta="corretora-br")
    assert _dados(ws) == antes
    assert not (ws / "logs" / "importacoes").exists()


def test_dados_sujos_bloqueiam_importacao(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "fills.csv").write_text("data,ticker\n", encoding="utf-8")
    with pytest.raises(ValueError, match="corrija antes de importar"):
        gravar(ws, _res(proventos=[_prov("2026-10-05", "HGLG11", 1.0)]), mapeamento="m", arquivo="a", conciliacao="x", conta="corretora-br")


def test_conferir_compara_sem_gravar(tmp_path):
    ws = copia_exemplo(tmp_path)
    antes = _dados(ws)
    res = _res(posicoes=[
        {"ticker": "PETR4", "classe": "acoes-br", "conta": "corretora-br", "qty": 100.0, "pm": 30.0, "moeda": "BRL", "_data": "2026-09-08"},
        {"ticker": "VALE3", "classe": "acoes-br", "conta": "corretora-br", "qty": 10.0, "pm": 60.0, "moeda": "BRL", "_data": "2026-09-08"},
    ], proventos=[_prov("2026-09-05", "HGLG11", 55.00)])
    linhas, divergiu, _novos = conferir(ws, res)
    texto = "\n".join(linhas)
    assert divergiu is True   # HGLG11 está em dados/ e não no documento
    assert "PETR4 (corretora-br): OK" in texto and "VALE3 (corretora-br): NOVA" in texto
    assert "HGLG11 (corretora-br): 50 @ 155,00 no livro e ausente do documento" in texto
    assert "registre a venda" in texto
    assert "proventos: 0 nova(s), 1 já presente(s)" in texto
    assert _novos == 2                       # a abertura de VALE3 E a linha dela em ativos.csv
    assert _dados(ws) == antes


def test_conferir_sem_divergencia_nao_diverge(tmp_path):
    """A prévia usa o mesmo `separar` da gravação: sem divergência de posição, `divergiu` é
    False mesmo havendo lançamento novo a gravar (novo não é divergente)."""
    ws = copia_exemplo(tmp_path)
    res = _res(posicoes=[_pos("PETR4", 100, 30.0), _pos("HGLG11", 50, 155.0, classe="fiis")],
               proventos=[_prov("2026-10-05", "HGLG11", 56.00)])
    linhas, divergiu, _novos = conferir(ws, res)
    assert divergiu is False
    assert "proventos: 1 nova(s), 0 já presente(s)" in "\n".join(linhas)


# --- dedupe por multiconjunto: o documento nunca é comparado contra ele mesmo ---------------

KW = dict(mapeamento="m", arquivo="a.csv", conciliacao="x", conta="corretora-br")


def _duas_compras_iguais():
    """Duas execuções parciais da mesma ordem: mesmo dia, mesmo preço, mesma quantidade."""
    return _res(fills=[_fill("2026-09-10", "PETR4", 10, 31.00), _fill("2026-09-10", "PETR4", 10, 31.00)])


def _iguais_em(ws):
    fills, erros = ler_csv("fills", ws / "dados" / "fills.csv")
    assert erros == []
    return [f for f in fills if f["data"] == "2026-09-10" and f["ticker"] == "PETR4" and f["preco"] == 31.0]


def test_duas_linhas_identicas_no_documento_gravam_duas(tmp_path):
    """Regra do multiconjunto. Duas execuções parciais da mesma ordem são dois eventos reais e
    rotineiros em B3 e Schwab; deduplicar o documento contra si mesmo perderia a segunda em
    silêncio, depois de a conciliação já ter abençoado as duas."""
    ws = copia_exemplo(tmp_path)
    r = gravar(ws, _duas_compras_iguais(), **KW)
    assert r["gravadas"]["fills"] == 2 and r["duplicadas"]["fills"] == 0
    assert len(_iguais_em(ws)) == 2


def test_reimportar_o_mesmo_documento_nao_duplica_nada(tmp_path):
    ws = copia_exemplo(tmp_path)
    gravar(ws, _duas_compras_iguais(), **KW)
    r = gravar(ws, _duas_compras_iguais(), **KW)
    assert r["gravadas"]["fills"] == 0 and r["duplicadas"]["fills"] == 2
    assert len(_iguais_em(ws)) == 2


def test_documento_com_duas_iguais_e_dados_com_uma_grava_so_a_que_falta(tmp_path):
    """A metade que faltava. O contador de existentes decrementa a cada casamento, então a
    segunda linha do documento não encontra par e entra."""
    ws = copia_exemplo(tmp_path)
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8")
                     + "2026-09-10,PETR4,compra,10,31.00,0,corretora-br,BRL\n", encoding="utf-8")
    r = gravar(ws, _duas_compras_iguais(), **KW)
    assert r["gravadas"]["fills"] == 1 and r["duplicadas"]["fills"] == 1
    assert len(_iguais_em(ws)) == 2


# --- posição do documento: abertura por lote, multiconjunto no ledger ------------------------

def _dados(ws):
    return {p.name: p.read_text(encoding="utf-8") for p in sorted((ws / "dados").glob("*.csv"))}


def test_dois_lotes_do_mesmo_ticker_no_documento_viram_uma_abertura_consolidada(tmp_path):
    """A guarda de unicidade morreu com a tabela, e o ledger abre cada ticker/conta uma vez só.
    Corretora que quebra a posição por lote ou por agente de custódia gera UMA abertura: qty
    somada (60 + 40), PM ponderado (59,20), e o log nomeia a consolidação. Antes era conflito que
    mandava "consolidar no mapeamento", coisa que o mapeamento não sabe fazer."""
    ws = copia_exemplo(tmp_path)
    r = gravar(ws, _res(posicoes=[_pos("VALE3", 60, 58.0), _pos("VALE3", 40, 61.0)]), **KW)
    assert r["gravadas"] == {"fills": 1, "proventos": 0, "eventos": 0, "ativos": 1} and r["aberturas"] == 1
    assert "Aberturas (saldo-inicial): 1; VALE3 (corretora-br): 2 lotes consolidados numa abertura" in \
        r["log"].read_text(encoding="utf-8")
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    assert [(f["tipo"], f["qty"], f["preco"]) for f in fills if f["ticker"] == "VALE3"] == \
        [("saldo-inicial", 100.0, 59.2)]
    from po.carteira import valorar
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,VALE3,62.00,BRL,manual")
    vale = next(l for l in valorar(ws, hoje=datetime.date(2026, 9, 8)).linhas if l.ticker == "VALE3")
    assert vale.qty == 100 and round(vale.pm, 2) == 59.20


def test_ledger_continua_multiconjunto_ao_lado_da_posicao(tmp_path):
    """Duas compras idênticas no mesmo documento continuam virando duas linhas, e a posição do
    mesmo documento não vira abertura (o ticker já tem fill no próprio documento)."""
    ws = copia_exemplo(tmp_path)
    res = _res(posicoes=[_pos("VALE3", 20, 31.0)],
               fills=[_fill("2026-09-10", "VALE3", 10, 31.00), _fill("2026-09-10", "VALE3", 10, 31.00)])
    r = gravar(ws, res, **KW)
    assert r["gravadas"]["ativos"] == 1 and r["gravadas"]["fills"] == 2 and r["aberturas"] == 0
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    assert [f["tipo"] for f in fills if f["ticker"] == "VALE3"] == ["compra", "compra"]


# --- conferir: 'sem divergência' e 'nada a fazer' são coisas diferentes ----------------------

def test_conferir_conta_os_registros_novos(tmp_path):
    """O terceiro valor de `conferir`. Sem ele o CLI dizia 'o documento bate com dados/'
    contradizendo a linha logo acima, que anunciava lançamento novo a gravar."""
    ws = copia_exemplo(tmp_path)
    _linhas, divergiu, novos = conferir(ws, _res(proventos=[_prov("2026-10-05", "HGLG11", 56.00)]))
    assert divergiu is False and novos == 1
    _linhas, divergiu, novos = conferir(ws, _res(proventos=[_prov("2026-09-05", "HGLG11", 55.00)]))
    assert divergiu is False and novos == 0


def test_conferir_recusa_resultado_com_erro(tmp_path):
    """Mesma guarda de `gravar`: prévia sobre resultado que a gravação recusaria mente."""
    ws = copia_exemplo(tmp_path)
    res = _res(proventos=[_prov("2026-10-05", "HGLG11", 1.0)])
    res.erros.append("linha 7: valor_bruto não numérico ('abc')")
    with pytest.raises(ValueError, match="nada a conferir") as exc:
        conferir(ws, res)
    assert "linha 7" in str(exc.value)


# --- gravação parcial e a abertura que ficou faltando ---------------------------------------

def _falha_em_fills(monkeypatch):
    """Trava anexar_csv na tabela fills: a gravação já escreveu ativos e morre no meio,
    como um fills.csv aberto no Excel."""
    from po.ingestao import escrita as mod
    real = mod.anexar_csv

    def falso(nome, caminho, linhas):
        if nome == "fills":
            raise OSError(13, "Permission denied")
        return real(nome, caminho, linhas)

    monkeypatch.setattr(mod, "anexar_csv", falso)


def test_gravacao_parcial_levanta_e_o_log_nomeia_o_que_entrou(tmp_path, monkeypatch):
    """A rodada que mais precisa de registro é justamente a que morreu no meio."""
    ws = copia_exemplo(tmp_path)
    _falha_em_fills(monkeypatch)
    with pytest.raises(GravacaoParcial):
        gravar(ws, _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")]), **KW)
    logs = sorted((ws / "logs" / "importacoes").glob("*.md"))
    assert len(logs) == 1
    corpo = logs[0].read_text(encoding="utf-8")
    assert "**A gravação falhou no meio**" in corpo
    assert "| ativos | 1 | 0 |" in corpo and "| fills | 0 | 0 |" in corpo
    assert "Aberturas (saldo-inicial): 0" in corpo                  # a abertura NÃO entrou
    ativos, _ = ler_csv("ativos", ws / "dados" / "ativos.csv")
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    assert any(a["ticker"] == "VALE3" for a in ativos)        # entrou o que o log nomeia
    assert not any(f["ticker"] == "VALE3" for f in fills)     # e só isso


def test_rodada_seguinte_completa_o_saldo_inicial_que_faltou(tmp_path, monkeypatch):
    """Sem isto o ledger ficava permanentemente sem abertura: a posição já existia, a rodada
    seguinte a via como duplicada e o saldo-inicial nunca nascia."""
    ws = copia_exemplo(tmp_path)
    _falha_em_fills(monkeypatch)
    with pytest.raises(GravacaoParcial):
        gravar(ws, _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")]), **KW)
    monkeypatch.undo()
    r = gravar(ws, _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")]), **KW)
    assert r["gravadas"]["ativos"] == 0                       # já declarado na rodada que morreu
    assert r["gravadas"]["fills"] == 1 and r["aberturas"] == 1
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    abertura = [f for f in fills if f["ticker"] == "VALE3"]
    assert len(abertura) == 1
    assert abertura[0]["tipo"] == "saldo-inicial" and abertura[0]["qty"] == 20.0 and abertura[0]["preco"] == 60.0


def test_ticker_com_fill_no_documento_nao_ganha_abertura_sintetica(tmp_path):
    ws = copia_exemplo(tmp_path)
    res = _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")],
               fills=[_fill("2026-09-10", "VALE3", 20, 60.00)])
    r = gravar(ws, res, **KW)
    assert r["gravadas"] == {"fills": 1, "proventos": 0, "eventos": 0, "ativos": 1} and r["aberturas"] == 0
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    assert [f["tipo"] for f in fills if f["ticker"] == "VALE3"] == ["compra"]


def test_ticker_com_fill_em_dados_nao_ganha_abertura_sintetica(tmp_path):
    ws = copia_exemplo(tmp_path)
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8")
                     + "2026-09-10,VALE3,compra,20,60.00,0,corretora-br,BRL\n", encoding="utf-8")
    r = gravar(ws, _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")]), **KW)
    assert r["gravadas"]["ativos"] == 1 and r["gravadas"]["fills"] == 0 and r["aberturas"] == 0
    lidos, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    assert [f["tipo"] for f in lidos if f["ticker"] == "VALE3"] == ["compra"]


def test_workspace_continua_valido_depois_da_parcial_e_da_rodada_que_completou(tmp_path, monkeypatch):
    """Fim de linha do caminho de recuperação: o ledger fecha e o validador não acha nada.
    A cotação e o ESTADO são trabalho de outras skills, não da escrita — aqui a cotação entra
    à mão e o ESTADO é REGENERADO, não editado, só para o check ter o que conferir. Editar a
    linha do total à mão deixou de bastar: o check compara o arquivo inteiro contra o gerador."""
    ws = copia_exemplo(tmp_path)
    _falha_em_fills(monkeypatch)
    with pytest.raises(GravacaoParcial):
        gravar(ws, _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")]), **KW)
    monkeypatch.undo()
    gravar(ws, _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")]), **KW)
    cot = ws / "dados" / "cotacoes.csv"
    cot.write_text(cot.read_text(encoding="utf-8") + "2026-09-09,18:00,VALE3,62.00,BRL,manual\n",
                   encoding="utf-8")
    _caminho, texto = gerar_estado(ws, hoje=datetime.date(2026, 9, 10))
    assert "Total investido: R$ 13.240,00" in texto, texto   # 100×40 + 50×160 + 20×62
    erros, _ = validar(ws)
    assert erros == []


def test_gravar_recusa_resultado_com_erro(tmp_path):
    """O contrato 'nada entra em dados/ sem conciliação' valia só por disciplina do chamador."""
    ws = copia_exemplo(tmp_path)
    antes = (ws / "dados" / "proventos.csv").read_text(encoding="utf-8")
    res = _res(proventos=[_prov("2026-10-05", "HGLG11", 1.0)])
    res.erros.append("linha 7: valor_bruto não numérico ('abc')")
    with pytest.raises(ValueError, match="nada gravado") as exc:
        gravar(ws, res, **KW)
    assert "linha 7" in str(exc.value)          # a frase diz qual erro barrou
    assert (ws / "dados" / "proventos.csv").read_text(encoding="utf-8") == antes
    assert not (ws / "logs" / "importacoes").exists()


def test_log_registra_acertos_por_regra_e_as_que_nunca_casaram(tmp_path):
    """Regra morta não vira aviso gritado em toda rodada (mapa real tem uma regra por tipo de
    evento e o mês aciona duas ou três), mas fica auditável no registro durável."""
    ws = copia_exemplo(tmp_path)
    res = _res(proventos=[_prov("2026-10-05", "HGLG11", 1.0)])
    res.acertos = {1: 1, 2: 0, 3: 0}
    r = gravar(ws, res, **KW)
    corpo = r["log"].read_text(encoding="utf-8")
    assert "Acertos por regra de `linhas`: regra 1: 1; regra 2: 0; regra 3: 0" in corpo
    assert "Regras que nunca casaram: [2, 3]" in corpo
def test_conferir_escreve_quantidade_e_pm_em_pt_br(tmp_path):
    """C8: a prévia escrevia "3e-08 @ 350000.00" para três satoshis a R$ 350.000,00."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/ativos.csv", "BTC,cripto")
    _anexa(ws, "dados/fills.csv", "2026-08-01,BTC,saldo-inicial,0.00012345,350000.00,0,corretora-br,BRL")
    linhas, _, _ = conferir(ws, _res(posicoes=[_pos("BTC", 0.00012345, 350000.0, classe="cripto"),
                                              _pos("VALE3", 1500, 60.5),
                                              _pos("HGLG11", 50.5, 155.0, classe="fiis")]))
    texto = "\n".join(linhas)
    assert "BTC (corretora-br): OK — 0,00012345 @ 350.000,00" in texto, texto
    assert "VALE3 (corretora-br): NOVA no documento — 1.500 @ 60,50" in texto, texto
    assert "HGLG11 (corretora-br): o ledger tem 50 @ R$ 155,00 em 2026-09-08; o documento diz 50,5 @ R$ 155,00." in texto, texto


# --- G1: posicoes.csv deixa de existir; o documento de posição grava abertura + ativo -------

def test_posicao_do_documento_vira_abertura_e_ativo_nunca_posicoes_csv(tmp_path):
    """Spec §2.1: cada linha de posição do documento vira UM fill `saldo-inicial` e UMA linha em
    dados/ativos.csv. A síntese do saldo-inicial já existia como complemento da escrita em
    posicoes.csv; agora é a escrita inteira. Recolocar `posicoes` em TABELAS faz este teste cair
    (a tabela morta renasce no workspace)."""
    from po.ingestao import escrita
    ws = copia_exemplo(tmp_path)
    assert "posicoes" not in escrita.TABELAS
    r = gravar(ws, _res(posicoes=[_pos("VALE3", 10, 60.0, data="2026-08-01"),
                                  _pos("BTC", 0.5, 300000.0, data="2026-08-01", classe="cripto")]), **KW)
    assert r["gravadas"] == {"fills": 2, "proventos": 0, "eventos": 0, "ativos": 2}
    assert r["aberturas"] == 2
    assert not (ws / "dados" / "posicoes.csv").exists()
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    assert [(f["ticker"], f["tipo"], f["qty"], f["preco"], f["data"]) for f in fills[-2:]] == \
        [("VALE3", "saldo-inicial", 10.0, 60.0, "2026-08-01"), ("BTC", "saldo-inicial", 0.5, 300000.0, "2026-08-01")]
    ativos, _ = ler_csv("ativos", ws / "dados" / "ativos.csv")
    assert [(a["ticker"], a["classe"]) for a in ativos[-2:]] == [("VALE3", "acoes-br"), ("BTC", "cripto")]
    assert "Aberturas (saldo-inicial): 2" in r["log"].read_text(encoding="utf-8")
    # o único erro que sobra é o de cotação: o ledger fechou e a classe está declarada
    erros, _ = validar(ws)
    assert erros == ["cotacoes.csv: BTC sem nenhuma cotação — rode scripts/atualizar_cotacoes.py (ou passe --manual BTC=PRECO)",
                     "cotacoes.csv: VALE3 sem nenhuma cotação — rode scripts/atualizar_cotacoes.py (ou passe --manual VALE3=PRECO)"]


def test_reimportar_documento_de_posicao_nao_grava_nada(tmp_path):
    """Idempotência sem a tabela: ticker que já tem fill não ganha abertura, ticker já declarado
    não ganha linha em ativos.csv."""
    ws = copia_exemplo(tmp_path)
    r = gravar(ws, _res(posicoes=[_pos("PETR4", 100, 30.0), _pos("HGLG11", 50, 155.0, classe="fiis")]), **KW)
    assert r["gravadas"] == {"fills": 0, "proventos": 0, "eventos": 0, "ativos": 0} and r["aberturas"] == 0


def test_ativos_csv_da_pessoa_vence_a_classe_do_documento(tmp_path):
    """Decisão 10: ativos.csv é declaração da pessoa. Documento que traz outra classe para um
    ticker já declarado não a sobrescreve nem anexa linha nova."""
    ws = copia_exemplo(tmp_path)
    antes = (ws / "dados" / "ativos.csv").read_text(encoding="utf-8")
    r = gravar(ws, _res(posicoes=[_pos("PETR4", 100, 30.0, classe="fiis")]), **KW)
    assert r["gravadas"]["ativos"] == 0
    assert (ws / "dados" / "ativos.csv").read_text(encoding="utf-8") == antes


def test_conferir_nao_engole_um_satoshi(tmp_path):
    """`_mesma_posicao` tolerava 1e-6 em qty e morreu com o ramo de unicidade: um satoshi (1e-8)
    a mais no documento é divergência, não ruído. (A posição fica acima de TOLERANCIA_QTY do
    ledger, 1e-6, senão ela nem existe para o motor.)"""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/ativos.csv", "BTC,cripto")
    _anexa(ws, "dados/fills.csv", "2026-08-01,BTC,saldo-inicial,0.00012345,350000.00,0,corretora-br,BRL")
    linhas, divergiu, _ = conferir(ws, _res(posicoes=[_pos("BTC", 0.00012346, 350000.0, classe="cripto")]))
    texto = "\n".join(linhas)
    assert divergiu, texto
    assert "BTC (corretora-br): o ledger tem 0,00012345 @ R$ 350.000,00 em 2026-09-08; o documento diz 0,00012346 @ R$ 350.000,00." in texto, texto
    assert "e-0" not in texto


def test_abertura_consolidada_nasce_na_data_do_primeiro_lote(tmp_path):
    """A abertura consolidada carrega a data da PRIMEIRA linha do documento, não da última.
    Sonda da revisão do G1: trocar `ps[0]["_data"]` por `ps[-1]["_data"]` passava verde, porque
    os dois lotes do teste anterior têm a mesma data."""
    ws = copia_exemplo(tmp_path)
    r = gravar(ws, _res(posicoes=[_pos("VALE3", 60, 58.0, data="2026-07-01"),
                                  _pos("VALE3", 40, 61.0, data="2026-08-01")]), **KW)
    assert r["aberturas"] == 1
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    assert [(f["data"], f["qty"], f["preco"]) for f in fills if f["ticker"] == "VALE3"] == \
        [("2026-07-01", 100.0, 59.2)]


# --- F2a.3: a divergência contra a corretora vira conversa, não recusa --------------------

def test_conferir_diverge_contra_o_ledger_e_nao_contra_tabela(tmp_path):
    ws = copia_exemplo(tmp_path)
    linhas, divergiu, _ = conferir(ws, _res(posicoes=[_pos("PETR4", 150, 32.0)]))
    texto = "\n".join(linhas)
    assert divergiu
    assert "preço implícito R$ 36,00" in texto and "registrar.py" in texto
    assert "Resolva antes de importar" not in texto


def test_gravar_recusa_foto_divergente_com_o_mesmo_texto_da_conferencia(tmp_path):
    """Prévia e gravação não podem dizer coisas diferentes: é o contrato do módulo."""
    ws = copia_exemplo(tmp_path)
    antes = _dados(ws)
    with pytest.raises(ValueError) as exc:
        _grava_pos(ws, _pos("PETR4", 150, 32.0))
    assert "preço implícito R$ 36,00" in str(exc.value)
    assert "--conferir" not in str(exc.value)
    assert _dados(ws) == antes


def _grava_pos(ws, *posicoes):
    return gravar(ws, _res(posicoes=list(posicoes)), **KW)


def test_conferir_corta_o_ledger_na_data_do_documento(tmp_path):
    """Uma foto de 31/08 é conferida contra o livro COMO ELE ERA em 31/08 (PETR4 60 @ 29,50), não
    contra o de hoje (100 @ 30,00 depois da compra de 05/09). É o corte por data que a F1
    entregou e que esta task existe para usar: sem ele, toda foto antiga divergiria."""
    ws = copia_exemplo(tmp_path)
    foto = [_pos("PETR4", 60, 29.5, data="2026-08-31"), _pos("HGLG11", 50, 155.0, data="2026-08-31", classe="fiis")]
    linhas, divergiu, _ = conferir(ws, _res(posicoes=list(foto)))
    assert not divergiu, linhas
    assert "PETR4 (corretora-br): OK — 60 @ 29,50" in "\n".join(linhas)
    r = _grava_pos(ws, *foto)
    assert r["gravadas"]["fills"] == 0 and r["aberturas"] == 0


def test_ajuste_de_custo_e_nota_e_nao_barra_a_importacao(tmp_path):
    """Quantidade bate e o PM da corretora difere por centavos (taxa que ela soma ao custo, ou
    arredondamento): "nada a fazer" é o próximo passo, e a foto tem que continuar passando todo
    mês. Se isso barrasse, a pessoa nunca mais importaria essa foto: o beco de novo."""
    ws = copia_exemplo(tmp_path)
    foto = [_pos("PETR4", 100, 30.02), _pos("HGLG11", 50, 155.0, classe="fiis")]
    linhas, divergiu, _ = conferir(ws, _res(posicoes=list(foto)))
    texto = "\n".join(linhas)
    assert not divergiu, texto
    assert "nada a fazer" in texto.lower() and "R$ 2,00" in texto
    r = _grava_pos(ws, *foto)
    assert r["gravadas"]["fills"] == 0


def test_ticker_com_fill_e_saldo_zero_na_data_da_foto_e_divergencia_nao_abertura(tmp_path):
    """Revisão do grupo F: HGLG11 vendida inteira em 06/09 e a foto de 08/09 diz 50 @ 155. Antes,
    a prévia prometia "abre o livro como saldo-inicial" e a gravação passava em silêncio com
    "nada novo" (`_aberturas` nunca abre quem já tem fill): o beco silencioso de volta, por
    outra porta. Agora é divergência a partir do zero, com o comando, e --aceitar-como compra
    fecha o ledger datado na foto. Vale também para a foto ANTERIOR ao primeiro fill do ticker."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/fills.csv", "2026-09-06,HGLG11,venda,50,160.00,0,corretora-br,BRL")
    foto = [_pos("PETR4", 100, 30.0), _pos("HGLG11", 50, 155.0, classe="fiis")]
    linhas, divergiu, novos = conferir(ws, _res(posicoes=list(foto)))
    texto = "\n".join(linhas)
    assert divergiu and novos == 0, texto
    assert "HGLG11 (corretora-br): o ledger está zerado em 2026-09-08" in texto, texto
    assert "compra HGLG11 50 155,00" in texto and "abre o livro" not in texto and "evento" not in texto
    antes = _dados(ws)
    with pytest.raises(ValueError, match="não bate com o seu livro"):
        _grava_pos(ws, *foto)
    assert _dados(ws) == antes
    r = gravar(ws, _res(posicoes=list(foto)), aceitar_como="compra", **KW)
    assert r["gravadas"]["fills"] == 1 and r["aberturas"] == 0 and r["implicitos"] == 1
    assert _derivada(ws, "HGLG11") == (50.0, 155.0)
    # foto anterior ao primeiro fill do ticker: o livro de 15/08 não tem VALE3, e a foto diz que tinha
    ws = copia_exemplo(tmp_path / "b")
    _anexa(ws, "dados/ativos.csv", "VALE3,acoes-br")
    _anexa(ws, "dados/fills.csv", "2026-09-06,VALE3,compra,10,60.00,0,corretora-br,BRL")
    foto = [_pos("PETR4", 60, 29.5, data="2026-08-15"), _pos("VALE3", 10, 60.0, data="2026-08-15")]
    linhas, divergiu, _ = conferir(ws, _res(posicoes=list(foto)))
    assert divergiu and "VALE3 (corretora-br): o ledger está zerado em 2026-08-15" in "\n".join(linhas)
    with pytest.raises(ValueError, match="não bate com o seu livro"):
        _grava_pos(ws, *foto)


def test_lotes_do_mesmo_ticker_sao_consolidados_antes_de_comparar_com_o_ledger(tmp_path):
    """Corretora que quebra PETR4 em dois lotes (60 + 40) contra um ledger de 100: uma posição,
    zero divergência. Dois lotes que somam 150 @ 32: UMA divergência, não duas."""
    ws = copia_exemplo(tmp_path)
    iguais = [_pos("PETR4", 60, 30.0), _pos("PETR4", 40, 30.0), _pos("HGLG11", 50, 155.0, classe="fiis")]
    linhas, divergiu, _ = conferir(ws, _res(posicoes=list(iguais)))
    texto = "\n".join(linhas)
    assert not divergiu, texto
    assert texto.count("PETR4 (corretora-br): OK — 100 @ 30,00") == 1, texto
    assert _grava_pos(ws, *iguais)["gravadas"]["fills"] == 0
    lotes = [_pos("PETR4", 100, 30.0), _pos("PETR4", 50, 36.0), _pos("HGLG11", 50, 155.0, classe="fiis")]
    linhas, divergiu, _ = conferir(ws, _res(posicoes=list(lotes)))
    texto = "\n".join(linhas)
    assert divergiu and texto.count("PETR4 (corretora-br):") == 1, texto
    assert "o documento diz 150 @ R$ 32,00" in texto and "preço implícito R$ 36,00" in texto


def test_ticker_suspeito_no_ledger_nao_ganha_segunda_divergencia(tmp_path):
    """Livro com erro nomeado (venda acima do saldo) já tem a frase do validador; empilhar uma
    divergência derivada em cima esconderia a causa. A conferência recusa com a frase do ledger."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/fills.csv", "2026-09-06,PETR4,venda,500,40.00,0,corretora-br,BRL")
    with pytest.raises(ValueError, match="excede o saldo"):
        conferir(ws, _res(posicoes=[_pos("PETR4", 150, 32.0)]))


# --- G3: --aceitar-como compra fecha o ledger pela foto, com o caveat impresso e logado ------

def _derivada(ws, ticker):
    from po.ativos import ler_ativos
    from po.ledger import posicoes_de_fills
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    eventos, _ = ler_csv("eventos", ws / "dados" / "eventos.csv")
    pos, erros = posicoes_de_fills(fills, eventos, ler_ativos(ws)[0])
    assert erros == []
    return next((p["qty"], round(p["pm"], 4)) for p in pos if p["ticker"] == ticker)


def test_aceitar_como_compra_fecha_o_ledger_pela_foto_e_loga_o_caveat(tmp_path):
    """Decisão 14 da spec: o fill implícito (delta de qty, preço implícito, taxa 0) nasce DATADO
    NA FOTO, não na operação, e o custo disso é dito na hora e no log. Depois, a mesma foto
    confere OK: o ledger fechou."""
    from po.ingestao.reconciliacao import CAVEAT_ACEITAR
    ws = copia_exemplo(tmp_path)
    foto = [_pos("PETR4", 150, 32.0, data="2026-09-10"), _pos("HGLG11", 50, 155.0, data="2026-09-10", classe="fiis")]
    r = gravar(ws, _res(posicoes=list(foto)), aceitar_como="compra", **KW)
    assert r["gravadas"]["fills"] == 1 and r["aberturas"] == 0 and r["implicitos"] == 1
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    assert (fills[-1]["data"], fills[-1]["ticker"], fills[-1]["tipo"], fills[-1]["qty"], fills[-1]["preco"], fills[-1]["taxa"]) == \
        ("2026-09-10", "PETR4", "compra", 50.0, 36.0, 0.0)
    assert _derivada(ws, "PETR4") == (150.0, 32.0)
    corpo = r["log"].read_text(encoding="utf-8")
    assert "Fills implícitos aceitos pela foto (--aceitar-como compra): 1" in corpo and CAVEAT_ACEITAR in corpo
    linhas, divergiu, novos = conferir(ws, _res(posicoes=list(foto)))
    assert not divergiu and novos == 0 and "PETR4 (corretora-br): OK — 150 @ 32,00" in "\n".join(linhas)
    _caminho, texto = gerar_estado(ws, hoje=datetime.date(2026, 9, 10))
    assert "Total investido: R$ 14.000,00" in texto, texto     # 150×40 + 50×160: o ESTADO vê o fill
    erros, _ = validar(ws)
    assert erros == []


def test_aceitar_como_compra_recusa_leitura_venda_e_nao_grava_nada(tmp_path):
    """A foto tem preço médio, não preço de venda: a flag não cobre venda. Recusa com a
    explicação e manda registrar.py venda; nada entra, nem a parte que seria compra."""
    ws = copia_exemplo(tmp_path)
    antes = _dados(ws)
    _anexa(ws, "dados/ativos.csv", "VALE3,acoes-br")
    _anexa(ws, "dados/fills.csv", "2026-09-06,VALE3,compra,10,60.00,0,corretora-br,BRL")
    foto = [_pos("PETR4", 150, 32.0, data="2026-09-10"), _pos("VALE3", 4, 60.0, data="2026-09-10"),
            _pos("HGLG11", 50, 155.0, data="2026-09-10", classe="fiis")]
    depois_do_anexo = _dados(ws)
    with pytest.raises(ValueError) as exc:
        gravar(ws, _res(posicoes=list(foto)), aceitar_como="compra", **KW)
    texto = str(exc.value)
    assert "venda VALE3 6 <preco-de-venda>" in texto and "não cobre venda" in texto
    assert _dados(ws) == depois_do_anexo and _dados(ws) != antes
    assert not (ws / "logs" / "importacoes").exists()


def test_aceitar_como_compra_nao_inventa_fill_sem_preco_nem_para_ajuste_de_custo(tmp_path):
    """Custo que cai com quantidade que sobe não tem preço: a flag não fabrica um. Ajuste de
    custo continua nota: nada a gravar."""
    ws = copia_exemplo(tmp_path)
    antes = _dados(ws)
    with pytest.raises(ValueError, match="nenhum preço de compra explica"):
        gravar(ws, _res(posicoes=[_pos("PETR4", 150, 19.0), _pos("HGLG11", 50, 155.0, classe="fiis")]),
               aceitar_como="compra", **KW)
    assert _dados(ws) == antes
    r = gravar(ws, _res(posicoes=[_pos("PETR4", 100, 30.02), _pos("HGLG11", 50, 155.0, classe="fiis")]),
               aceitar_como="compra", **KW)
    assert r["gravadas"]["fills"] == 0 and r["implicitos"] == 0
    assert "Fills implícitos aceitos pela foto (--aceitar-como compra): 0" in r["log"].read_text(encoding="utf-8")


def test_aceitar_como_compra_nao_grava_fill_que_o_livro_recusaria(tmp_path):
    """Revisão do grupo F: HGLG11 abriu com saldo-inicial em 01/08; uma foto de 15/07 aceita como
    compra poria um fill ANTES da abertura, e o validador acusaria o livro logo depois de uma
    gravação que devolveu sucesso. A guarda recusa com a frase do ledger e nada entra."""
    ws = copia_exemplo(tmp_path)
    antes = _dados(ws)
    foto = [_pos("HGLG11", 50, 150.0, data="2026-07-15", classe="fiis")]
    with pytest.raises(ValueError) as exc:
        gravar(ws, _res(posicoes=list(foto)), aceitar_como="compra", **KW)
    assert "deixaria o livro com erro" in str(exc.value) and "vem depois de outros fills" in str(exc.value)
    assert _dados(ws) == antes
    assert not (ws / "logs" / "importacoes").exists()
    erros, _ = validar(ws)
    assert erros == []


def test_aceitar_como_so_aceita_compra(tmp_path):
    ws = copia_exemplo(tmp_path)
    with pytest.raises(ValueError, match="aceitar_como"):
        gravar(ws, _res(posicoes=[_pos("PETR4", 100, 30.0)]), aceitar_como="venda", **KW)
