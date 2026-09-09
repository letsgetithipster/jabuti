"""Parser determinístico de datas vindas de documentos de corretora (ingestão).

Nunca adivinha formato: o mapeamento declara a lista de formatos strptime, na
ordem de tentativa. Célula de xlsx que já é datetime/date passa direto.
"""
import datetime
import re


def parse_data(valor: object, formatos: list[str], extrair: str | None = None) -> datetime.date | None:
    """Converte célula/texto em date; None se não casar nenhum formato.

    extrair: regex com exatamente UM grupo de captura (ValueError se não tiver),
    aplicado antes do parse (ex.: '^(\\S+)' pega '08/11/2026' de
    '08/11/2026 as of 08/10/2026'). Datetime com fuso usa .date() no próprio
    fuso, sem conversão. Int/float (serial do Excel) retornam None.
    """
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    if not isinstance(valor, str) or not valor.strip():
        return None
    texto = valor.strip()
    if extrair:
        try:
            padrao = re.compile(extrair)
        except re.error as e:
            raise ValueError(f"extrair {extrair!r}: regex inválida ({e})") from e
        if padrao.groups != 1:
            raise ValueError(f"extrair {extrair!r} precisa de exatamente um grupo de captura")
        m = padrao.search(texto)
        if not m:
            return None
        texto = m.group(1)
    for fmt in formatos:
        try:
            return datetime.datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None
