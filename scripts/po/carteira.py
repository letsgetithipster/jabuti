"""Valoração da carteira a partir de dados/: posição × cotação vencedora × câmbio, em BRL.

Cálculo único, usado pelo gerador de ESTADO e pelo cockpit — o mesmo número nos dois.
Falta de cotação ou de câmbio é ValueError acionável: número parcial não sai daqui.
"""
import datetime
from dataclasses import dataclass
from pathlib import Path

from po.csvs import ler_csv, ultimas_cotacoes
from po.politica import Banda, ler_bandas

# Cotação velha não é erro (o mercado pode estar fechado, o ativo pode ser ilíquido), mas virar
# patrimônio de hoje sem uma palavra é. Um número só, aqui, para não haver dois limiares no repo.
DIAS_COTACAO_VELHA = 7


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
        """Custo remarcado ao câmbio CORRENTE, não a base fiscal. Para posição em moeda
        estrangeira o BRL que saiu da conta foi o da data de cada fill, e a diferença é
        valorização cambial. Quem for mostrar rentabilidade em tela precisa resolver isso
        antes (item aberto da Task 14); aqui o campo existe para comparação em moeda única."""
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


def valorar(raiz: str | Path, hoje: datetime.date | None = None) -> Carteira:
    raiz = Path(raiz)
    hoje = hoje or datetime.date.today()
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
        usados_cambio[f"{moeda}BRL"] = par
        return par["preco"]

    usados_cambio: dict[str, dict] = {}
    linhas = []
    for p in posicoes:
        c = ultimas.get(p["ticker"])
        if c is None:
            raise ValueError(f"{p['ticker']} sem cotação em cotacoes.csv — rode scripts/atualizar_cotacoes.py "
                             f"(ou --manual {p['ticker']}=PRECO)")
        if c["moeda"] != p["moeda"]:
            # O validador também pega isto, mas o gerador de ESTADO grava antes de alguém rodar o
            # validador: sem esta guarda, uma cotação de AAPL digitada em BRL vira valor 5× errado
            # no arquivo que a casa lê primeiro. Mesma disciplina do _checar_moeda_unica do cotador.
            raise ValueError(f"{p['ticker']}: cotação em {c['moeda']} mas a posição está em "
                             f"{p['moeda']} — corrija cotacoes.csv (rode o validador)")
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
    avisos += _avisos_de_idade(linhas, usados_cambio, hoje)
    return Carteira(linhas, bandas, total, por_bloco, mais_antiga, avisos)


def _avisos_de_idade(linhas, usados_cambio, hoje: datetime.date) -> list[str]:
    """Cotação e câmbio velhos viram aviso nomeando o ticker e a idade. Antes a data mais antiga
    era só impressa no ESTADO, sem pendência e sem erro: um preço de 2019 virava patrimônio de hoje
    com o validador verde."""
    def idade(iso: str) -> int:
        return (hoje - datetime.date.fromisoformat(iso)).days

    velhas = sorted({(l.ticker, l.data_cotacao) for l in linhas if idade(l.data_cotacao) > DIAS_COTACAO_VELHA})
    avisos = []
    if velhas:
        quais = ", ".join(f"{t} ({d}, {idade(d)} dias)" for t, d in velhas)
        avisos.append(f"cotação com mais de {DIAS_COTACAO_VELHA} dias em {len(velhas)} ativo(s): {quais} "
                      "— rode scripts/atualizar_cotacoes.py antes de decidir aporte")
    for par, c in sorted(usados_cambio.items()):
        if idade(c["data"]) > DIAS_COTACAO_VELHA:
            avisos.append(f"câmbio {par} de {c['data']} ({idade(c['data'])} dias) convertendo preço de "
                          "hoje — rode scripts/atualizar_cotacoes.py")
    return avisos
