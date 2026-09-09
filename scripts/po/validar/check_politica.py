"""Checa a política declarada: bandas coerentes e alvos somando 100."""
from pathlib import Path

from po.csvs import CLASSES
from po.politica import ler_bandas

TOLERANCIA_SOMA = 0.01


def checar_politica(raiz: str | Path) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos). Tabela vazia é aviso (o /definir-macro preenche)."""
    bandas, erros = ler_bandas(raiz)
    if erros:
        return erros, []
    if not bandas:
        return [], ["politica: nenhuma banda declarada ainda (o /definir-macro preenche a tabela)"]
    vistos = set()
    for b in bandas:
        if b.bloco not in CLASSES:
            erros.append(f"politica: bloco {b.bloco!r} fora do vocabulário {sorted(CLASSES)}")
        if b.bloco in vistos:
            erros.append(f"politica: bloco {b.bloco!r} duplicado na tabela de bandas")
        vistos.add(b.bloco)
        if not (0 <= b.minimo <= b.alvo <= b.maximo <= 100):
            erros.append(f"politica: {b.bloco} exige 0 ≤ mín ≤ alvo ≤ máx ≤ 100 "
                         f"(lido: {b.minimo:g}/{b.alvo:g}/{b.maximo:g})")
    soma = sum(b.alvo for b in bandas)
    if abs(soma - 100) > TOLERANCIA_SOMA:
        erros.append(f"politica: alvos somam {soma:g}%, devem somar 100%")
    return erros, []
