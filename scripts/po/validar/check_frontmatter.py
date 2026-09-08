"""Checa frontmatter dos .md do workspace: vocabulário fechado, datas, aliases."""
from pathlib import Path

from po.frontmatter import extrair_frontmatter

TIPOS = {
    "perfil", "alocacao", "frameworks", "rituais",
    "tese", "tese-semente", "watchlist",
    "estado", "setup", "foto",
    "log-aporte", "log-venda", "log-decisao", "log-revisao",
}
# 'data' é chave legítima nos logs; os aliases herdados do vault ficam proibidos:
ALIASES_PROIBIDOS = {"criado", "atualizado", "ultima-revisao"}
PASTAS_COM_MD = ["politica", "teses", "watchlist", "estado", "logs"]
IGNORADOS = {"README.md"}


def checar_frontmatter(raiz: str | Path) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos) sobre os .md do workspace."""
    raiz = Path(raiz)
    erros, avisos = [], []
    for pasta in PASTAS_COM_MD:
        base = raiz / pasta
        if not base.exists():
            continue
        for md in sorted(base.rglob("*.md")):
            if md.name in IGNORADOS:
                continue
            rel = md.relative_to(raiz).as_posix()
            meta, _ = extrair_frontmatter(md.read_text(encoding="utf-8"))
            if not meta:
                erros.append(f"{rel}: sem frontmatter válido")
                continue
            tipo = meta.get("tipo")
            if tipo not in TIPOS:
                erros.append(f"{rel}: tipo {tipo!r} fora do vocabulário")
            usados = ALIASES_PROIBIDOS & set(meta)
            if usados:
                erros.append(f"{rel}: chave alias proibida {sorted(usados)} — use data-criacao/data-revisao")
            if tipo == "tese-semente" and meta.get("validada") is not False:
                erros.append(f"{rel}: tese-semente exige validada: false (para validar, vire tipo: tese)")
            nota = meta.get("nota-final")
            if tipo == "tese" and (isinstance(nota, bool) or not isinstance(nota, (int, float))):
                erros.append(f"{rel}: tese exige nota-final numérica")
    return erros, avisos
