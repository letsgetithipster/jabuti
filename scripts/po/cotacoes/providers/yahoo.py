"""Provider Yahoo Finance (endpoint público v8/chart, sem chave).

Fonte não-oficial: quando quebra, a falha é declarada por ticker — nunca preço velho
em silêncio. Hora gravada = hora local da bolsa (regularMarketTime + gmtoffset).
"""
import datetime

from po.cotacoes.http import buscar_json
from po.cotacoes.tipos import Cotacao, Pedido, RespostaInvalida

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?range=1d&interval=1d"
SEM_MERCADO = {"rf-br", "caixa"}
SEMPRE_B3 = {"acoes-br", "fiis"}      # por definição da classe
SEMPRE_EUA = {"reits-us"}             # idem


def simbolo_yahoo(p: Pedido) -> str | None:
    """Símbolo no Yahoo a partir de (ticker, classe, moeda). None = classe sem cotação de mercado.

    A classe resolve quando ela já diz a bolsa (acoes-br e fiis são B3, reits-us é EUA).
    Nas classes mistas (rv-int, commodities) o TICKER decide: papel listado na B3 carrega
    dígito (IVVB11, AAPL34, OZ1D — contrato com código de vencimento no meio → sufixo .SA),
    papel americano não tem dígito nenhum (AAPL, GLD). A moeda do Pedido é só o valor
    ESPERADO pra validar a resposta do yahoo — não entra na escolha do símbolo, senão um
    pedido malformado (ticker americano com moeda BRL) nunca chegaria a consultar a fonte
    pra denunciar a inconsistência.
    """
    if p.classe in SEM_MERCADO:
        return None
    if p.classe == "cambio":
        return "BRL=X" if p.ticker == "USDBRL" else f"{p.ticker}=X"
    if p.classe == "cripto":
        return f"{p.ticker}-{p.moeda}"
    if p.classe in SEMPRE_B3:
        return f"{p.ticker}.SA"
    if p.classe in SEMPRE_EUA:
        return p.ticker
    return f"{p.ticker}.SA" if any(ch.isdigit() for ch in p.ticker) else p.ticker


class YahooProvider:
    nome = "yahoo"

    def __init__(self, buscar=buscar_json):
        self._buscar = buscar

    def cotar(self, pedidos: list[Pedido]) -> tuple[list[Cotacao], list[str]]:
        cotacoes, falhas = [], []
        for p in pedidos:
            simbolo = simbolo_yahoo(p)
            if simbolo is None:
                falhas.append(f"{p.ticker}: classe {p.classe} não tem cotação de mercado — "
                              f"passe --manual {p.ticker}=VALOR")
                continue
            try:
                d = self._buscar(URL.format(simbolo=simbolo))
                meta = d["chart"]["result"][0]["meta"]
                preco = float(meta["regularMarketPrice"])
                moeda = str(meta["currency"]).upper()
                ts = int(meta["regularMarketTime"])
                off = int(meta.get("gmtoffset", 0))
            except RespostaInvalida as e:
                falhas.append(f"{p.ticker}: yahoo não devolveu cotação para {simbolo} ({e})")
                continue
            except (KeyError, IndexError, TypeError, ValueError):
                falhas.append(f"{p.ticker}: resposta do yahoo sem regularMarketPrice para {simbolo}")
                continue
            if moeda != p.moeda:
                falhas.append(f"{p.ticker}: yahoo devolveu {moeda}, esperado {p.moeda} (moeda da posição) "
                              "— confira o ticker")
                continue
            momento = datetime.datetime.fromtimestamp(ts + off, tz=datetime.timezone.utc)
            cotacoes.append(Cotacao(momento.strftime("%Y-%m-%d"), momento.strftime("%H:%M"),
                                    p.ticker, preco, moeda, "yahoo"))
        return cotacoes, falhas
