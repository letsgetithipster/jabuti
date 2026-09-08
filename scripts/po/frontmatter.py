r"""Parser único de frontmatter YAML. Toda leitura de frontmatter do motor passa aqui."""
import re

import yaml

# Delimitadores tolerantes a CRLF; fechamento exige linha exatamente "---"
# (com espaços/tabs finais opcionais). Não-greedy: para no PRIMEIRO fechamento,
# então "---" de régua horizontal mais adiante no corpo não é engolido.
_DELIMITADO = re.compile(r"---\r?\n(.*?)(?:\r?\n)---[ \t]*(?:\r?\n|$)", re.DOTALL)


def extrair_frontmatter(texto: str) -> tuple[dict, str]:
    """Retorna (meta: dict, corpo: str). Sem frontmatter válido: ({}, texto integral).

    Tolera CRLF nos delimitadores e dentro do bloco (PyYAML aceita).
    Data YAML não-aspada vira datetime.date — contrato pinado em teste.
    """
    m = _DELIMITADO.match(texto)
    if not m:
        return {}, texto
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}, texto
    if not isinstance(meta, dict):
        return {}, texto
    return meta, texto[m.end():].lstrip("\r\n")
