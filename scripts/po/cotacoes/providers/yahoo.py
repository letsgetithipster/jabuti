"""Provider Yahoo Finance (endpoint público v8/chart, sem chave).

Fonte não-oficial: quando quebra, a falha é declarada por ticker — nunca preço velho
em silêncio. Hora gravada = hora local da bolsa (regularMarketTime + gmtoffset).
"""
import datetime
import math
import time
import urllib.parse

from po.cotacoes.http import buscar_json
from po.cotacoes.tipos import (Cotacao, Pedido, RespostaInvalida, e_codigo_b3, falha_moeda,
                               falha_nao_negociado, falha_preco, sem_cotacao_de_mercado)

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?range=1d&interval=1d"
PAUSA_ENTRE_PEDIDOS = 0.3   # a fonte pública é sensível a rajada
SEMPRE_B3 = {"acoes-br", "fiis"}      # por definição da classe
SEMPRE_EUA = {"reits-us"}             # idem


def simbolo_yahoo(p: Pedido) -> str | None:
    """Símbolo no Yahoo a partir de (ticker, classe, moeda). None = não é papel negociado.

    A classe resolve quando ela já diz a bolsa (acoes-br e fiis são B3, reits-us é EUA); em
    cripto a moeda define o par (BTC-BRL, BTC-USD). Nas classes mistas (rv-int, commodities,
    caixa) o TICKER decide, e um ticker sem dígito em caixa é saldo em conta, não papel.
    Fora de cripto, a moeda do Pedido é só o valor ESPERADO pra validar a resposta do yahoo —
    não entra na escolha do símbolo, senão um pedido malformado (ticker americano com moeda
    BRL) nunca chegaria a consultar a fonte pra denunciar a inconsistência.
    Errar o palpite não inventa preço: o símbolo não existe no yahoo e a falha é declarada
    por ticker (e uma moeda diferente da esperada é barrada logo depois).
    """
    if sem_cotacao_de_mercado(p):
        return None
    if p.classe == "cambio":
        return "BRL=X" if p.ticker == "USDBRL" else f"{p.ticker}=X"
    if p.classe == "cripto":
        return f"{p.ticker}-{p.moeda}"
    if p.classe in SEMPRE_B3:
        return f"{p.ticker}.SA"
    if p.classe in SEMPRE_EUA:
        return p.ticker
    return f"{p.ticker}.SA" if e_codigo_b3(p.ticker) else p.ticker


class YahooProvider:
    nome = "yahoo"

    def __init__(self, buscar=buscar_json, pausa: float = PAUSA_ENTRE_PEDIDOS, dormir=time.sleep):
        self._buscar = buscar
        self._pausa = pausa
        self._dormir = dormir

    def cotar(self, pedidos: list[Pedido]) -> tuple[list[Cotacao], list[str]]:
        cotacoes, falhas, consultados = [], [], 0
        for p in pedidos:
            simbolo = simbolo_yahoo(p)
            if simbolo is None:
                falhas.append(falha_nao_negociado(p.ticker, p.classe))
                continue
            if consultados and self._pausa:
                self._dormir(self._pausa)
            consultados += 1
            try:
                d = self._buscar(URL.format(simbolo=urllib.parse.quote(simbolo, safe="=.-")))
            except RespostaInvalida as e:
                falhas.append(f"{p.ticker}: yahoo não devolveu cotação para {simbolo} ({e})")
                continue
            try:
                meta = d["chart"]["result"][0]["meta"]
                preco = float(meta["regularMarketPrice"])
                moeda = str(meta["currency"]).upper()
                ts = int(meta["regularMarketTime"])
                off = int(meta.get("gmtoffset", 0))
            except (KeyError, IndexError, TypeError, ValueError) as e:
                falhas.append(f"{p.ticker}: resposta do yahoo ilegível para {simbolo} "
                              f"({type(e).__name__}: {e})")
                continue
            if not math.isfinite(preco) or preco <= 0:
                falhas.append(falha_preco(p.ticker, "yahoo", preco))
                continue
            if moeda != p.moeda:
                falhas.append(falha_moeda(p.ticker, "yahoo", moeda, p.moeda))
                continue
            momento = datetime.datetime.fromtimestamp(ts + off, tz=datetime.timezone.utc)
            cotacoes.append(Cotacao(momento.strftime("%Y-%m-%d"), momento.strftime("%H:%M"),
                                    p.ticker, preco, moeda, "yahoo"))
        return cotacoes, falhas
