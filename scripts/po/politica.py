"""Leitura da política declarada: tabela 'Bandas por bloco' de politica/01-alocacao-alvo.md.

Parser único, compartilhado pelo validador (check_politica) e pelo cockpit.
Formato esperado (escrito pelo /definir-macro, Fase 3, ou à mão):

    ## Bandas por bloco

    | Bloco | Mín % | Alvo % | Máx % |
    |---|---|---|---|
    | acoes-br | 25 | 35 | 45 |
"""
import re
from dataclasses import dataclass
from pathlib import Path

from po.numeros import parse_valor

ARQUIVO = "politica/01-alocacao-alvo.md"
_SECAO = re.compile(r"^## Bandas por bloco[ \t]*\r?$", re.MULTILINE)


@dataclass(frozen=True)
class Banda:
    bloco: str
    minimo: float
    alvo: float
    maximo: float


def _celulas(linha: str) -> list[str]:
    return [c.strip() for c in linha.strip().strip("|").split("|")]


def ler_bandas(raiz: str | Path) -> tuple[list[Banda], list[str]]:
    """Retorna (bandas, erros). Tabela sem linhas = ([], []) — política ainda não declarada."""
    caminho = Path(raiz) / ARQUIVO
    if not caminho.exists():
        return [], [f"{ARQUIVO} ausente"]
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return [], [f"{ARQUIVO}: não é UTF-8 válido — salve o arquivo como UTF-8"]
    m = _SECAO.search(texto)
    if not m:
        return [], [f"{ARQUIVO}: seção '## Bandas por bloco' ausente"]
    linhas = texto[m.end():].splitlines()
    i = 0
    while i < len(linhas) and not linhas[i].strip():
        i += 1
    if (i + 1 >= len(linhas) or not linhas[i].lstrip().startswith("|")
            or not linhas[i + 1].lstrip().startswith("|")):
        return [], [f"{ARQUIVO}: tabela de bandas ausente logo após a seção (header + separador)"]
    bandas, erros = [], []
    for n, linha in enumerate(linhas[i + 2:], start=1):
        if not linha.lstrip().startswith("|"):
            break
        celulas = _celulas(linha)
        if len(celulas) != 4:
            erros.append(f"{ARQUIVO}: linha {n} da tabela de bandas com {len(celulas)} colunas "
                         "(esperado 4: bloco, mín, alvo, máx)")
            continue
        bloco, *nums = celulas
        valores = [parse_valor(v) for v in nums]
        if any(v is None for v in valores):
            erros.append(f"{ARQUIVO}: bloco {bloco!r} com valor não numérico: {nums}")
            continue
        bandas.append(Banda(bloco, *valores))
    # O check_politica já acusava bloco duplicado, mas só ele: o gerador de ESTADO lê por aqui e
    # percorria a lista na ordem, então o bloco repetido saía duas vezes na tabela e a soma dela
    # passava do "Total investido" impresso logo acima — no arquivo que o cabeçalho diz ser gerado
    # e confiável. Acusar na leitura faz a valoração recusar antes de gravar. Mesma frase do check.
    vistos, ja_avisados = set(), set()
    for b in bandas:
        if b.bloco in vistos and b.bloco not in ja_avisados:
            erros.append(f"{ARQUIVO}: bloco {b.bloco!r} duplicado na tabela de bandas")
            ja_avisados.add(b.bloco)
        vistos.add(b.bloco)
    return bandas, erros
