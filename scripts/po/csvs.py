"""Schemas e leitura validada dos 6 CSVs canônicos do workspace (spec §4).

Contrato: os CSVs canônicos são escritos por máquina, então número aceita SÓ
o formato canônico (-?d+(.d+)?, decimal com ponto, sem separador de milhar).
Formato humano/corretora (1.234,56) é assunto da ingestão (Fase 2), que
converte ANTES de gravar aqui. Campos NUMERICOS voltam como float nas linhas
retornadas: a conversão string→número acontece em um lugar só.
Se erros != [], não consuma linhas.
"""
import csv
import datetime
import re
from pathlib import Path

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
NUMERO_CANONICO = re.compile(r"^-?\d+(\.\d+)?$")
# Campos de texto que podem ficar vazios; todo o resto é obrigatório
OPCIONAIS = {
    "proventos": {"cnpj"},
    "eventos": {"razao"},
}


def ler_csv(nome: str, caminho: str | Path) -> tuple[list[dict], list[str]]:
    """Lê um CSV canônico. Retorna (linhas, erros); NUMERICOS já convertidos a float."""
    schema = SCHEMAS[nome]
    opcionais = OPCIONAIS.get(nome, set())
    caminho = Path(caminho)
    erros = []
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != schema:
            return [], [f"{caminho.name}: header {reader.fieldnames} difere do schema (esperado: {schema})"]
        linhas = list(reader)
    for i, linha in enumerate(linhas, start=2):
        onde = f"{caminho.name}:{i}"
        extras = linha.pop(None, None)
        if extras:
            erros.append(f"{onde}: linha com colunas a mais ({len(extras)} valor(es) além do schema)")
        faltantes = [c for c in schema if linha[c] is None]
        if faltantes:
            erros.append(f"{onde}: linha com colunas a menos (faltam: {', '.join(faltantes)})")
            continue
        for campo in schema:
            valor = linha[campo]
            if valor != valor.strip():
                erros.append(f"{onde}: campo {campo} com espaço nas bordas: {valor!r}")
            if not valor:
                if campo not in opcionais:
                    erros.append(f"{onde}: campo {campo} vazio")
                continue
            if campo in NUMERICOS:
                if not NUMERO_CANONICO.match(valor):
                    erros.append(
                        f"{onde}: campo {campo} fora do formato canônico "
                        f"(decimal com ponto, sem milhar): {valor!r}")
                else:
                    linha[campo] = float(valor)
            elif campo == "data":
                if not DATA_RE.match(valor):
                    erros.append(f"{onde}: data deve ser YYYY-MM-DD: {valor!r}")
                else:
                    try:
                        datetime.date.fromisoformat(valor)
                    except ValueError:
                        erros.append(f"{onde}: data impossível no calendário: {valor!r}")
        if nome == "posicoes" and linha["classe"] not in CLASSES:
            erros.append(f"{onde}: classe {linha['classe']!r} fora do vocabulário {sorted(CLASSES)}")
        if nome == "fills" and linha["tipo"] not in TIPOS_FILL:
            erros.append(f"{onde}: tipo {linha['tipo']!r} deve ser um de {sorted(TIPOS_FILL)}")
    return linhas, erros
