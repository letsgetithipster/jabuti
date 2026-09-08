from po.csvs import SCHEMAS, ler_csv


def escreve(tmp_path, nome, conteudo):
    p = tmp_path / f"{nome}.csv"
    p.write_text(conteudo, encoding="utf-8")
    return p


def test_schemas_cobrem_os_6_csvs():
    assert set(SCHEMAS) == {"posicoes", "cotacoes", "fills", "proventos", "eventos", "indices"}


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
