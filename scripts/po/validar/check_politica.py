"""Checa a política declarada: bandas coerentes e alvos somando 100."""
from pathlib import Path

from po.csvs import CLASSES, em_vocabulario
from po.politica import ler_bandas

TOLERANCIA_SOMA = 0.05   # pior caso de arredondamento a 2 casas em até 8 blocos é 0,04; comparação sobre diff arredondado, sem ruído de float


def checar_politica(raiz: str | Path) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos). Tabela vazia é aviso (o /definir-macro preenche)."""
    bandas, erros = ler_bandas(raiz)
    if erros and not bandas:
        return erros, []      # não deu para ler a tabela: o resto dos checks não teria o que dizer
    if not bandas:
        return [], ["politica: nenhuma banda declarada ainda (o /definir-macro preenche a tabela)"]
    for b in bandas:   # bloco duplicado é acusado pelo ler_bandas, uma casa só: o gerador de
        if not em_vocabulario(b.bloco, CLASSES):   # ESTADO lê por lá e precisa recusar antes de gravar
            erros.append(f"politica: bloco {b.bloco!r} fora do vocabulário {sorted(CLASSES)}")
        if not (0 <= b.minimo <= b.alvo <= b.maximo <= 100):
            erros.append(f"politica: {b.bloco} exige 0 ≤ mín ≤ alvo ≤ máx ≤ 100 "
                         f"(lido: {b.minimo:g}/{b.alvo:g}/{b.maximo:g})")
    soma = sum(b.alvo for b in bandas)
    if round(abs(soma - 100), 6) > TOLERANCIA_SOMA:
        erros.append(f"politica: alvos somam {soma:g}%, devem somar 100%")
    return erros, []
