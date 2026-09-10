import datetime

import pytest

from po.ingestao.inspecao import inspecionar
from po.ingestao.leitores import DependenciaAusente, Tabela, ler_tabela


def test_csv_com_cabecalho_na_primeira_linha(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text('"Date","Action","Amount"\n"08/20/2026","Buy","-$10.00"\n\n', encoding="utf-8")
    t = ler_tabela(p, {"formato": "csv"})
    assert t.cabecalho == ["Date", "Action", "Amount"]
    assert t.linhas == [["08/20/2026", "Buy", "-$10.00"]]
    assert t.linha_cabecalho == 1 and t.numero_da_linha(0) == 2


def test_csv_delimitador_e_encoding(tmp_path):
    p = tmp_path / "x.csv"
    p.write_bytes("Ativo;Preço\nPETR4;30,00\n".encode("latin-1"))
    t = ler_tabela(p, {"formato": "csv", "delimitador": ";", "encoding": "latin-1"})
    assert t.cabecalho == ["Ativo", "Preço"] and t.linhas == [["PETR4", "30,00"]]


def test_csv_encoding_errado_e_erro_acionavel(tmp_path):
    p = tmp_path / "x.csv"
    p.write_bytes("Ativo;Preço\n".encode("latin-1"))
    with pytest.raises(ValueError, match="encoding"):
        ler_tabela(p, {"formato": "csv", "delimitador": ";"})


def test_cabecalho_procurado_e_fim_em_vazio(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("Extrato da conta\nDe: 01/06 Até: 23/08\n\nMovimentação,Lançamento,Valor\n"
                 "2026-08-20,RENDIMENTOS X,5.00\n2026-08-19,TED,-1.00\n\nCLEAR CTVM,,\n", encoding="utf-8")
    t = ler_tabela(p, {"formato": "csv", "cabecalho-contem": ["Movimentação", "Valor"], "fim-em-vazio": True})
    assert t.linha_cabecalho == 4 and len(t.linhas) == 2 and t.linhas[1][1] == "TED"


def test_cabecalho_nao_encontrado(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cabeçalho não encontrado"):
        ler_tabela(p, {"formato": "csv", "cabecalho-contem": ["Zzz"]})


def test_linha_curta_e_completada_com_vazio(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b,c\n1,2\n", encoding="utf-8")
    t = ler_tabela(p, {"formato": "csv"})
    assert t.linhas == [["1", "2", ""]]


def test_arquivo_ausente(tmp_path):
    with pytest.raises(FileNotFoundError):
        ler_tabela(tmp_path / "nao.csv", {"formato": "csv"})


def test_diretorio_no_lugar_do_arquivo(tmp_path):
    (tmp_path / "umdir").mkdir()
    with pytest.raises(FileNotFoundError):
        ler_tabela(tmp_path / "umdir", {"formato": "csv"})
    with pytest.raises(FileNotFoundError):
        ler_tabela(tmp_path / "umdir", {"formato": "xlsx"})
    assert "não encontrado" in inspecionar(tmp_path / "umdir")


def test_xlsx_mantem_tipos_das_celulas(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["", "Extrato"])
    ws.append(["", "Movimentação", "Valor (R$)"])
    ws.append(["", datetime.datetime(2026, 8, 20), 5.74])
    ws.append(["", "", ""])
    ws.append(["", "Rodapé", ""])
    p = tmp_path / "x.xlsx"
    wb.save(p)
    t = ler_tabela(p, {"formato": "xlsx", "aba": 0, "cabecalho-contem": ["Movimentação"], "fim-em-vazio": True})
    assert t.cabecalho == ["", "Movimentação", "Valor (R$)"]
    assert t.linhas == [["", datetime.datetime(2026, 8, 20), 5.74]]
    assert t.linha_cabecalho == 2


def test_xlsx_aba_inexistente(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    p = tmp_path / "x.xlsx"
    wb.save(p)
    with pytest.raises(ValueError, match="aba"):
        ler_tabela(p, {"formato": "xlsx", "aba": "Extrato"})


def test_xlsx_sem_openpyxl_e_dependencia_ausente(tmp_path, monkeypatch):
    import builtins
    real = builtins.__import__

    def sem_openpyxl(nome, *a, **k):
        if nome == "openpyxl":
            raise ImportError("simulado")
        return real(nome, *a, **k)
    monkeypatch.setattr(builtins, "__import__", sem_openpyxl)
    p = tmp_path / "x.xlsx"
    p.write_bytes(b"PK")
    with pytest.raises(DependenciaAusente, match="requirements-xlsx.txt"):
        ler_tabela(p, {"formato": "xlsx"})


def test_formula_sem_valor_calculado_nao_vira_celula_vazia(tmp_path):
    """data_only=True devolve None para fórmula sem cache: uma coluna Total viraria coluna vazia,
    e com fim-em-vazio uma linha inteira de fórmulas truncaria a tabela sem erro nenhum."""
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Ativo", "Qtd", "PM", "Total"])
    ws.append(["PETR4", 100, 30, "=B2*C2"])
    p = tmp_path / "com_formula.xlsx"
    wb.save(p)
    with pytest.raises(ValueError, match="fórmula sem valor calculado"):
        ler_tabela(p, {"formato": "xlsx"})


def test_planilha_sem_formula_continua_lendo(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Ativo", "Qtd"])
    ws.append(["PETR4", 100])
    p = tmp_path / "normal.xlsx"
    wb.save(p)
    assert ler_tabela(p, {"formato": "xlsx"}).linhas == [["PETR4", 100]]


def test_inspecionar_csv_mostra_encoding_delimitador_e_amostra(tmp_path):
    p = tmp_path / "x.csv"
    p.write_bytes("Ativo;Preço\nPETR4;30,00\nHGLG11;155,00\n".encode("latin-1"))
    saida = inspecionar(p)
    assert "latin-1" in saida and "';'" in saida and "PETR4" in saida and "3 linha(s)" in saida


def test_inspecionar_xlsx_marca_cabecalho_candidato(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Planilha1"
    ws.append(["", "Extrato"])
    ws.append(["", "Movimentação", "Lançamento", "Valor (R$)"])
    p = tmp_path / "x.xlsx"
    wb.save(p)
    saida = inspecionar(p)
    assert "Planilha1" in saida and "cabeçalho candidato" in saida
