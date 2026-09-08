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
