from po.ledger import Saldo, calcular_saldos, posicoes_de_fills


def F(data, ticker, tipo, qty, preco, taxa=0.0, conta="c"):
    return {"data": data, "ticker": ticker, "tipo": tipo, "qty": float(qty),
            "preco": float(preco), "taxa": float(taxa), "conta": conta, "moeda": "BRL"}


def test_pm_ponderado_com_taxa():
    saldos, erros, _ = calcular_saldos([F("2026-08-05", "PETR4", "compra", 60, 29.50),
                                        F("2026-09-05", "PETR4", "compra", 40, 30.75, taxa=10)])
    assert erros == []
    s = saldos[("PETR4", "c")]
    assert s.qty == 100 and abs(s.pm - 30.10) < 1e-9     # (1770 + 1230 + 10) / 100


def test_saldo_inicial_abre_o_ledger():
    saldos, erros, _ = calcular_saldos([F("2026-08-01", "HGLG11", "saldo-inicial", 50, 155.00)])
    assert erros == [] and saldos[("HGLG11", "c")].pm == 155.0


def test_venda_baixa_ao_pm_corrente_sem_alterar_pm():
    saldos, erros, _ = calcular_saldos([F("2026-08-05", "PETR4", "compra", 100, 30.00),
                                        F("2026-09-05", "PETR4", "venda", 40, 50.00, taxa=5)])
    s = saldos[("PETR4", "c")]
    assert erros == [] and s.qty == 60 and abs(s.pm - 30.0) < 1e-9


def test_ordem_e_por_data_depois_por_linha():
    # venda aparece ANTES no arquivo, mas é depois no tempo: não pode dar erro
    saldos, erros, _ = calcular_saldos([F("2026-09-05", "PETR4", "venda", 40, 50.00),
                                        F("2026-08-05", "PETR4", "compra", 100, 30.00)])
    assert erros == [] and saldos[("PETR4", "c")].qty == 60


def test_venda_acima_do_saldo_e_erro():
    _, erros, _ = calcular_saldos([F("2026-08-05", "PETR4", "compra", 10, 30.00),
                                   F("2026-09-05", "PETR4", "venda", 40, 50.00)])
    assert any("excede o saldo" in e and "PETR4" in e for e in erros)


def test_posicao_zerada_tem_qty_zero():
    saldos, _, _ = calcular_saldos([F("2026-08-05", "PETR4", "compra", 10, 30.00),
                                    F("2026-09-05", "PETR4", "venda", 10, 50.00)])
    s = saldos[("PETR4", "c")]
    assert s.qty == 0 and s.pm == 0.0


def test_contas_separadas():
    saldos, _, _ = calcular_saldos([F("2026-08-05", "PETR4", "compra", 10, 30.00, conta="a"),
                                    F("2026-08-05", "PETR4", "compra", 5, 30.00, conta="b")])
    assert saldos[("PETR4", "a")].qty == 10 and saldos[("PETR4", "b")].qty == 5


def test_venda_sem_posicao_nao_cria_saldo_fantasma():
    saldos, erros, suspeitas = calcular_saldos([F("2026-09-05", "VALE3", "venda", 5, 60.00)])
    assert saldos == {} and ("VALE3", "c") in suspeitas
    assert any("excede o saldo" in e and "(0)" in e for e in erros)


def test_saldo_inicial_compra_e_venda_no_mesmo_ticker():
    saldos, erros, suspeitas = calcular_saldos([
        F("2026-08-01", "HGLG11", "saldo-inicial", 50, 150.00),
        F("2026-08-10", "HGLG11", "compra", 50, 160.00, taxa=10),
        F("2026-09-01", "HGLG11", "venda", 20, 170.00, taxa=5)])
    assert erros == [] and suspeitas == set()
    s = saldos[("HGLG11", "c")]
    assert s.qty == 80 and abs(s.pm - 155.10) < 1e-9        # (7500 + 8010) / 100 = 155,10; venda não muda PM


def test_venda_antes_da_compra_no_mesmo_dia_nao_e_erro():
    saldos, erros, _ = calcular_saldos([F("2026-01-01", "PETR4", "venda", 10, 40.00),
                                        F("2026-01-01", "PETR4", "compra", 100, 30.00)])
    assert erros == [] and saldos[("PETR4", "c")].qty == 90


def test_dois_saldos_iniciais_e_erro():
    _, erros, suspeitas = calcular_saldos([F("2026-08-01", "HGLG11", "saldo-inicial", 50, 155.00),
                                           F("2026-08-02", "HGLG11", "saldo-inicial", 50, 155.00)])
    assert any("mais de um saldo-inicial" in e for e in erros) and ("HGLG11", "c") in suspeitas


