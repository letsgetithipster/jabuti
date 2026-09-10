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
    linhas = conferir(ws, res)
    texto = "\n".join(linhas)
    assert "PETR4 (corretora-br): OK" in texto and "VALE3 (corretora-br): NOVA" in texto
    assert "HGLG11 (corretora-br): só em dados/" in texto
    assert "proventos: 0 nova(s), 1 já presente(s)" in texto
    assert (ws / "dados" / "posicoes.csv").read_text(encoding="utf-8") == antes
