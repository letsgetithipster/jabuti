"""Parser único de frontmatter YAML. Toda leitura de frontmatter do motor passa aqui."""
import yaml


def extrair_frontmatter(texto):
    """Retorna (meta: dict, corpo: str). Sem frontmatter válido: ({}, texto integral)."""
    if not texto.startswith("---\n"):
        return {}, texto
    fim = texto.find("\n---", 4)
    if fim == -1:
        return {}, texto
    bloco = texto[4:fim]
    corpo = texto[fim + 4:].lstrip("\n")
    try:
        meta = yaml.safe_load(bloco)
    except yaml.YAMLError:
        return {}, texto
    if not isinstance(meta, dict):
        return {}, texto
    return meta, corpo