def test_saldo_inicial_depois_de_compra_e_erro():
    _, erros, suspeitas = calcular_saldos([F("2026-08-01", "HGLG11", "compra", 10, 155.00),
                                           F("2026-08-02", "HGLG11", "saldo-inicial", 50, 155.00)])
    assert any("é o primeiro evento" in e for e in erros) and ("HGLG11", "c") in suspeitas


def test_tipo_desconhecido_e_erro():
    _, erros, suspeitas = calcular_saldos([F("2026-08-01", "HGLG11", "bonificacao", 10, 0.0)])
    assert any("tipo de fill desconhecido" in e for e in erros) and ("HGLG11", "c") in suspeitas


def E(data, ticker, tipo, razao="", confirmado="sim"):
    return {"data": data, "ticker": ticker, "tipo": tipo, "razao": razao, "confirmado": confirmado}


def test_split_dobra_qty_e_dilui_pm_sem_mexer_no_custo():
    s, erros, _ = calcular_saldos(
        [F("2026-01-01", "P", "compra", 100, 30.0), F("2026-01-02", "P", "compra", 50, 40.0)],
        [E("2026-02-01", "P", "split", "2:1")])
    assert erros == []
    assert s[("P", "c")].qty == 300
    assert round(s[("P", "c")].pm, 4) == 16.6667
    assert round(s[("P", "c")].custo, 2) == 5000.00


def test_grupamento_e_a_mesma_formula_do_split():
    s, erros, _ = calcular_saldos([F("2026-01-01", "P", "compra", 1000, 1.0)],
                                  [E("2026-02-01", "P", "grupamento", "1:10")])
    assert erros == [] and s[("P", "c")].qty == 100 and round(s[("P", "c")].pm, 4) == 10.0


def test_bonificacao_soma_as_novas_e_mantem_o_custo():
    s, erros, _ = calcular_saldos([F("2026-01-01", "P", "compra", 1000, 10.0)],
                                  [E("2026-02-01", "P", "bonificacao", "1:10")])
    assert erros == [] and s[("P", "c")].qty == 1100
    assert round(s[("P", "c")].pm, 4) == 9.0909 and round(s[("P", "c")].custo, 2) == 10000.00


def test_evento_intercala_cronologicamente_entre_as_compras():
    """A compra posterior ao split entra com a qty dela, não multiplicada: é a intercalação que
    um fator aplicado no fim do replay erraria em silêncio."""
    s, erros, _ = calcular_saldos(
        [F("2026-01-01", "P", "compra", 100, 30.0), F("2026-03-01", "P", "compra", 50, 20.0)],
        [E("2026-02-01", "P", "split", "2:1")])
    assert erros == [] and s[("P", "c")].qty == 250
    assert round(s[("P", "c")].pm, 4) == 16.0 and round(s[("P", "c")].custo, 2) == 4000.00


def test_razao_fora_de_novas_antigas_e_erro():
    _, erros, susp = calcular_saldos([F("2026-01-01", "P", "compra", 100, 30.0)],
                                     [E("2026-02-01", "P", "split", "2 para 1")])
    assert any("novas:antigas" in e for e in erros), erros
    assert ("P", "c") in susp


def test_tipo_confirmado_que_o_ledger_nao_aplica_e_erro_nomeado():
    """A4: TIPOS_EVENTO aceita subscricao, fusao e cisao. Nenhum pode virar no-op silencioso —
    com posição derivada isso seria patrimônio errado com o validador verde."""
    for tipo in ("subscricao", "fusao", "cisao", "outro", "variacao-anomala"):
        _, erros, susp = calcular_saldos([F("2026-01-01", "P", "compra", 100, 30.0)],
                                         [E("2026-02-01", "P", tipo)])
        assert any("não sabe o efeito" in e for e in erros), (tipo, erros)
        assert ("P", "c") in susp, tipo


def test_evento_nao_confirmado_nao_aplica():
    s, erros, _ = calcular_saldos([F("2026-01-01", "P", "compra", 100, 30.0)],
                                  [E("2026-02-01", "P", "split", "2:1", confirmado="nao")])
    assert erros == [] and s[("P", "c")].qty == 100


def test_confirmacao_por_append_vence_a_proposta():
    """Decisão 8: confirmar é anexar, nunca reescrever — anexar_csv é o único writer e ele não
    reescreve. A última linha por (data, ticker) vence, espelhando ultimas_cotacoes."""
    s, erros, _ = calcular_saldos(
        [F("2026-01-01", "P", "compra", 100, 30.0)],
        [E("2026-02-01", "P", "split", "", confirmado="nao"),
         E("2026-02-01", "P", "split", "2:1", confirmado="sim")])
    assert erros == [] and s[("P", "c")].qty == 200


