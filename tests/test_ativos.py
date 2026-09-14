"""dados/ativos.csv é a declaração da pessoa sobre o bloco de cada ticker — o único campo de uma
posição que não é derivável de um fill nem é fato de mercado. Estes testes cobram as duas coisas
que fazem dele uma casa canônica: última linha vence (append-only), e workspace antigo continua
valendo sem migrador."""
import pytest

from po.ativos import ler_ativos


def escreve(pasta, nome, conteudo):
    (pasta / "dados").mkdir(parents=True, exist_ok=True)
    (pasta / "dados" / f"{nome}.csv").write_text(conteudo, encoding="utf-8")


def test_le_ativos_csv_quando_existe(tmp_path):
    escreve(tmp_path, "ativos", "ticker,classe\nPETR4,acoes-br\nHGLG11,fiis\n")
    classes, erros, origem = ler_ativos(tmp_path)
    assert erros == []
    assert classes == {"PETR4": "acoes-br", "HGLG11": "fiis"}
    assert origem == "dados/ativos.csv"


def test_ultima_linha_por_ticker_vence(tmp_path):
    """anexar_csv nunca reescreve: corrigir uma classe é anexar a linha certa no fim, mesmo
    padrão de ultimas_cotacoes e da confirmação de evento."""
    escreve(tmp_path, "ativos", "ticker,classe\nPETR4,fiis\nPETR4,acoes-br\n")
    classes, erros, _ = ler_ativos(tmp_path)
    assert erros == [] and classes == {"PETR4": "acoes-br"}


def test_cai_para_posicoes_csv_quando_ativos_ausente(tmp_path):
    """A2: retrocompatível por construção. Workspace criado antes desta versão não tem ativos.csv
    e guarda a mesma declaração em posicoes.csv. Nenhum migrador, nenhum passo manual."""
    escreve(tmp_path, "posicoes",
            "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,c,100,30.00,BRL\n")
    classes, erros, origem = ler_ativos(tmp_path)
    assert erros == [] and classes == {"PETR4": "acoes-br"}
    assert origem == "dados/posicoes.csv"


def test_ativos_csv_vence_a_tabela_antiga(tmp_path):
    escreve(tmp_path, "ativos", "ticker,classe\nPETR4,fiis\n")
    escreve(tmp_path, "posicoes",
            "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,c,100,30.00,BRL\n")
    classes, _, origem = ler_ativos(tmp_path)
    assert classes == {"PETR4": "fiis"} and origem == "dados/ativos.csv"


def test_ativos_vazio_nao_desliga_a_queda_para_a_tabela_antiga(tmp_path):
    """Todo workspace saído do template nasce com um ativos.csv só de cabeçalho, e preferir o
    arquivo inteiro fazia "existe" bastar para desligar a queda. Medido: importar um extrato num
    workspace novo gravava a classe em posicoes.csv e gerar_estado.py morria com "PETR4 tem fill
    mas nenhuma classe declarada". Os dois se somam, ticker a ticker."""
    escreve(tmp_path, "ativos", "ticker,classe\n")
    escreve(tmp_path, "posicoes",
            "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,c,100,30.00,BRL\n")
    classes, erros, _ = ler_ativos(tmp_path)
    assert erros == [] and classes == {"PETR4": "acoes-br"}


def test_declaracao_nova_e_antiga_se_somam_ticker_a_ticker(tmp_path):
    escreve(tmp_path, "ativos", "ticker,classe\nPETR4,acoes-br\n")
    escreve(tmp_path, "posicoes",
            "ticker,classe,conta,qty,pm,moeda\nHGLG11,fiis,c,50,155.00,BRL\n")
    classes, erros, origem = ler_ativos(tmp_path)
    assert erros == [] and classes == {"PETR4": "acoes-br", "HGLG11": "fiis"}
    assert origem == "dados/ativos.csv"


def test_sem_nenhum_dos_dois_devolve_vazio(tmp_path):
    (tmp_path / "dados").mkdir()
    assert ler_ativos(tmp_path) == ({}, [], "nenhum")


def test_classe_fora_do_vocabulario_e_erro(tmp_path):
    escreve(tmp_path, "ativos", "ticker,classe\nPETR4,acoes\n")
    _, erros, _ = ler_ativos(tmp_path)
    assert any("classe" in e and "acoes" in e for e in erros), erros
