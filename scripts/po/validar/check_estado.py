"""Confere o Total investido do ESTADO.md contra posicoes × última cotação."""
import re
from pathlib import Path

from po.csvs import ler_csv
from po.numeros import parse_valor

TOTAL_RE = re.compile(r"Total investido:\s*(.+)")
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

    ultima = {}
    for c in cotacoes:  # arquivo é append-only: a última linha do ticker é a mais recente
        ultima[c["ticker"]] = c["preco"]

    total, completo = 0.0, True
    for p in posicoes:
        preco = ultima.get(p["ticker"])
        if preco is None:
            avisos.append(f"ESTADO: {p['ticker']} sem cotação — check do total suspenso")
            completo = False
            continue
        total += p["qty"] * preco
    if completo and abs(total - total_declarado) > TOLERANCIA:
        erros.append(
            f"estado/ESTADO.md: Total investido R$ {total_declarado:,.2f} difere do "
            f"recalculado R$ {total:,.2f} (posicoes × última cotação)")
    return erros, avisos
