import csv

import pytest

from po.csvs import (SCHEMAS, TABELAS_DADOS, anexar_csv, ler_csv, ultimas_cotacoes,
                     validar_linha)


def escreve(tmp_path, nome, conteudo):
    p = tmp_path / f"{nome}.csv"
    p.write_text(conteudo, encoding="utf-8")
    return p


def test_schemas_cobrem_toda_forma_que_o_motor_sabe_ler():
    """SCHEMAS é forma; TABELAS_DADOS é o que mora em dados/. `posicoes` fica em SCHEMAS porque a
    ingestão produz um registro com essa forma (que vira fill + ativo) e porque o caminho
    retrocompatível ainda lê o arquivo antigo — mas ela não é mais tabela de dados/."""
    assert set(SCHEMAS) == {"posicoes", "ativos", "cotacoes", "fills", "proventos", "eventos",
                            "indices", "movimentacoes"}
    assert SCHEMAS["ativos"] == ["ticker", "classe"]
    assert "posicoes" not in TABELAS_DADOS
    assert "ativos" in TABELAS_DADOS


def test_posicoes_ok(tmp_path):
    p = escreve(tmp_path, "posicoes",
                "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,corretora-br,100,30.00,BRL\n")
    linhas, erros = ler_csv("posicoes", p)
    assert erros == []
    assert linhas[0]["ticker"] == "PETR4"


def test_header_errado(tmp_path):
    p = escreve(tmp_path, "posicoes", "ticker,qty\nPETR4,100\n")
    _, erros = ler_csv("posicoes", p)
    assert any("header" in e for e in erros)


def test_classe_fora_do_vocabulario(tmp_path):
    p = escreve(tmp_path, "posicoes",
                "ticker,classe,conta,qty,pm,moeda\nPETR4,ações,corretora-br,100,30.00,BRL\n")
    _, erros = ler_csv("posicoes", p)
    assert any("classe" in e for e in erros)


def test_numero_invalido(tmp_path):
    p = escreve(tmp_path, "posicoes",
                "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,corretora-br,cem,30.00,BRL\n")
    _, erros = ler_csv("posicoes", p)
    assert any("qty" in e for e in erros)


def test_data_invalida(tmp_path):
    p = escreve(tmp_path, "fills",
                "data,ticker,tipo,qty,preco,taxa,conta,moeda\n08/09/2026,PETR4,compra,10,30,0,c1,BRL\n")
    _, erros = ler_csv("fills", p)
    assert any("data" in e for e in erros)


def test_tipo_de_fill_invalido(tmp_path):
    p = escreve(tmp_path, "fills",
                "data,ticker,tipo,qty,preco,taxa,conta,moeda\n2026-09-08,PETR4,doacao,10,30,0,c1,BRL\n")
    _, erros = ler_csv("fills", p)
    assert any("tipo" in e for e in erros)


def test_csv_vazio_so_header_ok(tmp_path):
    p = escreve(tmp_path, "eventos", "data,ticker,tipo,razao,confirmado\n")
    linhas, erros = ler_csv("eventos", p)
    assert linhas == [] and erros == []


def test_linha_com_coluna_a_menos(tmp_path):
    p = escreve(tmp_path, "posicoes",
                "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,corretora-br,100,30.00\n")
    _, erros = ler_csv("posicoes", p)
    assert any("a menos" in e for e in erros)


def test_linha_com_coluna_a_mais(tmp_path):
    p = escreve(tmp_path, "posicoes",
                "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,corretora-br,100,30.00,BRL,EXTRA\n")
    _, erros = ler_csv("posicoes", p)
    assert any("a mais" in e for e in erros)


def test_numerico_volta_como_float(tmp_path):
    p = escreve(tmp_path, "posicoes",
                "ticker,classe,conta,qty,pm,moeda\nBTC,cripto,exchange,0.015,350000.00,BRL\n")
    linhas, erros = ler_csv("posicoes", p)
    assert erros == []
    assert linhas[0]["qty"] == 0.015 and isinstance(linhas[0]["qty"], float)


def test_formato_humano_rejeitado_no_canonico(tmp_path):
    p = escreve(tmp_path, "posicoes",
                "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,c1,100,\"1.234,56\",BRL\n")
    _, erros = ler_csv("posicoes", p)
    assert any("pm" in e for e in erros)


