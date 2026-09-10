"""Provider brapi.dev (B3 apenas). Token por variável de ambiente BRAPI_TOKEN — nunca em arquivo."""
import datetime
import math
import os
import time
import urllib.parse

from po.cotacoes.http import buscar_json
from po.cotacoes.tipos import (Cotacao, Pedido, RespostaInvalida, falha_moeda,
                               falha_nao_negociado, falha_preco, sem_cotacao_de_mercado)

URL = "https://brapi.dev/api/quote/{ticker}?token={token}"
PAUSA_ENTRE_PEDIDOS = 0.3  # cota por minuto no plano gratuito; 0,3s mantém a taxa bem abaixo do limite
# fixo em -3: o Brasil aboliu o horário de verão em 2019, e zoneinfo exigiria o pacote tzdata no
# Windows por zero benefício. O yahoo é imune por construção (lê gmtoffset da resposta).
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
                falhas.append(falha_nao_negociado(p.ticker, p.classe))
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
                dica = (" — token ausente ou inválido? defina a variável de ambiente BRAPI_TOKEN"
                        if not self._token or "401" in str(e) or "403" in str(e) else "")
                falhas.append(f"{p.ticker}: brapi não devolveu cotação ({e}){dica}")
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
                falhas.append(falha_preco(p.ticker, "brapi", preco))
                continue
            if moeda != p.moeda:
                falhas.append(falha_moeda(p.ticker, "brapi", moeda, p.moeda))
                continue
            try:
                momento = datetime.datetime.fromisoformat(str(quando).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                falhas.append(f"{p.ticker}: resposta da brapi sem regularMarketTime legível ({quando!r})")
                continue
            if momento.tzinfo is None:   # sem fuso, a hora dependeria do relógio desta máquina
                falhas.append(f"{p.ticker}: brapi devolveu regularMarketTime sem fuso ({quando!r}) — "
                              "não dá para saber a hora real")
                continue
            momento = momento.astimezone(FUSO_BRASILIA)
            cotacoes.append(Cotacao(momento.strftime("%Y-%m-%d"), momento.strftime("%H:%M"),
                                    p.ticker, preco, moeda, "brapi"))
        return cotacoes, falhas
