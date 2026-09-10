from po.cotacoes.tipos import Cotacao, Pedido, pedidos_de_posicoes


def test_cotacao_vira_linha_do_schema():
    from po.csvs import SCHEMAS, validar_linha
    c = Cotacao("2026-09-08", "18:00", "PETR4", 40.0, "BRL", "yahoo")
    assert set(c.como_linha()) == set(SCHEMAS["cotacoes"])
    assert validar_linha("cotacoes", dict(c.como_linha()), "teste") == []   # é sempre linha anexável


def test_pedidos_de_posicoes_deduplica_e_adiciona_cambio():
    pos = [
        {"ticker": "PETR4", "classe": "acoes-br", "conta": "br", "qty": 1.0, "pm": 1.0, "moeda": "BRL"},
        {"ticker": "PETR4", "classe": "acoes-br", "conta": "br2", "qty": 1.0, "pm": 1.0, "moeda": "BRL"},
        {"ticker": "AAPL", "classe": "rv-int", "conta": "us", "qty": 1.0, "pm": 1.0, "moeda": "USD"},
    ]
    pedidos = pedidos_de_posicoes(pos)
    assert pedidos == [Pedido("PETR4", "acoes-br", "BRL"), Pedido("AAPL", "rv-int", "USD"),
                       Pedido("USDBRL", "cambio", "BRL")]


def test_sem_posicao_fora_do_brl_nao_pede_cambio():
    pos = [{"ticker": "PETR4", "classe": "acoes-br", "conta": "br", "qty": 1.0, "pm": 1.0, "moeda": "BRL"}]
    assert [p.ticker for p in pedidos_de_posicoes(pos)] == ["PETR4"]
