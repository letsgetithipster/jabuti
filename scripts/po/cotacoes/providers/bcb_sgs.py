"""Provider BCB/SGS: PTAX (USDBRL) e séries de indexadores (CDI, Selic, IPCA).

Fonte diária sem hora: grava hora 00:00 (convenção documentada em mapeamentos/README e
no LEIAME do cockpit). cotar() atende só USDBRL; serie() é consumida pelo fechar-mes (Fase 4).
"""
import datetime
import math

from po.cotacoes.http import buscar_json
from po.cotacoes.tipos import Cotacao, Pedido, RespostaInvalida

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json"
SERIES = {"usdbrl": 1, "cdi": 12, "selic": 11, "ipca": 433}   # 1 = dólar venda PTAX, diário


class BcbSgsProvider:
    nome = "bcb-sgs"

    def __init__(self, buscar=buscar_json):
        self._buscar = buscar

    def serie(self, codigo: int, n: int = 1) -> list[tuple[str, float]]:
        """Últimos n pontos da série: [(data ISO, valor)]. RespostaInvalida se o shape não é o do SGS."""
        d = self._buscar(URL.format(codigo=codigo, n=n))
        if not isinstance(d, list) or not d:
            raise RespostaInvalida(f"série {codigo}: resposta sem pontos")
        pontos = []
        for ponto in d:
            try:
                data = datetime.datetime.strptime(ponto["data"], "%d/%m/%Y").date().isoformat()
                pontos.append((data, float(ponto["valor"])))
            except (KeyError, TypeError, ValueError) as e:
                raise RespostaInvalida(f"série {codigo}: ponto ilegível {ponto!r}") from e
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
                falhas.append(f"USDBRL: bcb-sgs não devolveu PTAX ({e})")
                continue
            if not math.isfinite(valor) or valor <= 0:
                falhas.append(f"USDBRL: bcb-sgs devolveu PTAX inválida ({valor!r})")
                continue
            cotacoes.append(Cotacao(data, "00:00", "USDBRL", valor, "BRL", "bcb-sgs"))
        return cotacoes, falhas
