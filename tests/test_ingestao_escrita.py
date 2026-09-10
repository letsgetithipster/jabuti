import datetime

import pytest

from po.csvs import ler_csv
from po.frontmatter import extrair_frontmatter
from po.ingestao.engine import Resultado
from po.ingestao.escrita import conferir, gravar
from po.validar import validar
from test_validar_dados import copia_exemplo


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


def _pos(ticker, qty, pm, data="2026-09-01", classe="acoes-br", conta="corretora-br"):
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


def test_posicao_nova_nasce_com_saldo_inicial_e_valida(tmp_path):
    ws = copia_exemplo(tmp_path)
    pos = {"ticker": "VALE3", "classe": "acoes-br", "conta": "corretora-br", "qty": 10.0, "pm": 60.0, "moeda": "BRL",
           "_data": "2026-08-01"}
    r = gravar(ws, _res(posicoes=[pos]), mapeamento="m", arquivo="p.csv", conciliacao="x", conta="corretora-br")
    assert r["gravadas"] == {"posicoes": 1, "fills": 1, "proventos": 0, "eventos": 0}
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    assert fills[-1]["tipo"] == "saldo-inicial" and fills[-1]["preco"] == 60.0 and fills[-1]["data"] == "2026-08-01"
    erros, _ = validar(ws)
    assert erros == ["cotacoes.csv: VALE3 sem nenhuma cotação — rode scripts/atualizar_cotacoes.py (ou passe --manual VALE3=PRECO)"]


def test_posicao_igual_e_duplicada_sem_saldo_inicial(tmp_path):
    ws = copia_exemplo(tmp_path)
    pos = {"ticker": "PETR4", "classe": "acoes-br", "conta": "corretora-br", "qty": 100.0, "pm": 30.0, "moeda": "BRL",
           "_data": "2026-09-01"}
    r = gravar(ws, _res(posicoes=[pos]), mapeamento="m", arquivo="p.csv", conciliacao="x", conta="corretora-br")
    assert r["gravadas"]["posicoes"] == 0 and r["gravadas"]["fills"] == 0 and r["duplicadas"]["posicoes"] == 1


def test_posicao_divergente_e_conflito_sem_gravar_nada(tmp_path):
    ws = copia_exemplo(tmp_path)
    antes = (ws / "dados" / "posicoes.csv").read_text(encoding="utf-8")
    pos = {"ticker": "PETR4", "classe": "acoes-br", "conta": "corretora-br", "qty": 120.0, "pm": 30.0, "moeda": "BRL",
           "_data": "2026-09-01"}
    with pytest.raises(ValueError, match="conflito"):
        gravar(ws, _res(posicoes=[pos], proventos=[_prov("2026-10-05", "HGLG11", 1.0)]),
               mapeamento="m", arquivo="p.csv", conciliacao="x", conta="corretora-br")
    assert (ws / "dados" / "posicoes.csv").read_text(encoding="utf-8") == antes
    prov, _ = ler_csv("proventos", ws / "dados" / "proventos.csv")
    assert len(prov) == 1


def test_dados_sujos_bloqueiam_importacao(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "fills.csv").write_text("data,ticker\n", encoding="utf-8")
    with pytest.raises(ValueError, match="corrija antes de importar"):
        gravar(ws, _res(proventos=[_prov("2026-10-05", "HGLG11", 1.0)]), mapeamento="m", arquivo="a", conciliacao="x", conta="corretora-br")


def test_conferir_compara_sem_gravar(tmp_path):
    ws = copia_exemplo(tmp_path)
    antes = (ws / "dados" / "posicoes.csv").read_text(encoding="utf-8")
    res = _res(posicoes=[
        {"ticker": "PETR4", "classe": "acoes-br", "conta": "corretora-br", "qty": 100.0, "pm": 30.0, "moeda": "BRL", "_data": "2026-09-01"},
        {"ticker": "VALE3", "classe": "acoes-br", "conta": "corretora-br", "qty": 10.0, "pm": 60.0, "moeda": "BRL", "_data": "2026-09-01"},
    ], proventos=[_prov("2026-09-05", "HGLG11", 55.00)])
    linhas, divergiu = conferir(ws, res)
    texto = "\n".join(linhas)
    assert divergiu is True   # HGLG11 está em dados/ e não no documento
    assert "PETR4 (corretora-br): OK" in texto and "VALE3 (corretora-br): NOVA" in texto
    assert "HGLG11 (corretora-br): só em dados/" in texto
    assert "proventos: 0 nova(s), 1 já presente(s)" in texto
    assert (ws / "dados" / "posicoes.csv").read_text(encoding="utf-8") == antes


