"""A diferença entre o seu livro e a foto da corretora, feita conta e nomeada.

Reimportar uma foto era o único erro do produto sem próximo comando: `--conferir` dizia "resolva
antes de importar" (exit 3) e, depois que a tabela de posição morreu, a importação sem `--conferir`
aceitava a foto divergente em silêncio ("Nada novo para gravar", exit 0). Ou o erro mandava fazer
o que a pessoa acabou de fazer, ou não havia erro nenhum.

Aqui a divergência vira conversa: o motor calcula a diferença de quantidade e de custo, deriva o
preço implícito QUANDO ELE EXISTE, nomeia a leitura e entrega o comando de cada saída. Ele não
escolhe — "ele zela, não decide" descido até a camada de dado.

A corretora NUNCA sobrescreve o seu livro, porque é o livro que sustenta o IR: o PM calculado é o
único com procedência (a soma dos fills que o produziram, cada um com log). O PM da corretora é
afirmação de terceiro, e eles divergem legitimamente (taxa somada ao custo, evento societário,
arredondamento exibido).
"""
from dataclasses import dataclass

from po.numeros import formatar_brl, formatar_decimal_brl

# Sem tolerância de satoshi: o ledger arredonda a 8 casas e um satoshi (1e-8) a mais no documento
# é diferença real, não ruído. A tolerância do ledger (1e-6) diz se a posição EXISTE, não se ela
# bate. O 1e-9 só absorve representação binária de float.
TOLERANCIA_QTY = 1e-9
TOLERANCIA_PM = 0.005     # meio centavo: PM exibido com 2 casas contra PM cheio do livro
LEITURAS = ("igual", "compra", "venda", "ajuste-de-custo")
# O custo de --aceitar-como compra (decisão 14 da spec), dito na hora e gravado no log: uma casa só.
CAVEAT_ACEITAR = ("o fill nasce datado na foto, não na operação; para IR preciso, importe o extrato "
                  "de negociações")


@dataclass(frozen=True)
class Diferenca:
    delta_qty: float
    delta_custo: float
    preco_implicito: float | None
    leitura: str


def fill_implicito(qty_ledger: float, pm_ledger: float,
                   qty_doc: float, pm_doc: float) -> Diferenca:
    """O que teria que ter acontecido para o livro virar a foto.

    `preco_implicito` só existe na leitura `compra` e só quando o custo SUBIU: em venda, a foto
    traz PM e não preço de venda, e o quociente devolveria o próprio PM do livro — um número com
    cara de conferido que contaminaria o IR. Quantidade que entra com custo que não sobe não tem
    preço que a explique, e devolver o quociente daria preço zero ou negativo.
    """
    dq = round(qty_doc - qty_ledger, 8)
    dc = round(qty_doc * pm_doc - qty_ledger * pm_ledger, 2)
    if abs(dq) <= TOLERANCIA_QTY:
        if abs(pm_doc - pm_ledger) <= TOLERANCIA_PM:
            return Diferenca(0.0, 0.0, None, "igual")
        return Diferenca(0.0, dc, None, "ajuste-de-custo")
    if dq > 0:
        return Diferenca(dq, dc, round(dc / dq, 4) if dc > 0 else None, "compra")
    return Diferenca(dq, dc, None, "venda")


def _q(v: float) -> str:
    return formatar_decimal_brl(v)


def explicar(dif: Diferenca, *, ticker: str, conta: str, data: str, qty_ledger: float,
             pm_ledger: float, qty_doc: float, pm_doc: float,
             registrar: str = "python <motor>/scripts/registrar.py .",
             importar: str | None = None) -> list[str]:
    """As linhas que a pessoa lê. Todo ramo termina num comando que EXISTE, ou em "nada a fazer".
    Nenhum ramo termina mandando fazer o que ela acabou de fazer. Quantidade e preço em pt-BR,
    inclusive dentro do comando: registrar.py lê 0,25 e 36,00.

    `importar` é o comando de importação que a pessoa acabou de rodar; com ele, a leitura `compra`
    com preço implícito ganha a terceira saída, `--aceitar-como compra`, com o caveat na mesma
    linha. Sem ele (chamador sem CLI de importação) a saída não é oferecida: comando que não dá
    para digitar não é saída."""
    if dif.leitura == "igual":
        return []
    cab = [f"  {ticker} ({conta}): o ledger tem {_q(qty_ledger)} @ R$ {formatar_brl(pm_ledger)} "
           f"em {data}; o documento diz {_q(qty_doc)} @ R$ {formatar_brl(pm_doc)}."]
    if dif.leitura == "ajuste-de-custo":
        return cab + [
            f"    A quantidade bate e o custo não: diferença de R$ {formatar_brl(dif.delta_custo)}."
            " Isso nunca vira fill — costuma ser taxa que a corretora não soma ao custo, ou"
            " arredondamento de exibição. O seu livro tem a procedência; nada a fazer."]
    sinal = "+" if dif.delta_qty > 0 else "-"
    unidades = f"{sinal}{_q(abs(dif.delta_qty))} unidade(s) por R$ {formatar_brl(dif.delta_custo)}"
    if dif.leitura == "venda":
        return cab + [
            f"    A diferença é {unidades}. A foto traz preço médio, não preço de venda, então o"
            " motor não inventa o preço. Nada foi gravado.",
            "    Se foi venda que você ainda não registrou:",
            f"      {registrar} venda {ticker} {_q(abs(dif.delta_qty))} <preco-de-venda> "
            "--data <data-da-venda>",
            "    Se o documento é de outra conta ou de outro período, corrija o arquivo e rode de"
            " novo."]
    linhas = cab + [f"    A diferença é {unidades}" + (
        f", ou seja, preço implícito R$ {formatar_brl(dif.preco_implicito)}."
        if dif.preco_implicito is not None else
        ". Entraram unidades e o custo não subiu: nenhum preço de compra explica isso — confira o"
        " documento antes de registrar qualquer coisa."), "    Nada foi gravado."]
    if dif.preco_implicito is not None:
        linhas += [
            "    Se foi compra que você ainda não registrou:",
            f"      {registrar} compra {ticker} {_q(dif.delta_qty)} "
            f"{formatar_brl(dif.preco_implicito)} --data <data-da-compra>",
            "    Se foi evento societário (split, grupamento, bonificação), o preço implícito não"
            " significa nada — registre o evento:",
            f"      {registrar} evento {ticker} split --razao <novas:antigas> --data <data> "
            "--confirmar"]
        if importar:
            linhas += ["    Se você confia na foto e não tem a data da compra:",
                       f"      {importar} --aceitar-como compra",
                       f"      ({CAVEAT_ACEITAR})"]
    linhas.append("    Depois, rode esta importação de novo: ela passa quando o livro e o"
                  " documento concordarem.")
    return linhas