def test_estorno_remove_o_fill_que_casa_exatamente():
    s, erros, _ = calcular_saldos([
        F("2026-01-01", "P", "compra", 100, 30.0),
        F("2026-01-02", "P", "compra", 50, 40.0),
        F("2026-01-02", "P", "estorno", 50, 40.0)])
    assert erros == [] and s[("P", "c")].qty == 100 and round(s[("P", "c")].custo, 2) == 3000.00


def test_estorno_que_casa_zero_fills_e_erro():
    _, erros, susp = calcular_saldos([F("2026-01-02", "P", "compra", 50, 40.0),
                                      F("2026-01-03", "P", "estorno", 50, 40.0)])
    assert any("casa 0 fill" in e for e in erros), erros
    assert ("P", "c") in susp


def test_estorno_ambiguo_e_erro():
    """Duas execuções parciais da mesma ordem no mesmo dia pelo mesmo preço são dois eventos
    reais e rotineiros. O ledger não escolhe qual apagar: ele nomeia a ambiguidade."""
    _, erros, _ = calcular_saldos([F("2026-01-02", "P", "compra", 50, 40.0),
                                   F("2026-01-02", "P", "compra", 50, 40.0),
                                   F("2026-01-02", "P", "estorno", 50, 40.0)])
    assert any("casa 2 fill" in e for e in erros), erros


def test_ate_corta_a_linha_do_tempo():
    """É o corte que posicoes.csv estruturalmente não podia dar: a posição de 31/12 lida em março,
    que o preparar-ir exige."""
    fills = [F("2026-08-05", "P", "compra", 60, 29.5), F("2026-09-05", "P", "compra", 40, 30.75)]
    s, _, _ = calcular_saldos(fills, ate="2026-08-31")
    assert s[("P", "c")].qty == 60 and round(s[("P", "c")].pm, 4) == 29.5
    s, _, _ = calcular_saldos(fills)
    assert s[("P", "c")].qty == 100 and round(s[("P", "c")].pm, 4) == 30.0


def test_ate_corta_evento_posterior_ao_recorte():
    """S22 do par: `ate` filtra fills E eventos. Nenhum teste combinava os dois, então remover o
    filtro de data dos eventos passava pela suíte inteira — e um split de fevereiro/27 aplicado
    à posição de 31/12/26 é erro de IR invisível, no caso de uso que o próprio parâmetro nomeia.
    """
    fills = [F("2026-01-01", "P", "compra", 100, 30.0)]
    eventos = [E("2027-02-01", "P", "split", "2:1")]
    s, erros, _ = calcular_saldos(fills, eventos, ate="2026-12-31")
    assert erros == [] and s[("P", "c")].qty == 100
    s, erros, _ = calcular_saldos(fills, eventos)
    assert erros == [] and s[("P", "c")].qty == 200


def test_evento_de_um_ticker_nao_toca_os_outros():
    """S22: com um ticker só no livro, filtrar por ticker e não filtrar dão o MESMO saldo — as
    seis fixtures de evento usavam "P" sozinho, e um split de PETR4 que multiplicasse HGLG11
    junto passava pela suíte inteira. É o erro de patrimônio mais caro que o ledger pode cometer
    em silêncio, porque escala com o tamanho da carteira."""
    s, erros, _ = calcular_saldos(
        [F("2026-01-01", "PETR4", "compra", 100, 30.0),
         F("2026-01-01", "HGLG11", "compra", 50, 155.0)],
        [E("2026-02-01", "PETR4", "split", "2:1")])
    assert erros == []
    assert s[("PETR4", "c")].qty == 200 and round(s[("PETR4", "c")].custo, 2) == 3000.00
    assert s[("HGLG11", "c")].qty == 50 and round(s[("HGLG11", "c")].custo, 2) == 7750.00


def test_mensagem_de_estorno_escreve_numero_em_pt_br():
    """A mensagem manda repetir EXATAMENTE a linha que o estorno anula, então não pode corromper
    o número que manda repetir. Com `:g` ela escrevia "R$ 350000" para R$ 350.000,50 (os centavos
    sumiam), "1.23457e+06" para R$ 1.234.567,89 e ponto decimal num produto pt-BR."""
    _, erros, _ = calcular_saldos(
        [F("2026-01-02", "BTC", "estorno", 0.03, 350000.5, taxa=12.34, conta="exchange")])
    assert len(erros) == 1, erros
    assert "estorno de 0,03 BTC" in erros[0], erros[0]
    assert "R$ 350.000,50" in erros[0], erros[0]
    assert "taxa 12,34" in erros[0], erros[0]

    _, erros, _ = calcular_saldos([F("2026-01-02", "BTC", "estorno", 0.00000001, 1234567.89)])
    assert len(erros) == 1, erros
    assert "estorno de 0,00000001 BTC" in erros[0], erros[0]
    assert "R$ 1.234.567,89" in erros[0], erros[0]
    assert "e+" not in erros[0] and "e-" not in erros[0], erros[0]