def test_campo_obrigatorio_vazio(tmp_path):
    p = escreve(tmp_path, "posicoes",
                "ticker,classe,conta,qty,pm,moeda\n,acoes-br,c1,100,30.00,BRL\n")
    _, erros = ler_csv("posicoes", p)
    assert any("ticker" in e and "vazio" in e for e in erros)


def test_cnpj_opcional_em_proventos(tmp_path):
    p = escreve(tmp_path, "proventos",
                "data,ticker,cnpj,tipo,valor_bruto,valor_liquido,conta,moeda\n"
                "2026-09-05,MSFT,,dividendo,10.00,7.00,corretora-us,USD\n")
    _, erros = ler_csv("proventos", p)
    assert erros == []


def test_data_impossivel(tmp_path):
    p = escreve(tmp_path, "indices",
                "data,indice,valor,fonte\n2026-13-45,ibov,140000,manual\n")
    _, erros = ler_csv("indices", p)
    assert any("data" in e for e in erros)


def test_bom_aceito(tmp_path):
    p = tmp_path / "cotacoes.csv"
    p.write_bytes("﻿data,hora,ticker,preco,moeda,fonte\n2026-09-08,18:00,PETR4,40.00,BRL,manual\n".encode("utf-8"))
    linhas, erros = ler_csv("cotacoes", p)
    assert erros == [] and linhas[0]["preco"] == 40.0


def test_espaco_nas_bordas(tmp_path):
    p = escreve(tmp_path, "posicoes",
                "ticker,classe,conta,qty,pm,moeda\n PETR4 ,acoes-br,c1,100,30.00,BRL\n")
    _, erros = ler_csv("posicoes", p)
    assert any("bordas" in e for e in erros)


def test_fill_qty_negativa_e_erro(tmp_path):
    p = escreve(tmp_path, "fills",
                "data,ticker,tipo,qty,preco,taxa,conta,moeda\n2026-09-08,PETR4,venda,-40,30.00,0,c1,BRL\n")
    _, erros = ler_csv("fills", p)
    assert any("positiva" in e for e in erros)


def test_posicao_qty_zero_e_erro(tmp_path):
    p = escreve(tmp_path, "posicoes",
                "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,c1,0,30.00,BRL\n")
    _, erros = ler_csv("posicoes", p)
    assert any("positiva" in e for e in erros)


def test_csv_nao_utf8_vira_erro(tmp_path):
    p = tmp_path / "posicoes.csv"
    p.write_bytes("ticker,classe,conta,qty,pm,moeda\nAÇÃO,acoes-br,c1,1,1.00,BRL\n".encode("latin-1"))
    linhas, erros = ler_csv("posicoes", p)
    assert linhas == []
    assert any("UTF-8" in e for e in erros)


def test_csv_utf16_vira_erro(tmp_path):
    p = tmp_path / "posicoes.csv"
    p.write_bytes("ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,c1,1,1.00,BRL\n".encode("utf-16"))
    linhas, erros = ler_csv("posicoes", p)
    assert linhas == []
    assert erros


def _csv(tmp_path, nome, conteudo):
    p = tmp_path / f"{nome}.csv"
    p.write_text(conteudo, encoding="utf-8")
    return p


def test_saldo_inicial_e_tipo_de_fill_valido(tmp_path):
    p = _csv(tmp_path, "fills", "data,ticker,tipo,qty,preco,taxa,conta,moeda\n"
             "2026-08-01,HGLG11,saldo-inicial,50,155.00,0,corretora-br,BRL\n")
    linhas, erros = ler_csv("fills", p)
    assert erros == [] and linhas[0]["tipo"] == "saldo-inicial"


def test_provento_tipo_fora_do_vocabulario(tmp_path):
    p = _csv(tmp_path, "proventos", "data,ticker,cnpj,tipo,valor_bruto,valor_liquido,conta,moeda\n"
             "2026-09-05,HGLG11,,bonus,55.00,55.00,corretora-br,BRL\n")
    _, erros = ler_csv("proventos", p)
    assert any("tipo" in e and "vocabulário" in e for e in erros)


def test_evento_tipo_e_confirmado(tmp_path):
    p = _csv(tmp_path, "eventos", "data,ticker,tipo,razao,confirmado\n"
             "2026-09-05,PETR4,desdobramento,2:1,sim\n"
             "2026-09-06,PETR4,split,2:1,talvez\n")
    _, erros = ler_csv("eventos", p)
    assert any("eventos.csv:2" in e and "tipo" in e for e in erros)
    assert any("eventos.csv:3" in e and "confirmado" in e for e in erros)


