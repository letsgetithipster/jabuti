"""Confere o Total investido do ESTADO.md contra a valoração da carteira.

O recálculo NÃO mora aqui: ele mora em `po/carteira.py`, que é o mesmo cálculo que o gerador de
ESTADO e o cockpit usam. Enquanto este check tinha implementação própria, ela não conhecia câmbio
e se desligava inteira na primeira posição não-BRL — justo a carteira que a ingestão da Fase 2
passou a habilitar — e qualquer correção na valoração não chegava aqui.
"""
import re
from pathlib import Path

from po.carteira import valorar
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
    try:
        conteudo = estado.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return ["estado/ESTADO.md: não é UTF-8 válido — salve o arquivo como UTF-8"], []
    m = TOTAL_RE.search(conteudo)
    if not m:
        return ["estado/ESTADO.md: linha 'Total investido:' ausente"], []
    total_declarado = parse_valor(m.group(1))
    if total_declarado is None:
        return [f"estado/ESTADO.md: Total investido não numérico: {m.group(1)!r}"], []

    try:
        total = valorar(raiz).total_brl
    except (FileNotFoundError, ValueError) as e:
        # A valoração recusa número parcial: falta de cotação, de câmbio, dados/ sujo. O check de
        # dados é quem nomeia a causa de origem; aqui a consequência é só suspender o total.
        avisos.append(f"ESTADO: check do total suspenso — {e}")
        return erros, avisos
    if abs(total - total_declarado) > TOLERANCIA:
        erros.append(
            f"estado/ESTADO.md: Total investido {m.group(1).strip()} difere do "
            f"recalculado R$ {formatar_brl(total)} (posicoes × última cotação × câmbio)")
    return erros, avisos
