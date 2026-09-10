"""Provider manual: o usuário colou a cotação (--manual TICKER=PRECO). Fonte gravada como 'manual'."""
import math

from po.cotacoes.tipos import Cotacao, Pedido


class ManualProvider:
    nome = "manual"

    def __init__(self, valores: dict[str, float], data: str, hora: str = "00:00"):
        self._valores = valores
        self._data = data
        self._hora = hora

    def cotar(self, pedidos: list[Pedido]) -> tuple[list[Cotacao], list[str]]:
        cotacoes, falhas = [], []
        for p in pedidos:
            if p.ticker not in self._valores:
                falhas.append(f"{p.ticker}: sem valor manual (passe --manual {p.ticker}=PRECO)")
                continue
            preco = float(self._valores[p.ticker])
            if not math.isfinite(preco) or preco <= 0:
                falhas.append(f"{p.ticker}: valor manual inválido ({self._valores[p.ticker]!r}) — "
                              "o preço tem que ser positivo")
                continue
            cotacoes.append(Cotacao(self._data, self._hora, p.ticker, preco, p.moeda, "manual"))
        return cotacoes, falhas
