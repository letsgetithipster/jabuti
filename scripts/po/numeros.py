"""Parser determinístico de números em formato pt-BR e US.

Regras (na ordem):
1. Remove espaços em qualquer posição (cobre milhar com espaço: "1 234,56"),
   prefixo de moeda (R$/US$/$) no início e um "%" no final.
   Percentual retorna valor de face: "-3,5%" -> -3.5.
2. Dois separadores presentes: o mais à direita é o decimal (o agrupamento
   do outro separador não é validado; leniência deliberada).
3. Um separador: se casa o padrão exato de grupos de milhar
   (1.234 / 12.345.678), é milhar; senão é decimal.
   Caveat: decimal-com-ponto de exatamente 3 casas ("12.345") é lido como
   milhar; coluna que precise disso deve tratar no chamador.
4. Só resultado final estritamente numérico ([+-]?\d+(\.\d+)?) é aceito:
   nan/inf/notação científica/underscore retornam None.
"""
import re

_ESPACOS = re.compile(r"[\s ]+")
_MOEDA_PREFIXO = re.compile(r"^(r\$|us\$|\$)", re.IGNORECASE)
_MILHAR_PONTO = re.compile(r"^-?\d{1,3}(\.\d{3})+$")
_MILHAR_VIRGULA = re.compile(r"^-?\d{1,3}(,\d{3})+$")
_NUMERO_FINAL = re.compile(r"[+-]?\d+(\.\d+)?")


def parse_valor(texto: object) -> float | None:
    """Converte texto numérico pt-BR/US em float. Retorna None se não numérico."""
    if not texto or not isinstance(texto, str):
        return None
    t = _ESPACOS.sub("", texto)
    t = _MOEDA_PREFIXO.sub("", t)
    if t.endswith("%"):
        t = t[:-1]
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
    if not _NUMERO_FINAL.fullmatch(t):
        return None
    return float(t)
