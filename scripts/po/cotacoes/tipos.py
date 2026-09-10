"""Tipos canônicos de cotação. Cotacao espelha a linha de cotacoes.csv."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Pedido:
    ticker: str
    classe: str   # classe de posicoes.csv, ou "cambio" para pares como USDBRL
    moeda: str    # moeda ESPERADA da cotação (a da posição; BRL para câmbio)


@dataclass(frozen=True)
class Cotacao:
    data: str
    hora: str
    ticker: str
    preco: float
    moeda: str
    fonte: str

    def como_linha(self) -> dict:
        return {"data": self.data, "hora": self.hora, "ticker": self.ticker,
                "preco": self.preco, "moeda": self.moeda, "fonte": self.fonte}


class SemRede(Exception):
    """Rede indisponível: quem chama PARA e declara; nada é gravado."""


class RespostaInvalida(Exception):
    """A fonte respondeu, mas sem cotação utilizável (HTTP 4xx/5xx, JSON estranho)."""


class ProviderCotacoes(Protocol):
    nome: str

    def cotar(self, pedidos: list[Pedido]) -> tuple[list[Cotacao], list[str]]:
        """Retorna (cotações obtidas, falhas em pt-BR, uma por pedido não atendido).
        Levanta SemRede se a rede caiu — nunca devolve preço parcial nesse caso."""
        ...


def pedidos_de_posicoes(posicoes: list[dict]) -> list[Pedido]:
    """Um pedido por (ticker, moeda) das posições + um par de câmbio por moeda ≠ BRL."""
    vistos, pedidos = set(), []
    for p in posicoes:
        chave = (p["ticker"], p["moeda"])
        if chave not in vistos:
            vistos.add(chave)
            pedidos.append(Pedido(p["ticker"], p["classe"], p["moeda"]))
    for moeda in sorted({p["moeda"] for p in posicoes if p["moeda"] != "BRL"}):
        pedidos.append(Pedido(f"{moeda}BRL", "cambio", "BRL"))
    return pedidos
