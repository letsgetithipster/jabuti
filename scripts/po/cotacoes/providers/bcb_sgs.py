"""Provider BCB/SGS: PTAX (USDBRL) e séries de indexadores (CDI, Selic, IPCA).

Fonte diária sem hora: grava hora 00:00 (convenção a documentar no mapeamentos/README e no
LEIAME do cockpit quando eles nascerem). cotar() atende só USDBRL; serie() é consumida pelo
fechar-mes (Fase 5).
"""
import datetime
import math

from po.cotacoes.http import buscar_json
from po.cotacoes.tipos import Cotacao, Pedido, RespostaInvalida, falha_preco

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json"
SERIES = {"usdbrl": 1, "cdi": 12, "selic": 11, "ipca": 433}   # 1 = dólar venda PTAX, diário


class BcbSgsProvider:
    nome = "bcb-sgs"

    def __init__(self, buscar=buscar_json):
        self._buscar = buscar

    def serie(self, codigo: int, n: int = 1) -> list[tuple[str, float]]:
        """Últimos n pontos da série: [(data ISO, valor)]. RespostaInvalida se o shape não é o do
        SGS ou se algum valor não é finito (o SGS manda número como string dentro do JSON, então
        o parse_constant do http nunca vê um NaN/Infinity nela — a checagem tem que ser feita aqui)."""
        d = self._buscar(URL.format(codigo=codigo, n=n))
        if not isinstance(d, list) or not d:
            raise RespostaInvalida(f"série {codigo}: resposta sem pontos")
        pontos = []
        for ponto in d:
            try:
                data = datetime.datetime.strptime(ponto["data"], "%d/%m/%Y").date().isoformat()
                valor = float(ponto["valor"])
            except (KeyError, TypeError, ValueError) as e:
                raise RespostaInvalida(f"série {codigo}: ponto ilegível {ponto!r}") from e
            if not math.isfinite(valor):
                raise RespostaInvalida(f"série {codigo}: valor não finito em {ponto!r}")
            pontos.append((data, valor))
        return pontos

    def cotar(self, pedidos: list[Pedido]) -> tuple[list[Cotacao], list[str]]:
        cotacoes, falhas = [], []
        for p in pedidos:
            if p.classe != "cambio" or p.ticker != "USDBRL":
                falhas.append(f"{p.ticker}: bcb-sgs cobre só USDBRL (PTAX) e indexadores — use yahoo")
                continue
            try:
                data, valor = self.serie(SERIES["usdbrl"], 1)[-1]
            except RespostaInvalida as e:
                falhas.append(f"{p.ticker}: bcb-sgs não devolveu PTAX ({e})")
                continue
            if valor <= 0:
                falhas.append(falha_preco(p.ticker, "bcb-sgs", valor,
                                          dica="a fonte publicou um valor que não serve como taxa"))
                continue
            cotacoes.append(Cotacao(data, "00:00", p.ticker, valor, p.moeda, "bcb-sgs"))
        return cotacoes, falhas
