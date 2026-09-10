"""Provider brapi.dev (B3 apenas). Token por variável de ambiente BRAPI_TOKEN — nunca em arquivo."""
import datetime
import math
import os
import time
import urllib.parse

from po.cotacoes.http import buscar_json
from po.cotacoes.providers.yahoo import PAUSA_ENTRE_PEDIDOS, sem_cotacao_de_mercado
from po.cotacoes.tipos import Cotacao, Pedido, RespostaInvalida

URL = "https://brapi.dev/api/quote/{ticker}?token={token}"
FUSO_BRASILIA = datetime.timezone(datetime.timedelta(hours=-3))


class BrapiProvider:
    nome = "brapi"

    def __init__(self, buscar=buscar_json, token: str | None = None,
                 pausa: float = PAUSA_ENTRE_PEDIDOS, dormir=time.sleep):
        self._buscar = buscar
        self._token = token if token is not None else os.environ.get("BRAPI_TOKEN", "")
        self._pausa = pausa
        self._dormir = dormir

    def cotar(self, pedidos: list[Pedido]) -> tuple[list[Cotacao], list[str]]:
        cotacoes, falhas, consultados = [], [], 0
        for p in pedidos:
            if sem_cotacao_de_mercado(p):
                falhas.append(f"{p.ticker}: não é papel negociado ({p.classe}) — "
                              f"passe --manual {p.ticker}=VALOR")
                continue
            if p.moeda != "BRL" or p.classe in ("cambio", "cripto"):
                falhas.append(f"{p.ticker}: brapi cobre só ativos da B3 em BRL — use yahoo como "
                              "provider (ou bcb-sgs para câmbio)")
                continue
            if consultados and self._pausa:
                self._dormir(self._pausa)
            consultados += 1
            try:
                d = self._buscar(URL.format(ticker=urllib.parse.quote(p.ticker), token=self._token))
            except RespostaInvalida as e:
                falhas.append(f"{p.ticker}: brapi respondeu {e} — token ausente ou inválido? "
                              "defina a variável de ambiente BRAPI_TOKEN")
                continue
            try:
                r = d["results"][0]
                preco = float(r["regularMarketPrice"])
                moeda = str(r.get("currency", "BRL")).upper()
                quando = r["regularMarketTime"]
            except (KeyError, IndexError, TypeError, ValueError) as e:
                falhas.append(f"{p.ticker}: resposta da brapi ilegível ({type(e).__name__}: {e})")
                continue
            if not math.isfinite(preco) or preco <= 0:
                falhas.append(f"{p.ticker}: brapi devolveu preço inválido ({preco!r}) — "
                              "ativo suspenso ou deslistado? confira o ticker")
                continue
            if moeda != p.moeda:
                falhas.append(f"{p.ticker}: brapi devolveu {moeda}, esperado {p.moeda}")
                continue
            try:
                momento = datetime.datetime.fromisoformat(str(quando).replace("Z", "+00:00")).astimezone(FUSO_BRASILIA)
            except (TypeError, ValueError):
                falhas.append(f"{p.ticker}: resposta da brapi sem regularMarketTime legível")
                continue
            cotacoes.append(Cotacao(momento.strftime("%Y-%m-%d"), momento.strftime("%H:%M"),
                                    p.ticker, preco, moeda, "brapi"))
        return cotacoes, falhas