def test_indice_fora_do_vocabulario(tmp_path):
    p = _csv(tmp_path, "indices", "data,indice,valor,fonte\n2026-08-31,dow,40000,manual\n")
    _, erros = ler_csv("indices", p)
    assert any("indice" in e and "vocabulário" in e for e in erros)


def test_fonte_de_cotacao_fora_do_vocabulario(tmp_path):
    p = _csv(tmp_path, "cotacoes", "data,hora,ticker,preco,moeda,fonte\n"
             "2026-09-08,18:00,PETR4,40.00,BRL,chute\n")
    _, erros = ler_csv("cotacoes", p)
    assert any("fonte" in e and "vocabulário" in e for e in erros)


def test_hora_invalida(tmp_path):
    p = _csv(tmp_path, "cotacoes", "data,hora,ticker,preco,moeda,fonte\n"
             "2026-09-08,25:00,PETR4,40.00,BRL,manual\n"
             "2026-09-08,9h,PETR4,40.00,BRL,manual\n")
    _, erros = ler_csv("cotacoes", p)
    assert len([e for e in erros if "hora" in e and "HH:MM" in e]) == 2


def test_moeda_fora_do_vocabulario(tmp_path):
    p = _csv(tmp_path, "posicoes", "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,corretora-br,100,30.00,reais\n")
    _, erros = ler_csv("posicoes", p)
    assert any("moeda" in e and "vocabulário" in e for e in erros)


def test_validar_linha_aceita_float_ja_convertido():
    linha = {"ticker": "PETR4", "classe": "acoes-br", "conta": "c", "qty": 10.0, "pm": 30.0, "moeda": "BRL"}
    assert validar_linha("posicoes", linha, "ingestão:1") == []
    linha["qty"] = -1.0
    assert any("positiva" in e for e in validar_linha("posicoes", linha, "ingestão:1"))


def test_ultimas_cotacoes_por_data_linha_desempata():
    cot = [
        {"data": "2026-09-08", "ticker": "PETR4", "preco": 40.0},
        {"data": "2026-09-01", "ticker": "PETR4", "preco": 38.0},   # append fora de ordem
        {"data": "2026-09-08", "ticker": "PETR4", "preco": 41.0},   # mesma data: última linha vence
        {"data": "2026-09-08", "ticker": "HGLG11", "preco": 160.0},
    ]
    u = ultimas_cotacoes(cot)
    assert u["PETR4"]["preco"] == 41.0 and u["HGLG11"]["preco"] == 160.0


def test_anexar_csv_cria_e_anexa_em_formato_canonico(tmp_path):
    p = tmp_path / "cotacoes.csv"
    assert anexar_csv("cotacoes", p, [{"data": "2026-09-08", "hora": "18:00", "ticker": "PETR4",
                                       "preco": 40.0, "moeda": "BRL", "fonte": "manual"}]) == 1
    assert p.read_text(encoding="utf-8") == ("data,hora,ticker,preco,moeda,fonte\n"
                                             "2026-09-08,18:00,PETR4,40,BRL,manual\n")
    # arquivo existente SEM quebra de linha final: anexa sem colar na última linha
    p.write_text(p.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")
    anexar_csv("cotacoes", p, [{"data": "2026-09-09", "hora": "18:00", "ticker": "PETR4",
                                "preco": 5.4321, "moeda": "BRL", "fonte": "manual"}])
    linhas, erros = ler_csv("cotacoes", p)
    assert erros == [] and [l["preco"] for l in linhas] == [40.0, 5.4321]


def test_anexar_csv_recusa_texto_humano_em_campo_numerico(tmp_path):
    p = tmp_path / "cotacoes.csv"
    with pytest.raises(ValueError, match="formato canônico"):
        anexar_csv("cotacoes", p, [{"data": "2026-09-08", "hora": "18:00", "ticker": "PETR4",
                                    "preco": "1.234,56", "moeda": "BRL", "fonte": "manual"}])
    assert not p.exists() or p.read_text(encoding="utf-8") == ""


def test_anexar_csv_valida_texto_e_vocabulario_antes_de_gravar(tmp_path):
    p = tmp_path / "cotacoes.csv"
    base = {"data": "2026-09-08", "ticker": "PETR4", "preco": 40.0, "moeda": "BRL"}
    with pytest.raises(ValueError, match="hora"):
        anexar_csv("cotacoes", p, [dict(base, hora="18:00:00", fonte="yahoo")])
    with pytest.raises(ValueError, match="fonte"):
        anexar_csv("cotacoes", p, [dict(base, hora="18:00", fonte="chute")])
    assert not p.exists()


def test_anexar_csv_recusa_header_diferente(tmp_path):
    p = tmp_path / "cotacoes.csv"
    p.write_text("data,ticker,preco\n2026-09-08,PETR4,40\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        anexar_csv("cotacoes", p, [{"data": "2026-09-08", "hora": "18:00", "ticker": "PETR4",
                                    "preco": 40.0, "moeda": "BRL", "fonte": "manual"}])
    assert p.read_text(encoding="utf-8") == "data,ticker,preco\n2026-09-08,PETR4,40\n"


