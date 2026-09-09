"""Ledger cronológico de fills por (ticker, conta): saldo de quantidade e preço médio.

Ordem: data, depois ordem do arquivo. `compra` e `saldo-inicial` somam custo
(qty × preço + taxa); `venda` baixa ao PM corrente (taxa de venda não altera
PM) e não pode exceder o saldo daquele momento. Quem usa: check_dados (qty e
PM contra posicoes.csv) e a ingestão (posição importada nasce com saldo-inicial).
"""
from dataclasses import dataclass

TOLERANCIA_QTY = 1e-6


@dataclass
class Saldo:
    qty: float = 0.0
    custo: float = 0.0

    @property
    def pm(self) -> float:
        return self.custo / self.qty if self.qty > TOLERANCIA_QTY else 0.0


def calcular_saldos(fills: list[dict]) -> tuple[dict[tuple[str, str], Saldo], list[str]]:
    """Retorna ({(ticker, conta): Saldo}, erros). Fills já validados (floats)."""
    saldos: dict[tuple[str, str], Saldo] = {}
    erros = []
    ordenados = sorted(enumerate(fills), key=lambda par: (par[1]["data"], par[0]))
    for _, f in ordenados:
        s = saldos.setdefault((f["ticker"], f["conta"]), Saldo())
        if f["tipo"] in ("compra", "saldo-inicial"):
            s.custo += f["qty"] * f["preco"] + f["taxa"]
            s.qty += f["qty"]
        else:  # venda
            if f["qty"] > s.qty + TOLERANCIA_QTY:
                erros.append(
                    f"fills.csv: venda de {f['qty']:g} {f['ticker']} em {f['data']} excede o saldo "
                    f"na conta {f['conta']} ({s.qty:g}) — confira a ordem cronológica ou registre "
                    "um saldo-inicial anterior")
                continue
            s.custo -= f["qty"] * s.pm
            s.qty -= f["qty"]
            if s.qty <= TOLERANCIA_QTY:
                s.qty, s.custo = 0.0, 0.0
    return saldos, erros
