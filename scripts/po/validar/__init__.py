"""Runner do validador: agrega todos os checks sobre um workspace."""
from pathlib import Path

from po.validar.check_dados import checar_dados
from po.validar.check_estado import checar_estado
from po.validar.check_frontmatter import checar_frontmatter

CHECKS = [checar_frontmatter, checar_dados, checar_estado]


def validar(raiz: str | Path) -> tuple[list[str], list[str]]:
    """Roda todos os checks. Retorna (erros, avisos) agregados."""
    raiz = Path(raiz)
    if not raiz.exists():
        return [f"workspace {raiz} não existe"], []
    erros, avisos = [], []
    for check in CHECKS:
        e, a = check(raiz)
        erros.extend(e)
        avisos.extend(a)
    return erros, avisos