def test_mensagem_de_venda_acima_do_saldo_escreve_qty_em_pt_br():
    """A mesma mancha, no outro erro do ledger: `:g` escrevia "1e-08" para o saldo de um satoshi
    e ponto decimal onde o produto é pt-BR."""
    _, erros, _ = calcular_saldos([F("2026-01-01", "BTC", "compra", 0.00000001, 350000.0),
                                   F("2026-02-01", "BTC", "venda", 0.5, 350000.0)])
    assert len(erros) == 1, erros
    assert "venda de 0,5 BTC" in erros[0], erros[0]
    assert "(0,00000001)" in erros[0], erros[0]
    assert "e-" not in erros[0], erros[0]


def test_posicoes_de_fills_devolve_o_formato_de_posicao():
    pos, erros = posicoes_de_fills(
        [F("2026-01-01", "P", "compra", 100, 30.0)], [], {"P": "acoes-br"})
    assert erros == []
    assert pos == [{"ticker": "P", "classe": "acoes-br", "conta": "c",
                    "qty": 100.0, "pm": 30.0, "moeda": "BRL"}]


def test_posicoes_de_fills_omite_posicao_zerada():
    pos, erros = posicoes_de_fills(
        [F("2026-01-01", "P", "compra", 100, 30.0), F("2026-02-01", "P", "venda", 100, 50.0)],
        [], {"P": "acoes-br"})
    assert erros == [] and pos == []


def test_posicoes_de_fills_acusa_ticker_sem_classe():
    pos, erros = posicoes_de_fills([F("2026-01-01", "P", "compra", 100, 30.0)], [], {})
    assert any("ativos.csv" in e and "P" in e for e in erros), erros
    assert pos and pos[0]["classe"] == ""


def test_propriedade_compra_mais_venda_total_zera():
    s, erros, _ = calcular_saldos([F("2026-01-01", "P", "compra", 100, 30.0),
                                   F("2026-01-05", "P", "venda", 100, 50.0)])
    assert erros == [] and s[("P", "c")].qty == 0 and s[("P", "c")].custo == 0


def test_propriedade_ordem_de_leitura_nao_altera_o_saldo():
    fills = [F("2026-01-01", "P", "compra", 60, 29.5), F("2026-03-01", "P", "compra", 40, 30.75),
             F("2026-02-01", "Q", "compra", 10, 5.0)]
    a, _, _ = calcular_saldos(fills)
    b, _, _ = calcular_saldos(list(reversed(fills)))
    assert {k: (round(v.qty, 6), round(v.custo, 6)) for k, v in a.items()} == \
           {k: (round(v.qty, 6), round(v.custo, 6)) for k, v in b.items()}


def test_propriedade_soma_dos_custos_igual_a_soma_dos_fills():
    fills = [F("2026-01-01", "P", "compra", 60, 29.5, taxa=2.9),
             F("2026-02-01", "Q", "compra", 10, 5.0, taxa=1.1)]
    s, _, _ = calcular_saldos(fills)
    esperado = sum(f["qty"] * f["preco"] + f["taxa"] for f in fills)
    assert round(sum(v.custo for v in s.values()), 6) == round(esperado, 6)


def test_propriedade_estorno_mais_fill_devolve_o_saldo_anterior():
    base, _, _ = calcular_saldos([F("2026-01-01", "P", "compra", 100, 30.0)])
    com, erros, _ = calcular_saldos([F("2026-01-01", "P", "compra", 100, 30.0),
                                     F("2026-02-01", "P", "compra", 7, 99.0, taxa=1.5),
                                     F("2026-02-01", "P", "estorno", 7, 99.0, taxa=1.5)])
    assert erros == []
    assert (round(com[("P", "c")].qty, 6), round(com[("P", "c")].custo, 6)) == \
           (round(base[("P", "c")].qty, 6), round(base[("P", "c")].custo, 6))


def test_propriedade_evento_aplicado_nao_muda_o_custo():
    a, _, _ = calcular_saldos([F("2026-01-01", "P", "compra", 100, 30.0)])
    b, _, _ = calcular_saldos([F("2026-01-01", "P", "compra", 100, 30.0)],
                              [E("2026-02-01", "P", "split", "3:1")])
    assert a[("P", "c")].custo == b[("P", "c")].custo and b[("P", "c")].qty == 300
