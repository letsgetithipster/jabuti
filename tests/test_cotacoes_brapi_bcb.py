import json
from pathlib import Path

import pytest

from po.cotacoes.providers import REGISTRY, criar_provider
from po.cotacoes.providers.bcb_sgs import SERIES, BcbSgsProvider
from po.cotacoes.providers.brapi import BrapiProvider
from po.cotacoes.tipos import Pedido, RespostaInvalida, SemRede
from po.csvs import FONTES_COTACAO

FIX = Path(__file__).resolve().parent / "fixtures" / "cotacoes"


def buscar_brapi(url, timeout=15.0, headers=None):
    assert "token=segredo" in url
    ticker = url.split("/quote/")[1].split("?")[0]
    caminho = FIX / f"brapi_{ticker}.json"
    if not caminho.exists():
        raise RespostaInvalida("HTTP 404")
    return json.loads(caminho.read_text(encoding="utf-8"))


def buscar_bcb(url, timeout=15.0, headers=None):
    codigo = url.split("bcdata.sgs.")[1].split("/")[0]
    return json.loads((FIX / f"bcb_sgs_{codigo}.json").read_text(encoding="utf-8"))


def test_registry_fecha_com_o_vocabulario_de_fonte():
    assert set(REGISTRY) | {"manual", "definicao"} == FONTES_COTACAO
    with pytest.raises(ValueError):
        criar_provider("chute")


def test_brapi_cota_b3_em_horario_de_brasilia():
    cot, falhas = BrapiProvider(buscar=buscar_brapi, token="segredo", pausa=0).cotar([Pedido("PETR4", "acoes-br", "BRL")])
    assert falhas == []
    c = cot[0]
    assert (c.preco, c.moeda, c.fonte, c.data, c.hora) == (40.15, "BRL", "brapi", "2026-09-08", "17:07")


def test_brapi_recusa_fora_da_b3():
    cot, falhas = BrapiProvider(buscar=buscar_brapi, token="segredo", pausa=0).cotar(
        [Pedido("AAPL", "rv-int", "USD"), Pedido("USDBRL", "cambio", "BRL"), Pedido("BTC", "cripto", "BRL")])
    assert cot == [] and len(falhas) == 3 and all("só" in f for f in falhas)


def test_brapi_le_token_do_ambiente(monkeypatch):
    monkeypatch.setenv("BRAPI_TOKEN", "segredo")
    cot, _ = BrapiProvider(buscar=buscar_brapi, pausa=0).cotar([Pedido("PETR4", "acoes-br", "BRL")])
    assert cot[0].preco == 40.15


def test_brapi_http_erro_sugere_token():
    def nega(url, timeout=15.0, headers=None):
        raise RespostaInvalida("HTTP 401")
    _, falhas = BrapiProvider(buscar=nega, token="", pausa=0).cotar([Pedido("PETR4", "acoes-br", "BRL")])
    assert any("BRAPI_TOKEN" in f for f in falhas)


def test_brapi_404_com_401_no_corpo_nao_sugere_token():
    def nega(url, timeout=15.0, headers=None):
        raise RespostaInvalida("HTTP 404: id 401 nao encontrado")   # corpo cita 401, mas nao e o codigo
    _, falhas = BrapiProvider(buscar=nega, token="segredo", pausa=0).cotar([Pedido("PETR4", "acoes-br", "BRL")])
    assert falhas and not any("BRAPI_TOKEN" in f for f in falhas)


def test_brapi_nao_e_papel_negociado():
    cot, falhas = BrapiProvider(buscar=buscar_brapi, token="segredo", pausa=0).cotar(
        [Pedido("CDB-X", "rf-br", "BRL"), Pedido("CAIXA", "caixa", "BRL")])
    assert cot == [] and len(falhas) == 2 and all("não é papel negociado" in f for f in falhas)


def test_brapi_preco_invalido_nao_vira_cotacao():
    def zero(url, timeout=15.0, headers=None):
        return {"results": [{"symbol": "PETR4", "currency": "BRL", "regularMarketPrice": 0,
                             "regularMarketTime": "2026-09-08T20:07:00.000Z"}]}
    cot, falhas = BrapiProvider(buscar=zero, token="s", pausa=0).cotar([Pedido("PETR4", "acoes-br", "BRL")])
    assert cot == [] and any("preço inválido" in f for f in falhas)


def test_bcb_ptax_para_usdbrl():
    cot, falhas = BcbSgsProvider(buscar=buscar_bcb).cotar([Pedido("USDBRL", "cambio", "BRL")])
    assert falhas == []
    c = cot[0]
    assert (c.ticker, c.preco, c.moeda, c.fonte, c.data, c.hora) == ("USDBRL", 5.4321, "BRL", "bcb-sgs", "2026-09-08", "00:00")


