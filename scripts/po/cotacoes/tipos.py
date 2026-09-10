"""Tipos canônicos de cotação e a derivação dos pedidos a partir de posicoes.csv."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Pedido:
    ticker: str
    classe: str   # classe de posicoes.csv, ou "cambio" para pares como USDBRL
    moeda: str    # moeda ESPERADA da cotação (a da posição; BRL para câmbio)


SEM_MERCADO = {"rf-br"}


def e_codigo_b3(ticker: str) -> bool:
    """Código da B3 carrega dígito (PETR4, HGLG11, IVVB11, AAPL34, OZ1D); papel americano é
    só letra (AAPL, GLD, O)."""
    return any(ch.isdigit() for ch in ticker)


def sem_cotacao_de_mercado(p: Pedido) -> bool:
    """Não é papel negociado: RF privada/tesouro (classe rf-br), ou saldo em conta (classe
    caixa sem código da B3 — um fundo de caixa listado, tipo AUPO11, tem cotação).

    Política do INSTRUMENTO, não de um provider: mora aqui pra que todo provider importe as
    duas metades da decisão (classe e forma do ticker) do mesmo lugar.
    """
    return p.classe in SEM_MERCADO or (p.classe == "caixa" and not e_codigo_b3(p.ticker))


def falha_nao_negociado(ticker: str, classe: str) -> str:
    return f"{ticker}: não é papel negociado ({classe}) — passe --manual {ticker}=VALOR"


# Existem para manter a FORMA uniforme entre providers; a dica é a parte que cada fonte sobrescreve.
def falha_preco(ticker: str, fonte: str, preco, alvo: str = "",
                dica: str = "ativo suspenso ou deslistado? confira o ticker") -> str:
    """Shape uniforme entre providers; a DICA é a parte que cada fonte sobrescreve."""
    return (f"{ticker}: {fonte} devolveu preço inválido ({preco!r})"
            + (f" para {alvo}" if alvo else "")
            + (f" — {dica}" if dica else ""))


def falha_moeda(ticker: str, fonte: str, obtida: str, esperada: str) -> str:
    return (f"{ticker}: {fonte} devolveu {obtida}, esperado {esperada} (moeda da posição) "
            "— confira o ticker")


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
        Levanta SemRede se a rede caiu — nunca devolve preço parcial nesse caso: as
        cotações já coletadas na chamada são descartadas, porque quem chama grava tudo
        de uma vez só no final."""
        ...


def pedidos_de_posicoes(posicoes: list[dict]) -> list[Pedido]:
    """Um pedido por (ticker, moeda) das posições + um par de câmbio por moeda ≠ BRL.
    A chave de dedup é (ticker, moeda): o mesmo ticker classificado de formas diferentes
    em duas contas mantém a primeira classe, e um ticker literalmente chamado USDBRL
    colidiria com o par sintetizado."""
    vistos, pedidos = set(), []
    for p in posicoes:
        chave = (p["ticker"], p["moeda"])
        if chave not in vistos:
            vistos.add(chave)
            pedidos.append(Pedido(p["ticker"], p["classe"], p["moeda"]))
    for moeda in sorted({p["moeda"] for p in posicoes if p["moeda"] != "BRL"}):
        pedidos.append(Pedido(f"{moeda}BRL", "cambio", "BRL"))
    return pedidos
