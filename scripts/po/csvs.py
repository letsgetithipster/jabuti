"""Schemas e leitura validada dos 6 CSVs canônicos do workspace (spec §4)."""
import csv
import re
from pathlib import Path

from po.numeros import parse_valor

SCHEMAS = {
    "posicoes": ["ticker", "classe", "conta", "qty", "pm", "moeda"],
    "cotacoes": ["data", "hora", "ticker", "preco", "moeda", "fonte"],
    "fills": ["data", "ticker", "tipo", "qty", "preco", "taxa", "conta", "moeda"],
    "proventos": ["data", "ticker", "cnpj", "tipo", "valor_bruto", "valor_liquido", "conta", "moeda"],
    "eventos": ["data", "ticker", "tipo", "razao", "confirmado"],
    "indices": ["data", "indice", "valor", "fonte"],
}
NUMERICOS = {"qty", "pm", "preco", "taxa", "valor_bruto", "valor_liquido", "valor"}
CLASSES = {"acoes-br", "fiis", "rv-int", "reits-us", "rf-br", "cripto", "caixa", "commodities"}
TIPOS_FILL = {"compra", "venda"}
DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def ler_csv(nome: str, caminho: str | Path) -> tuple[list[dict], list[str]]:
    """Lê um CSV canônico. Retorna (linhas: list[dict], erros: list[str])."""
    schema = SCHEMAS[nome]
    caminho = Path(caminho)
    erros = []
    with caminho.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != schema:
            return [], [f"{caminho.name}: header {reader.fieldnames} difere do schema (esperado: {schema})"]
        linhas = list(reader)
    for i, linha in enumerate(linhas, start=2):
        onde = f"{caminho.name}:{i}"
        for campo in schema:
            if campo in NUMERICOS and parse_valor(linha[campo]) is None:
                erros.append(f"{onde}: campo {campo} não numérico: {linha[campo]!r}")
            if campo == "data" and not DATA_RE.match(linha[campo]):
                erros.append(f"{onde}: data deve ser YYYY-MM-DD: {linha[campo]!r}")
        if nome == "posicoes" and linha["classe"] not in CLASSES:
            erros.append(f"{onde}: classe {linha['classe']!r} fora do vocabulário {sorted(CLASSES)}")
        if nome == "fills" and linha["tipo"] not in TIPOS_FILL:
            erros.append(f"{onde}: tipo {linha['tipo']!r} deve ser um de {sorted(TIPOS_FILL)}")
    return linhas, erros
