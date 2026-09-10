import json
from pathlib import Path

import pytest

from po.cotacoes.providers.manual import ManualProvider
from po.cotacoes.providers.yahoo import YahooProvider, simbolo_yahoo
from po.cotacoes.tipos import Pedido, RespostaInvalida, SemRede

FIX = Path(__file__).resolve().parent / "fixtures" / "cotacoes"


def buscar_fixture(url, timeout=15.0, headers=None):
    """Resolve a URL do Yahoo para um arquivo de fixture pelo símbolo. Sem rede."""
    simbolo = url.split("/chart/")[1].split("?")[0]
    nome = "yahoo_USDBRL.json" if simbolo == "BRL=X" else f"yahoo_{simbolo}.json"
    caminho = FIX / nome
    if not caminho.exists():
        raise RespostaInvalida("HTTP 404")
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_simbolos():
    assert simbolo_yahoo(Pedido("PETR4", "acoes-br", "BRL")) == "PETR4.SA"
    assert simbolo_yahoo(Pedido("HGLG11", "fiis", "BRL")) == "HGLG11.SA"
    assert simbolo_yahoo(Pedido("IVVB11", "rv-int", "BRL")) == "IVVB11.SA"   # BDR/ETF na B3: termina em dígito
    assert simbolo_yahoo(Pedido("AAPL34", "rv-int", "BRL")) == "AAPL34.SA"   # BDR de ação americana
    assert simbolo_yahoo(Pedido("AAPL", "rv-int", "USD")) == "AAPL"
    assert simbolo_yahoo(Pedido("O", "reits-us", "USD")) == "O"              # REIT americano nunca leva .SA
    assert simbolo_yahoo(Pedido("WELL", "reits-us", "USD")) == "WELL"
    assert simbolo_yahoo(Pedido("GLD", "commodities", "USD")) == "GLD"       # ETF de ouro americano
    assert simbolo_yahoo(Pedido("OZ1D", "commodities", "BRL")) == "OZ1D.SA"  # contrato de ouro na B3
    assert simbolo_yahoo(Pedido("BTC", "cripto", "BRL")) == "BTC-BRL"
    assert simbolo_yahoo(Pedido("BTC", "cripto", "USD")) == "BTC-USD"        # a moeda da posição decide o par
    assert simbolo_yahoo(Pedido("USDBRL", "cambio", "BRL")) == "BRL=X"
    assert simbolo_yahoo(Pedido("EURBRL", "cambio", "BRL")) == "EURBRL=X"
    assert simbolo_yahoo(Pedido("TESOURO-IPCA-2035", "rf-br", "BRL")) is None
    assert simbolo_yahoo(Pedido("AUPO11", "caixa", "BRL")) is None


def test_cota_com_fixture_e_hora_local_da_bolsa():
    cot, falhas = YahooProvider(buscar=buscar_fixture).cotar([Pedido("PETR4", "acoes-br", "BRL")])
    assert falhas == []
    c = cot[0]
    assert (c.ticker, c.preco, c.moeda, c.fonte) == ("PETR4", 40.0, "BRL", "yahoo")
    assert (c.data, c.hora) == ("2026-09-08", "18:00")


def test_moeda_diferente_da_esperada_e_falha():
    cot, falhas = YahooProvider(buscar=buscar_fixture).cotar([Pedido("AAPL", "rv-int", "BRL")])
    assert cot == [] and any("AAPL" in f and "USD" in f and "BRL" in f for f in falhas)


def test_ticker_desconhecido_e_falha_sem_derrubar_os_outros():
    cot, falhas = YahooProvider(buscar=buscar_fixture).cotar([Pedido("XXXX3", "acoes-br", "BRL"),
                                                             Pedido("PETR4", "acoes-br", "BRL")])
    assert [c.ticker for c in cot] == ["PETR4"]
    assert any("XXXX3" in f for f in falhas)


def test_classe_sem_mercado_pede_manual():
    cot, falhas = YahooProvider(buscar=buscar_fixture).cotar([Pedido("CDB-X", "rf-br", "BRL")])
    assert cot == [] and any("--manual CDB-X=" in f for f in falhas)


def test_sem_rede_propaga():
    def sem_rede(url, timeout=15.0, headers=None):
        raise SemRede("getaddrinfo failed")
    with pytest.raises(SemRede):
        YahooProvider(buscar=sem_rede).cotar([Pedido("PETR4", "acoes-br", "BRL")])


def test_resposta_sem_preco_e_falha():
    def vazio(url, timeout=15.0, headers=None):
        return {"chart": {"result": None, "error": {"code": "Not Found"}}}
    cot, falhas = YahooProvider(buscar=vazio).cotar([Pedido("PETR4", "acoes-br", "BRL")])
    assert cot == [] and any("PETR4" in f for f in falhas)


def test_manual_provider():
    prov = ManualProvider({"CDB-X": 1050.0}, "2026-09-08", "10:30")
    cot, falhas = prov.cotar([Pedido("CDB-X", "rf-br", "BRL"), Pedido("PETR4", "acoes-br", "BRL")])
    assert cot[0].preco == 1050.0 and cot[0].fonte == "manual" and cot[0].hora == "10:30"
    assert any("PETR4" in f and "--manual PETR4=" in f for f in falhas)