def test_anexar_csv_lista_vazia_nao_toca_o_disco(tmp_path):
    p = tmp_path / "cotacoes.csv"
    assert anexar_csv("cotacoes", p, []) == 0 and not p.exists()


def test_anexar_csv_arquivo_so_com_bom_e_novo(tmp_path):
    p = tmp_path / "cotacoes.csv"
    p.write_bytes(b"\xef\xbb\xbf")
    anexar_csv("cotacoes", p, [{"data": "2026-09-08", "hora": "18:00", "ticker": "PETR4",
                                "preco": 40.0, "moeda": "BRL", "fonte": "manual"}])
    linhas, erros = ler_csv("cotacoes", p)
    assert erros == [] and len(linhas) == 1


def test_validar_linha_int_nao_finito_tipo_errado_e_chave_faltando():
    linha = {"ticker": "PETR4", "classe": "acoes-br", "conta": "c", "qty": 10, "pm": 30, "moeda": "BRL"}
    assert validar_linha("posicoes", linha, "x") == []
    assert linha["qty"] == 10.0 and isinstance(linha["qty"], float)
    linha["qty"] = 0
    assert any("positiva" in e for e in validar_linha("posicoes", linha, "x"))
    linha["qty"] = float("nan")
    assert any("não finito" in e for e in validar_linha("posicoes", linha, "x"))
    linha = {"ticker": 40.0, "classe": "acoes-br", "conta": "c", "qty": 1.0, "pm": 1.0, "moeda": "BRL"}
    assert any("ticker" in e and "deve ser texto" in e for e in validar_linha("posicoes", linha, "x"))
    with pytest.raises(ValueError, match="sem os campos"):
        validar_linha("posicoes", {"ticker": "PETR4"}, "x")


def test_indices_fonte_no_vocabulario(tmp_path):
    p = _csv(tmp_path, "indices", "data,indice,valor,fonte\n2026-08-31,ibov,140000,chute\n")
    _, erros = ler_csv("indices", p)
    assert any("fonte" in e and "vocabulário" in e for e in erros)


def _provento(bruto, liquido):
    return {"data": "2026-08-20", "ticker": "WELL", "cnpj": "", "tipo": "dividendo",
            "valor_bruto": bruto, "valor_liquido": liquido, "conta": "corretora-us", "moeda": "USD"}


def test_provento_liquido_de_sinal_oposto_ao_bruto_e_erro():
    """Retenção não inverte o sinal de um provento. Sem esta régua, um ajuste de imposto com um
    dígito a mais (-15,30 no lugar de -1,53 sobre dividendo de 5,10) gravava líquido NEGATIVO, e
    a conciliação declarava a linha conferida porque compara valor_bruto com a célula de onde ele
    saiu — valor_liquido, o campo que o ajuste move, não era conferido por nada."""
    erros = validar_linha("proventos", _provento(5.10, -10.20), "linha 2")
    assert any("sinal oposto" in e and "linha 2" in e for e in erros)


def test_provento_liquido_maior_que_bruto_em_modulo_e_erro():
    assert any("maior que valor_bruto" in e
               for e in validar_linha("proventos", _provento(5.10, 7.00), "linha 2"))
    assert any("maior que valor_bruto" in e
               for e in validar_linha("proventos", _provento(-5.10, -7.00), "linha 2"))


