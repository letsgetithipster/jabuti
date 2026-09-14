r"""Parser determinístico de números NO FORMATO DECLARADO pelo chamador (pt-BR ou en-US).

O formato nunca é adivinhado: ver `parse_valor` para o porquê e para as regras de
separador. Regras de limpeza, comuns aos dois formatos (na ordem):
1. Remove espaços em qualquer posição (cobre milhar com espaço: "1 234,56"),
   prefixo de moeda (R$/US$/$) no início, com sinal opcional antes OU depois
   dele (`-R$ 5,00` e `R$ -5,00` valem), e um "%" no final.
   Percentual retorna valor de face: "-3,5%" -> -3.5.
2. Só resultado final estritamente numérico ([+-]?\d+(\.\d+)?) é aceito:
   nan/inf/notação científica/underscore retornam None.

Três formatadores, públicos diferentes: `formatar_brl` é dinheiro para humanos
(pt-BR, 2 casas); `formatar_decimal_brl` é quantidade para humanos (pt-BR, até N casas, sem
zeros à direita); `formatar_canonico` é para dados/ (deve satisfazer csvs.NUMERO_CANONICO).
"""
import math
import re

FORMATOS_NUMERO = ("pt-BR", "en-US")

_ESPACOS = re.compile(r"[\s ]+")
_MOEDA_PREFIXO = re.compile(r"^([+-]?)(r\$|us\$|\$)", re.IGNORECASE)   # preserva o sinal (grupo 1)
_NUMERO_FINAL = re.compile(r"[+-]?\d+(\.\d+)?")
_DECIMAL = {"pt-BR": ",", "en-US": "."}
_GRUPO = {"pt-BR": ".", "en-US": ","}
# Agrupamento BEM FORMADO: primeiro grupo de 1 a 3 dígitos sem zero à esquerda, depois grupos de
# exatamente 3. É a única condição em que o separador de grupo vira milhar. Fora dela ele é lido
# como o decimal do outro formato, que é o que export real traz o tempo todo (10750.00 num CSV
# brasileiro). A leniência é do PONTO em pt-BR e da VÍRGULA em en-US; o decimal do formato
# declarado nunca vira milhar, e é isso que mata 0,030 -> 30,0.
_MILHAR = {
    "pt-BR": re.compile(r"^[+-]?[1-9]\d{0,2}(\.\d{3})+$"),
    "en-US": re.compile(r"^[+-]?[1-9]\d{0,2}(,\d{3})+$"),
}


def parse_valor(texto: object, *, formato: str = "pt-BR") -> float | None:
    """Converte texto numérico para float NO FORMATO DECLARADO. None se não for numérico nele.

    O formato nunca é adivinhado. Documento de corretora declara o seu em `numeros:` no
    mapeamento (validar_mapeamento exige a chave); o default pt-BR vale para número que a pessoa
    digita e para texto que o próprio motor gerou, porque o produto é pt-BR por desenho.

    Regras, na ordem: remove espaços (cobre milhar com espaço), prefixo de moeda com sinal antes
    ou depois, e um '%' final (percentual volta como face: '-3,5%' -> -3.5). Depois, o separador
    decimal do formato manda: à direita dele não pode haver outro separador; à esquerda, o
    separador de grupo só é aceito se o agrupamento for bem formado. Sem decimal na string, o
    separador de grupo é milhar se bem formado, e o decimal do outro formato se não for.
    """
    if formato not in FORMATOS_NUMERO:
        raise ValueError(f"formato de número desconhecido: {formato!r} — "
                         f"use um de {list(FORMATOS_NUMERO)}")
    if not texto or not isinstance(texto, str):
        return None
    t = _ESPACOS.sub("", texto)
    t = _MOEDA_PREFIXO.sub(r"\1", t)
    if t.endswith("%"):
        t = t[:-1]
    if not t:
        return None
    decimal, grupo = _DECIMAL[formato], _GRUPO[formato]
    if decimal in t:
        inteiro, _, resto = t.partition(decimal)
        if decimal in resto or grupo in resto:
            return None
        if grupo in inteiro and not _MILHAR[formato].match(inteiro):
            return None
        t = inteiro.replace(grupo, "") + "." + resto
    elif grupo in t:
        t = t.replace(grupo, "") if _MILHAR[formato].match(t) else t.replace(grupo, ".")
    if not _NUMERO_FINAL.fullmatch(t):
        return None
    return float(t)


def formatar_brl(valor: float) -> str:
    """Formata em pt-BR: 12345.6 -> '12.345,60'."""
    return f"{valor:,.2f}".translate(str.maketrans(",.", ".,"))


def formatar_decimal_brl(valor: float, casas: int = 8) -> str:
    """Número em pt-BR com ATÉ `casas` casas, sem zeros à direita: 0.03 -> '0,03', 1500.0 -> '1.500'.

    É o formatador de QUANTIDADE para humano, e o terceiro porque os outros dois não servem aqui:
    `formatar_brl` fixa 2 casas e some com cripto (1 satoshi viraria '0,00'), `formatar_canonico`
    é exato mas escreve o decimal com ponto, que não é pt-BR. Nunca notação científica: `:g` daria
    '1e-08' para um satoshi e '1.23457e+06' para um milhão, numa mensagem que manda a pessoa
    repetir exatamente o número.
    """
    texto = f"{valor:,.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.translate(str.maketrans(",.", ".,"))


def formatar_canonico(valor: float, casas: int = 8) -> str:
    """Número no formato canônico dos CSVs: decimal com ponto, sem milhar, sem zeros à direita.

    Único caminho número→string de quem grava em dados/ (cotações, ingestão); o resultado
    sempre satisfaz csvs.NUMERO_CANONICO. 8 casas cobrem satoshi e fator diário de CDI.
    Nunca zera em silêncio: valor não-nulo que arredonda a zero é ValueError, assim como
    nan/inf (cotação ausente se pula, não se grava).
    Quem calcula arredonda antes (`round(v, casas)`); este writer não arredonda por você,
    então poeira aritmética (ex.: 0.3-0.1-0.2) levanta ValueError de propósito.
    """
    if not math.isfinite(valor):
        raise ValueError(f"formatar_canonico: valor não finito ({valor!r}) — cotação ausente se pula, não se grava")
    texto = f"{valor:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    if texto in ("0", "-0"):
        if valor != 0:
            raise ValueError(f"formatar_canonico: {valor!r} arredondado a zero com {casas} casas — aumente casas")
        return "0"
    return texto