def test_conferir_sem_divergencia_nao_diverge(tmp_path):
    """A prévia usa o mesmo `separar` da gravação: sem divergência de posição, `divergiu` é
    False mesmo havendo lançamento novo a gravar (novo não é divergente)."""
    ws = copia_exemplo(tmp_path)
    res = _res(posicoes=[_pos("PETR4", 100, 30.0), _pos("HGLG11", 50, 155.0, classe="fiis")],
               proventos=[_prov("2026-10-05", "HGLG11", 56.00)])
    linhas, divergiu = conferir(ws, res)
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


# --- gravação parcial e a abertura que ficou faltando ---------------------------------------

def _falha_em_fills(monkeypatch):
    """Trava anexar_csv na tabela fills: a gravação já escreveu posicoes e morre no meio,
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
    with pytest.raises(OSError):
        gravar(ws, _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")]), **KW)
    logs = sorted((ws / "logs" / "importacoes").glob("*.md"))
    assert len(logs) == 1
    corpo = logs[0].read_text(encoding="utf-8")
    assert "**A gravação falhou no meio**" in corpo
    assert "| posicoes | 1 | 0 |" in corpo and "| fills | 0 | 0 |" in corpo
    posicoes, _ = ler_csv("posicoes", ws / "dados" / "posicoes.csv")
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    assert any(p["ticker"] == "VALE3" for p in posicoes)      # entrou o que o log nomeia
    assert not any(f["ticker"] == "VALE3" for f in fills)     # e só isso


def test_rodada_seguinte_completa_o_saldo_inicial_que_faltou(tmp_path, monkeypatch):
    """Sem isto o ledger ficava permanentemente sem abertura: a posição já existia, a rodada
    seguinte a via como duplicada e o saldo-inicial nunca nascia."""
    ws = copia_exemplo(tmp_path)
    _falha_em_fills(monkeypatch)
    with pytest.raises(OSError):
        gravar(ws, _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")]), **KW)
    monkeypatch.undo()
    r = gravar(ws, _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")]), **KW)
    assert r["gravadas"]["posicoes"] == 0 and r["duplicadas"]["posicoes"] == 1
    assert r["gravadas"]["fills"] == 1
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    abertura = [f for f in fills if f["ticker"] == "VALE3"]
    assert len(abertura) == 1
    assert abertura[0]["tipo"] == "saldo-inicial" and abertura[0]["qty"] == 20.0 and abertura[0]["preco"] == 60.0


def test_ticker_com_fill_no_documento_nao_ganha_abertura_sintetica(tmp_path):
    ws = copia_exemplo(tmp_path)
    res = _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")],
               fills=[_fill("2026-09-10", "VALE3", 20, 60.00)])
    r = gravar(ws, res, **KW)
    assert r["gravadas"] == {"posicoes": 1, "fills": 1, "proventos": 0, "eventos": 0}
    fills, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    assert [f["tipo"] for f in fills if f["ticker"] == "VALE3"] == ["compra"]


def test_ticker_com_fill_em_dados_nao_ganha_abertura_sintetica(tmp_path):
    ws = copia_exemplo(tmp_path)
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8")
                     + "2026-09-10,VALE3,compra,20,60.00,0,corretora-br,BRL\n", encoding="utf-8")
    r = gravar(ws, _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")]), **KW)
    assert r["gravadas"]["posicoes"] == 1 and r["gravadas"]["fills"] == 0
    lidos, _ = ler_csv("fills", ws / "dados" / "fills.csv")
    assert [f["tipo"] for f in lidos if f["ticker"] == "VALE3"] == ["compra"]


def test_workspace_continua_valido_depois_da_parcial_e_da_rodada_que_completou(tmp_path, monkeypatch):
    """Fim de linha do caminho de recuperação: o ledger fecha e o validador não acha nada.
    A cotação e o ESTADO são trabalho de outras skills, não da escrita — aqui entram à mão
    só para o check do total ter o que conferir."""
    ws = copia_exemplo(tmp_path)
    _falha_em_fills(monkeypatch)
    with pytest.raises(OSError):
        gravar(ws, _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")]), **KW)
    monkeypatch.undo()
    gravar(ws, _res(posicoes=[_pos("VALE3", 20, 60.0, data="2026-09-10")]), **KW)
    cot = ws / "dados" / "cotacoes.csv"
    cot.write_text(cot.read_text(encoding="utf-8") + "2026-09-09,18:00,VALE3,62.00,BRL,manual\n",
                   encoding="utf-8")
    estado = ws / "estado" / "ESTADO.md"        # 100×40 + 50×160 + 20×62
    estado.write_text(estado.read_text(encoding="utf-8").replace("R$ 12.000,00", "R$ 13.240,00"),
                      encoding="utf-8")
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
