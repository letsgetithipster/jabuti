r"""Parser determinístico de números em formato pt-BR e US.

Regras (na ordem):
1. Remove espaços em qualquer posição (cobre milhar com espaço: "1 234,56"),
   prefixo de moeda (R$/US$/$) no início, com sinal opcional antes OU depois
   dele (`-R$ 5,00` e `R$ -5,00` valem), e um "%" no final.
   Percentual retorna valor de face: "-3,5%" -> -3.5.
2. Dois separadores presentes: o mais à direita é o decimal (o agrupamento
   do outro separador não é validado; leniência deliberada).
3. Um separador: se casa o padrão exato de grupos de milhar
   (1.234 / 12.345.678), é milhar; senão é decimal. Sinal (+/-) antes do
   número não impede o reconhecimento do milhar.
   Caveat: decimal-com-ponto de exatamente 3 casas ("12.345") é lido como
   milhar; coluna que precise disso deve tratar no chamador.
4. Só resultado final estritamente numérico ([+-]?\d+(\.\d+)?) é aceito:
   nan/inf/notação científica/underscore retornam None.
"""
import re

_ESPACOS = re.compile(r"[\s ]+")
_MOEDA_PREFIXO = re.compile(r"^([+-]?)(r\$|us\$|\$)", re.IGNORECASE)   # preserva o sinal (grupo 1)
_MILHAR_PONTO = re.compile(r"^[+-]?\d{1,3}(\.\d{3})+$")
_MILHAR_VIRGULA = re.compile(r"^[+-]?\d{1,3}(,\d{3})+$")
_NUMERO_FINAL = re.compile(r"[+-]?\d+(\.\d+)?")


def parse_valor(texto: object) -> float | None:
    """Converte texto numérico pt-BR/US em float. Retorna None se não numérico."""
    if not texto or not isinstance(texto, str):
        return None
    t = _ESPACOS.sub("", texto)
    t = _MOEDA_PREFIXO.sub(r"\1", t)
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


def formatar_brl(valor: float) -> str:
    """Formata em pt-BR: 12345.6 -> '12.345,60'."""
    return f"{valor:,.2f}".translate(str.maketrans(",.", ".,"))


def formatar_canonico(valor: float, casas: int = 4) -> str:
    """Número no formato canônico dos CSVs: decimal com ponto, sem milhar, sem zeros à direita.

    Único caminho número→string de quem grava em dados/ (cotações, ingestão).
    """
    texto = f"{valor:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return "0" if texto in ("", "-0") else texto
