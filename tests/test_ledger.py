from po.ledger import Saldo, calcular_saldos


def _f(data, ticker, tipo, qty, preco, taxa=0.0, conta="c"):
    return {"data": data, "ticker": ticker, "tipo": tipo, "qty": float(qty),
            "preco": float(preco), "taxa": float(taxa), "conta": conta, "moeda": "BRL"}


def test_pm_ponderado_com_taxa():
    saldos, erros, _ = calcular_saldos([_f("2026-08-05", "PETR4", "compra", 60, 29.50),
                                        _f("2026-09-05", "PETR4", "compra", 40, 30.75, taxa=10)])
    assert erros == []
    s = saldos[("PETR4", "c")]
    assert s.qty == 100 and abs(s.pm - 30.10) < 1e-9     # (1770 + 1230 + 10) / 100


def test_saldo_inicial_abre_o_ledger():
    saldos, erros, _ = calcular_saldos([_f("2026-08-01", "HGLG11", "saldo-inicial", 50, 155.00)])
    assert erros == [] and saldos[("HGLG11", "c")].pm == 155.0


def test_venda_baixa_ao_pm_corrente_sem_alterar_pm():
    saldos, erros, _ = calcular_saldos([_f("2026-08-05", "PETR4", "compra", 100, 30.00),
                                        _f("2026-09-05", "PETR4", "venda", 40, 50.00, taxa=5)])
    s = saldos[("PETR4", "c")]
    assert erros == [] and s.qty == 60 and abs(s.pm - 30.0) < 1e-9


def test_ordem_e_por_data_depois_por_linha():
    # venda aparece ANTES no arquivo, mas é depois no tempo: não pode dar erro
    saldos, erros, _ = calcular_saldos([_f("2026-09-05", "PETR4", "venda", 40, 50.00),
                                        _f("2026-08-05", "PETR4", "compra", 100, 30.00)])
    assert erros == [] and saldos[("PETR4", "c")].qty == 60


def test_venda_acima_do_saldo_e_erro():
    _, erros, _ = calcular_saldos([_f("2026-08-05", "PETR4", "compra", 10, 30.00),
                                   _f("2026-09-05", "PETR4", "venda", 40, 50.00)])
    assert any("excede o saldo" in e and "PETR4" in e for e in erros)


def test_posicao_zerada_tem_qty_zero():
    saldos, _, _ = calcular_saldos([_f("2026-08-05", "PETR4", "compra", 10, 30.00),
                                    _f("2026-09-05", "PETR4", "venda", 10, 50.00)])
    s = saldos[("PETR4", "c")]
    assert s.qty == 0 and s.pm == 0.0


def test_contas_separadas():
    saldos, _, _ = calcular_saldos([_f("2026-08-05", "PETR4", "compra", 10, 30.00, conta="a"),
                                    _f("2026-08-05", "PETR4", "compra", 5, 30.00, conta="b")])
    assert saldos[("PETR4", "a")].qty == 10 and saldos[("PETR4", "b")].qty == 5


def test_venda_sem_posicao_nao_cria_saldo_fantasma():
    saldos, erros, suspeitas = calcular_saldos([_f("2026-09-05", "VALE3", "venda", 5, 60.00)])
    assert saldos == {} and ("VALE3", "c") in suspeitas
    assert any("excede o saldo" in e and "(0)" in e for e in erros)


def test_saldo_inicial_compra_e_venda_no_mesmo_ticker():
    saldos, erros, suspeitas = calcular_saldos([
        _f("2026-08-01", "HGLG11", "saldo-inicial", 50, 150.00),
        _f("2026-08-10", "HGLG11", "compra", 50, 160.00, taxa=10),
        _f("2026-09-01", "HGLG11", "venda", 20, 170.00, taxa=5)])
    assert erros == [] and suspeitas == set()
    s = saldos[("HGLG11", "c")]
    assert s.qty == 80 and abs(s.pm - 155.10) < 1e-9        # (7500 + 8010) / 100 = 155,10; venda não muda PM


def test_venda_antes_da_compra_no_mesmo_dia_nao_e_erro():
    saldos, erros, _ = calcular_saldos([_f("2026-01-01", "PETR4", "venda", 10, 40.00),
                                        _f("2026-01-01", "PETR4", "compra", 100, 30.00)])
    assert erros == [] and saldos[("PETR4", "c")].qty == 90


def test_dois_saldos_iniciais_e_erro():
    _, erros, suspeitas = calcular_saldos([_f("2026-08-01", "HGLG11", "saldo-inicial", 50, 155.00),
                                           _f("2026-08-02", "HGLG11", "saldo-inicial", 50, 155.00)])
    assert any("mais de um saldo-inicial" in e for e in erros) and ("HGLG11", "c") in suspeitas


def test_saldo_inicial_depois_de_compra_e_erro():
    _, erros, suspeitas = calcular_saldos([_f("2026-08-01", "HGLG11", "compra", 10, 155.00),
                                           _f("2026-08-02", "HGLG11", "saldo-inicial", 50, 155.00)])
    assert any("é o primeiro evento" in e for e in erros) and ("HGLG11", "c") in suspeitas


def test_tipo_desconhecido_e_erro():
    _, erros, suspeitas = calcular_saldos([_f("2026-08-01", "HGLG11", "bonificacao", 10, 0.0)])
    assert any("tipo de fill desconhecido" in e for e in erros) and ("HGLG11", "c") in suspeitas
