"""Ledger cronológico de fills por (ticker, conta): saldo de quantidade e preço médio.

Ordem: data, depois tipo (saldo-inicial e compra antes de venda no mesmo dia), depois
ordem do arquivo. `compra` e `saldo-inicial` somam custo (qty × preço + taxa); `venda`
baixa ao PM corrente (taxa de venda não altera PM) e não pode exceder o saldo daquele
momento. A abertura (`saldo-inicial`) é única e vem antes de tudo na chave. Quem usa:
check_dados (qty e PM contra posicoes.csv) e a ingestão (posição importada nasce com
saldo-inicial).
"""
from dataclasses import dataclass

TOLERANCIA_QTY = 1e-6
_ORDEM_TIPO = {"saldo-inicial": 0, "compra": 1, "venda": 2}


@dataclass
class Saldo:
    qty: float = 0.0
    custo: float = 0.0

    @property
    def pm(self) -> float:
        return self.custo / self.qty if self.qty > TOLERANCIA_QTY else 0.0


def calcular_saldos(fills: list[dict]) -> tuple[dict[tuple[str, str], Saldo], list[str], set[tuple[str, str]]]:
    """Retorna ({(ticker, conta): Saldo}, erros, chaves suspeitas). Fills já validados (floats).

    Chave em 'chaves suspeitas' tem saldo derivado não confiável: quem compara contra
    posicoes.csv suspende a comparação em vez de somar um segundo erro derivado.
    """
    saldos: dict[tuple[str, str], Saldo] = {}
    erros: list[str] = []
    suspeitas: set[tuple[str, str]] = set()
    aberturas: set[tuple[str, str]] = set()
    ordenados = sorted(enumerate(fills),
                       key=lambda par: (par[1]["data"], _ORDEM_TIPO.get(par[1]["tipo"], 9), par[0]))
    for _, f in ordenados:
        chave = (f["ticker"], f["conta"])
        tipo = f["tipo"]
        if tipo in ("compra", "saldo-inicial"):
            if tipo == "saldo-inicial":
                if chave in aberturas:
                    erros.append(f"fills.csv: {f['ticker']} tem mais de um saldo-inicial na conta "
                                 f"{f['conta']} — a posição herdada abre uma vez só (o resto são compras)")
                    suspeitas.add(chave)
                    continue
                if chave in saldos:
                    erros.append(f"fills.csv: saldo-inicial de {f['ticker']} em {f['data']} vem depois de "
                                 f"outros fills na conta {f['conta']} — a abertura é o primeiro evento da posição")
                    suspeitas.add(chave)
                    continue
                aberturas.add(chave)
            s = saldos.setdefault(chave, Saldo())
            s.custo += f["qty"] * f["preco"] + f["taxa"]
            s.qty += f["qty"]
        elif tipo == "venda":
            s = saldos.get(chave)      # nunca cria entrada no caminho de erro
            disponivel = s.qty if s else 0.0
            if s is None or f["qty"] > disponivel + TOLERANCIA_QTY:
                erros.append(
                    f"fills.csv: venda de {f['qty']:g} {f['ticker']} em {f['data']} excede o saldo "
                    f"na conta {f['conta']} ({disponivel:g}) — confira a ordem cronológica ou registre "
                    "um saldo-inicial anterior")
                suspeitas.add(chave)
                continue
            s.custo -= f["qty"] * s.pm
            s.qty -= f["qty"]
            if s.qty <= TOLERANCIA_QTY:
                s.qty, s.custo = 0.0, 0.0
        else:
            erros.append(f"fills.csv: tipo de fill desconhecido {tipo!r} em {f['ticker']} ({f['data']}) — "
                         "o ledger não sabe o efeito dessa linha no saldo")
            suspeitas.add(chave)
    return saldos, erros, suspeitas
