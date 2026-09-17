"""A fila do aporte: quanto vai para cada bloco, pela política que a pessoa declarou.

Porta, linha a linha, as fórmulas que existiam SÓ como fórmula de Excel na aba Aporte do cockpit
(célula editável Aporte!B2, RANK/SUMIFS):

    gap      = MAX(0, alvo/100 × (total + aporte) − atual)
    ordem    = gap decrescente
    sugerido = MAX(0, MIN(gap, sobra))

Existe para que o número que move dinheiro não saia da cabeça de um modelo, e para que ele possa
ser confrontado por teste — na planilha ele não podia: openpyxl com data_only=True devolve None
em toda célula de fórmula.

Os três modos são as três alternativas da camada 4 do GUARDRAILS CALCULADAS, não narradas. Quem
escolhe é a pessoa, e a escolha vira log de decisão.

Isto EXECUTA uma política declarada. Não é recomendação de investimento, não ranqueia ativo e não
olha para preço: o v1 decide o BLOCO, nunca o ticker.
"""
from dataclasses import dataclass

MODOS = ("cascata", "concentrar", "proporcional")


@dataclass
class Sugestao:
    bloco: str
    atual: float
    alvo: float
    gap: float
    sugerido: float = 0.0


def distribuir(por_bloco: dict[str, float], bandas, aporte: float,
               modo: str = "cascata") -> tuple[list[Sugestao], float]:
    """(sugestões por gap decrescente, sobra). Bloco sem banda declarada não entra na fila: a
    banda é a política, e sem política não há alvo a perseguir — `carteira.valorar` já avisa.

    Aporte zero é uso legítimo e devolve gap calculado com sugestão zerada: é o mês em que não
    se aportou, com o mesmo comando e nenhum nome novo a memorizar.
    """
    if modo not in MODOS:
        raise ValueError(f"modo de distribuição desconhecido: {modo!r} — use um de {list(MODOS)}")
    if aporte < 0:
        raise ValueError(f"aporte não pode ser negativo: {aporte!r}")
    base = sum(por_bloco.values()) + aporte
    itens = [Sugestao(b.bloco, por_bloco.get(b.bloco, 0.0), b.alvo,
                      round(max(0.0, b.alvo / 100 * base - por_bloco.get(b.bloco, 0.0)), 2))
             for b in bandas]
    itens.sort(key=lambda i: (-i.gap, i.bloco))
    sobra = round(aporte, 2)
    if modo == "proporcional":
        soma = round(sum(i.gap for i in itens), 2)
        for i in itens:
            if soma <= 0:
                break
            i.sugerido = round(min(i.gap, aporte * i.gap / soma), 2)
            sobra = round(sobra - i.sugerido, 2)
        # O centavo que a divisão deixa vai para o bloco mais fora, e só se couber no gap dele:
        # sobra de arredondamento que some é dinheiro que ninguém aloca e ninguém vê.
        if sobra > 0 and itens and itens[0].gap - itens[0].sugerido >= sobra:
            itens[0].sugerido = round(itens[0].sugerido + sobra, 2)
            sobra = 0.0
        return itens, sobra
    for i in (itens[:1] if modo == "concentrar" else itens):
        i.sugerido = round(max(0.0, min(i.gap, sobra)), 2)
        sobra = round(sobra - i.sugerido, 2)
    return itens, sobra