@pytest.mark.parametrize("bruto,liquido,porque", [
    (5.10, 3.57, "caso normal do NRA tax adj da Schwab"),
    (-5.10, -5.10, "estorno: os dois negativos, mesmo módulo"),
    (5.10, 0.0, "retenção levou tudo"),
    (5.10, 5.10, "sem retenção: líquido igual ao bruto"),
])
def test_provento_com_retencao_plausivel_passa(bruto, liquido, porque):
    assert validar_linha("proventos", _provento(bruto, liquido), "linha 2") == [], porque


def test_provento_invariante_tambem_vale_lendo_do_csv(tmp_path):
    p = _csv(tmp_path, "proventos", "data,ticker,cnpj,tipo,valor_bruto,valor_liquido,conta,moeda\n"
             "2026-08-20,WELL,,dividendo,5.10,-10.20,corretora-us,USD\n")
    _, erros = ler_csv("proventos", p)
    assert any("sinal oposto" in e for e in erros)


# --- I2: preço não-positivo é recusado pela régua única, com pista diferente por caso ---

def test_preco_zero_recusado_com_pista_de_ativo_parado(tmp_path):
    """A guarda existia quatro vezes nas bordas, uma por provider, e faltava na régua única:
    preço 0 vindo do arquivo zerava o bloco inteiro com o validador verde."""
    p = escreve(tmp_path, "cotacoes",
                "data,hora,ticker,preco,moeda,fonte\n2026-09-08,18:00,PETR4,0,BRL,manual\n")
    _, erros = ler_csv("cotacoes", p)
    assert any("preço deve ser positivo (veio 0)" in e and "ativo parado" in e for e in erros)


def test_preco_negativo_recusado_com_pista_de_sinal(tmp_path):
    """Preço negativo dava patrimônio negativo com percentual de -100%. Pista diferente da do
    zero: aqui o que a pessoa tem que olhar é o sinal da linha, não a fonte."""
    p = escreve(tmp_path, "cotacoes",
                "data,hora,ticker,preco,moeda,fonte\n2026-09-08,18:00,PETR4,-40.00,BRL,manual\n")
    _, erros = ler_csv("cotacoes", p)
    assert any("preço deve ser positivo (veio -40)" in e and "confira o sinal" in e for e in erros)
    assert not any("ativo parado" in e for e in erros)


def test_preco_nao_positivo_recusado_tambem_vindo_da_ingestao():
    """A régua é a mesma para o que vem de arquivo e para o que vem de parser, antes de gravar."""
    linha = {"data": "2026-09-08", "hora": "18:00", "ticker": "PETR4", "preco": 0.0,
             "moeda": "BRL", "fonte": "yahoo"}
    assert any("positivo" in e for e in validar_linha("cotacoes", linha, "ingestão:1"))


def test_valor_de_indice_nao_positivo_recusado(tmp_path):
    p = escreve(tmp_path, "indices", "data,indice,valor,fonte\n2026-08-31,ibov,0,manual\n")
    _, erros = ler_csv("indices", p)
    assert any("valor de índice deve ser positivo" in e for e in erros)


# --- N1: o desempate da cotação vencedora olha a hora, não só a data ---

def test_ultimas_cotacoes_desempata_por_hora_nao_por_ordem_do_arquivo():
    """Comparando só a data, a linha das 09:00 appendada depois vencia a das 18:00 do mesmo dia,
    em silêncio: é o que acontece no primeiro backfill, reordenação ou série histórica."""
    cot = [
        {"data": "2026-09-08", "hora": "18:00", "ticker": "PETR4", "preco": 40.0},
        {"data": "2026-09-08", "hora": "09:00", "ticker": "PETR4", "preco": 35.0},
    ]
    assert ultimas_cotacoes(cot)["PETR4"]["preco"] == 40.0


def test_ultimas_cotacoes_mesma_hora_ainda_desempata_pela_ultima_linha():
    """Empate de (data, hora) mantém a regra antiga: a última linha do arquivo é a boa."""
    cot = [
        {"data": "2026-09-08", "hora": "18:00", "ticker": "PETR4", "preco": 40.0},
        {"data": "2026-09-08", "hora": "18:00", "ticker": "PETR4", "preco": 41.0},
    ]
    assert ultimas_cotacoes(cot)["PETR4"]["preco"] == 41.0