def test_bcb_recusa_o_que_nao_e_cambio():
    cot, falhas = BcbSgsProvider(buscar=buscar_bcb).cotar([Pedido("PETR4", "acoes-br", "BRL"), Pedido("EURBRL", "cambio", "BRL")])
    assert cot == [] and len(falhas) == 2


def test_bcb_serie_de_indexador():
    pontos = BcbSgsProvider(buscar=buscar_bcb).serie(SERIES["cdi"], n=2)
    assert pontos == [("2026-09-04", 0.055131), ("2026-09-08", 0.055131)]


def test_bcb_resposta_estranha_e_resposta_invalida():
    def estranho(url, timeout=15.0, headers=None):
        return {"erro": "x"}
    with pytest.raises(RespostaInvalida):
        BcbSgsProvider(buscar=estranho).serie(1)


def test_criar_provider_repassa_kwargs_por_provider():
    prov = criar_provider("brapi", buscar=buscar_brapi, token="segredo", pausa=0)
    cot, falhas = prov.cotar([Pedido("PETR4", "acoes-br", "BRL")])
    assert falhas == [] and cot[0].fonte == "brapi"
    cot, falhas = criar_provider("bcb-sgs", buscar=buscar_bcb).cotar([Pedido("USDBRL", "cambio", "BRL")])
    assert falhas == [] and cot[0].fonte == "bcb-sgs"
    with pytest.raises(TypeError):        # kwargs são por provider: o bcb-sgs não tem pausa
        criar_provider("bcb-sgs", buscar=buscar_bcb, pausa=0)


def test_brapi_erro_sem_relacao_com_token_nao_sugere_token():
    def nao_achou(url, timeout=15.0, headers=None):
        raise RespostaInvalida("HTTP 404: symbol not found")
    _, falhas = BrapiProvider(buscar=nao_achou, token="segredo", pausa=0).cotar([Pedido("XXXX3", "acoes-br", "BRL")])
    assert falhas and "BRAPI_TOKEN" not in falhas[0] and "404" in falhas[0]


def test_brapi_moeda_diferente_da_esperada():
    def em_usd(url, timeout=15.0, headers=None):
        return {"results": [{"symbol": "PETR4", "currency": "USD", "regularMarketPrice": 8.0,
                             "regularMarketTime": "2026-09-08T20:07:00.000Z"}]}
    cot, falhas = BrapiProvider(buscar=em_usd, token="s", pausa=0).cotar([Pedido("PETR4", "acoes-br", "BRL")])
    assert cot == [] and any("USD" in f and "BRL" in f for f in falhas)


def test_brapi_timestamp_sem_fuso_nao_vira_cotacao():
    def sem_fuso(url, timeout=15.0, headers=None):
        return {"results": [{"symbol": "PETR4", "currency": "BRL", "regularMarketPrice": 40.15,
                             "regularMarketTime": "2026-09-08 20:07:00"}]}
    cot, falhas = BrapiProvider(buscar=sem_fuso, token="s", pausa=0).cotar([Pedido("PETR4", "acoes-br", "BRL")])
    assert cot == [] and any("sem fuso" in f for f in falhas)


def test_brapi_sem_rede_propaga():
    def caiu(url, timeout=15.0, headers=None):
        raise SemRede("getaddrinfo failed")
    with pytest.raises(SemRede):
        BrapiProvider(buscar=caiu, token="s", pausa=0).cotar([Pedido("PETR4", "acoes-br", "BRL")])


def test_brapi_throttle_entre_pedidos():
    dormidas = []
    prov = BrapiProvider(buscar=buscar_brapi, token="segredo", pausa=0.4, dormir=dormidas.append)
    prov.cotar([Pedido("PETR4", "acoes-br", "BRL"), Pedido("PETR4", "acoes-br", "BRL")])
    assert dormidas == [0.4]


def test_bcb_ptax_invalida_nao_vira_cotacao():
    def zero(url, timeout=15.0, headers=None):
        return [{"data": "08/09/2026", "valor": "0"}]
    cot, falhas = BcbSgsProvider(buscar=zero).cotar([Pedido("USDBRL", "cambio", "BRL")])
    assert cot == [] and any("preço inválido" in f for f in falhas)


def test_bcb_serie_recusa_valor_nao_finito():
    def nan(url, timeout=15.0, headers=None):
        return [{"data": "08/09/2026", "valor": "NaN"}]
    with pytest.raises(RespostaInvalida, match="não finito"):
        BcbSgsProvider(buscar=nan).serie(12, 1)
