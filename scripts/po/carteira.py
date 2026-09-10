"""Valoração da carteira a partir de dados/: posição × cotação vencedora × câmbio, em BRL.

Cálculo único, usado pelo gerador de ESTADO e pelo cockpit — o mesmo número nos dois.
Falta de cotação ou de câmbio é ValueError acionável: número parcial não sai daqui.
"""
from dataclasses import dataclass
from pathlib import Path

from po.csvs import ler_csv, ultimas_cotacoes
from po.politica import Banda, ler_bandas


@dataclass
class Linha:
    ticker: str
    classe: str
    conta: str
    qty: float
    pm: float
    moeda: str
    preco: float
    moeda_cotacao: str
    data_cotacao: str
    fonte: str
    cambio_cotacao: float   # moeda da cotação → BRL (1.0 se BRL)
    cambio_posicao: float   # moeda da posição → BRL (1.0 se BRL)

    @property
    def valor_brl(self) -> float:
        return self.qty * self.preco * self.cambio_cotacao

    @property
    def custo_brl(self) -> float:
        return self.qty * self.pm * self.cambio_posicao


@dataclass
class Carteira:
    linhas: list[Linha]
    bandas: list[Banda]
    total_brl: float
    por_bloco: dict[str, float]          # todo bloco com banda OU com posição
    data_cotacao_mais_antiga: str | None
    avisos: list[str]


def _ler(nome: str, raiz: Path) -> list[dict]:
    linhas, erros = ler_csv(nome, raiz / "dados" / f"{nome}.csv")
    if erros:
        raise ValueError(f"dados/{nome}.csv com erros — corrija antes (rode o validador): {erros[0]}")
    return linhas


def valorar(raiz: str | Path) -> Carteira:
    raiz = Path(raiz)
    posicoes = _ler("posicoes", raiz)
    cotacoes = _ler("cotacoes", raiz)
    bandas, erros = ler_bandas(raiz)
    if erros:
        raise ValueError(erros[0])
    ultimas = ultimas_cotacoes(cotacoes)

    def cambio(moeda: str) -> float:
        if moeda == "BRL":
            return 1.0
        par = ultimas.get(f"{moeda}BRL")
        if par is None:
            raise ValueError(f"posição em {moeda} sem câmbio {moeda}BRL em cotacoes.csv — rode "
                             f"scripts/atualizar_cotacoes.py (ou --manual {moeda}BRL=TAXA)")
        return par["preco"]

    linhas = []
    for p in posicoes:
        c = ultimas.get(p["ticker"])
        if c is None:
            raise ValueError(f"{p['ticker']} sem cotação em cotacoes.csv — rode scripts/atualizar_cotacoes.py "
                             f"(ou --manual {p['ticker']}=PRECO)")
        linhas.append(Linha(p["ticker"], p["classe"], p["conta"], p["qty"], p["pm"], p["moeda"],
                            c["preco"], c["moeda"], c["data"], c["fonte"], cambio(c["moeda"]), cambio(p["moeda"])))
    por_bloco = {b.bloco: 0.0 for b in bandas}
    for l in linhas:
        por_bloco[l.classe] = por_bloco.get(l.classe, 0.0) + l.valor_brl
    total = sum(l.valor_brl for l in linhas)
    com_banda = {b.bloco for b in bandas}
    avisos = [f"{bloco} tem posição mas nenhuma banda declarada (defina no /definir-macro)"
              for bloco in sorted(por_bloco) if bloco not in com_banda]
    mais_antiga = min((l.data_cotacao for l in linhas), default=None)
    return Carteira(linhas, bandas, total, por_bloco, mais_antiga, avisos)
