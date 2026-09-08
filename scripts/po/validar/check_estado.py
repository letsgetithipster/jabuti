"""Confere o Total investido do ESTADO.md contra posicoes × última cotação."""
import re
from pathlib import Path

from po.csvs import ler_csv
from po.numeros import formatar_brl, parse_valor

TOTAL_RE = re.compile(r"^Total investido:\s*(.+)$", re.MULTILINE)
TOLERANCIA = 0.05


def checar_estado(raiz: str | Path) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos). Dado ausente/sujo suspende o check do total com aviso
    (o check de dados é quem acusa o problema de origem)."""
    raiz = Path(raiz)
    erros, avisos = [], []
    estado = raiz / "estado" / "ESTADO.md"
    if not estado.exists():
        return ["estado/ESTADO.md ausente"], []
    m = TOTAL_RE.search(estado.read_text(encoding="utf-8-sig"))
    if not m:
        return ["estado/ESTADO.md: linha 'Total investido:' ausente"], []
    total_declarado = parse_valor(m.group(1))
    if total_declarado is None:
        return [f"estado/ESTADO.md: Total investido não numérico: {m.group(1)!r}"], []

    csv_pos = raiz / "dados" / "posicoes.csv"
    csv_cot = raiz / "dados" / "cotacoes.csv"
    if not csv_pos.exists() or not csv_cot.exists():
        avisos.append("ESTADO: check do total suspenso — dados/ incompleto (ver check de dados)")
        return erros, avisos
    posicoes, errs_p = ler_csv("posicoes", csv_pos)
    cotacoes, errs_c = ler_csv("cotacoes", csv_cot)
    if errs_p or errs_c:
        avisos.append("ESTADO: check do total suspenso — dados/ com erros (ver check de dados)")
        return erros, avisos

    melhor = {}
    for c in cotacoes:  # vence a data mais recente; empate: última linha do arquivo
        if c["ticker"] not in melhor or c["data"] >= melhor[c["ticker"]]["data"]:
            melhor[c["ticker"]] = c

    nao_brl = sorted({p["ticker"] for p in posicoes if p["moeda"] != "BRL"} |
                     {c["ticker"] for c in melhor.values() if c["moeda"] != "BRL"})
    if nao_brl:
        avisos.append(
            f"ESTADO: check do total suspenso — moeda não-BRL em {nao_brl} "
            "(consolidação multi-moeda chega com o fechar-mes)")
        return erros, avisos

    total, completo = 0.0, True
    for p in posicoes:
        linha_cot = melhor.get(p["ticker"])
        preco = linha_cot["preco"] if linha_cot else None
        if preco is None:
            avisos.append(f"ESTADO: {p['ticker']} sem cotação — check do total suspenso")
            completo = False
            continue
        total += p["qty"] * preco
    if completo and abs(total - total_declarado) > TOLERANCIA:
        erros.append(
            f"estado/ESTADO.md: Total investido {m.group(1).strip()} difere do "
            f"recalculado R$ {formatar_brl(total)} (posicoes × última cotação)")
    return erros, avisos