def _mov(**campos):
    linha = {"data": "2026-09-01", "descricao": "PIX RECEBIDO", "valor": 1500.0, "moeda": "BRL",
             "conta": "corretora-br", "categoria_origem": "Transferências", "origem": "manual",
             "id_externo": "abc-123", "data_referencia": "2026-09-02"}
    linha.update(campos)
    return linha


def test_movimentacao_aceita_valor_negativo():
    """Gasto é negativo e receita é positiva: é o ponto da tabela. Ao contrário de qty e preço,
    aqui o sinal carrega significado e não pode ser barrado."""
    assert validar_linha("movimentacoes", _mov(valor=-89.90), "x:2") == []


def test_movimentacao_exige_data_de_referencia_do_provider():
    """Número de API sem idade declarada é pior que número de planilha, porque parece fresco."""
    erros = validar_linha("movimentacoes", _mov(data_referencia=""), "x:2")
    assert any("data_referencia" in e and "vazio" in e for e in erros)


def test_data_de_referencia_e_validada_como_data():
    erros = validar_linha("movimentacoes", _mov(data_referencia="02/09/2026"), "x:2")
    assert any("YYYY-MM-DD" in e for e in erros)


def test_movimentacao_exige_id_externo():
    """Sem ele, a reimportação depende de heurística de chave natural, que é frágil quando o
    mesmo lançamento volta em duas sincronizações."""
    erros = validar_linha("movimentacoes", _mov(id_externo=""), "x:2")
    assert any("id_externo" in e and "vazio" in e for e in erros)


def test_descricao_e_categoria_sao_opcionais():
    """Provider pode devolver lançamento sem descrição ou sem categoria. Isso não é erro de dado."""
    assert validar_linha("movimentacoes", _mov(descricao="", categoria_origem=""), "x:2") == []


def test_origem_tem_vocabulario_fechado():
    erros = validar_linha("movimentacoes", _mov(origem="banco-do-fulano"), "x:2")
    assert any("origem" in e and "vocabulário" in e for e in erros)


def test_nenhum_campo_canonico_carrega_nome_de_fornecedor():
    """O CSV canônico é o produto e o provider é acessório. No dia em que um campo se chamar
    como um fornecedor, trocar de fornecedor deixa de ser barato — e a spec §6.1 inteira cai.
    `origem` guarda o nome do fornecedor como VALOR, que é o lugar certo dele."""
    fornecedores = ("finnest", "pluggy", "belvo", "klavi", "yahoo", "brapi", "openfinance")
    for tabela, campos in SCHEMAS.items():
        for campo in campos:
            assert not any(f in campo.lower() for f in fornecedores), \
                f"{tabela}.{campo} carrega nome de fornecedor no NOME do campo"


def test_movimentacao_sinal_sobrevive_ao_round_trip_pelo_arquivo(tmp_path):
    """O caminho unitário (validar_linha) e o caminho de arquivo (anexar_csv → ler_csv) podem
    divergir — é a lição de test_provento_invariante_tambem_vale_lendo_do_csv e
    test_preco_nao_positivo_recusado_tambem_vindo_da_ingestao. Para movimentacoes o sinal É o
    dado: gasto negativo tem que sobreviver a _celula → formatar_canonico → CSV → ler_csv, e
    -0.0 tem que normalizar para 0 sem virar um '-0' que confunde leitura humana do CSV."""
    p = tmp_path / "movimentacoes.csv"
    anexar_csv("movimentacoes", p, [
        _mov(descricao="MERCADINHO", valor=-89.90, id_externo="ext-1"),
        _mov(descricao="ESTORNO", valor=-0.0, id_externo="ext-2"),
    ])
    linhas, erros = ler_csv("movimentacoes", p)
    assert erros == []
    assert [l["valor"] for l in linhas] == [-89.90, 0.0]
    linhas_csv = p.read_text(encoding="utf-8").splitlines()
    campo_valor = SCHEMAS["movimentacoes"].index("valor")
    valor_gasto = next(csv.reader([linhas_csv[1]]))[campo_valor]
    valor_estorno = next(csv.reader([linhas_csv[2]]))[campo_valor]
    assert valor_gasto == "-89.9"
    assert valor_estorno == "0"  # sem sinal fantasma: -0.0 canoniza para "0", não "-0"
