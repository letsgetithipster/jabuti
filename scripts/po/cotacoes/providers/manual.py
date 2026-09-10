"""Provider manual: o usuário colou a cotação (--manual TICKER=PRECO). Fonte gravada como 'manual'."""
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
            if p.ticker in self._valores:
                cotacoes.append(Cotacao(self._data, self._hora, p.ticker, float(self._valores[p.ticker]),
                                        p.moeda, "manual"))
            else:
                falhas.append(f"{p.ticker}: sem valor manual (passe --manual {p.ticker}=PRECO)")
        return cotacoes, falhas
