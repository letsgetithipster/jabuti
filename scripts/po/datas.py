"""Parser determinístico de datas vindas de documentos de corretora (ingestão).

Nunca adivinha formato: o mapeamento declara a lista de formatos strptime, na
ordem de tentativa. Célula de xlsx que já é datetime/date passa direto.
"""
import datetime
import re


def parse_data(valor: object, formatos: list[str], extrair: str | None = None) -> datetime.date | None:
    """Converte célula/texto em date; None se não casar nenhum formato.

    extrair: regex com UM grupo aplicado antes do parse (ex.: '^(\\S+)' pega
    '08/11/2026' de '08/11/2026 as of 08/10/2026').
    """
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    if not isinstance(valor, str) or not valor.strip():
        return None
    texto = valor.strip()
    if extrair:
        m = re.search(extrair, texto)
        if not m or not m.groups():
            return None
        texto = m.group(1)
    for fmt in formatos:
        try:
            return datetime.datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None
