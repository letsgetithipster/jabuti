"""Parser determinístico de números em formato pt-BR e US.

Regras (na ordem):
1. Remove prefixo de moeda (R$/US$/$), sufixo %, espaços.
2. Dois separadores presentes: o mais à direita é o decimal.
3. Um separador: se casa o padrão exato de grupos de milhar
   (1.234 / 12.345.678), é milhar; senão é decimal.
"""
import re

_LIMPA = re.compile(r"(r\$|us\$|\$|%|\s|\u00a0)", re.IGNORECASE)
_MILHAR_PONTO = re.compile(r"^-?\d{1,3}(\.\d{3})+$")
_MILHAR_VIRGULA = re.compile(r"^-?\d{1,3}(,\d{3})+$")


def parse_valor(texto):
    """Converte texto numérico pt-BR/US em float. Retorna None se não numérico."""
    if not texto or not isinstance(texto, str):
        return None
    t = _LIMPA.sub("", texto.strip())
    if not t:
        return None
    tem_ponto, tem_virgula = "." in t, "," in t
    if tem_ponto and tem_virgula:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif tem_virgula:
        t = t.replace(",", "") if _MILHAR_VIRGULA.match(t) else t.replace(",", ".")
    elif tem_ponto and _MILHAR_PONTO.match(t):
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None
