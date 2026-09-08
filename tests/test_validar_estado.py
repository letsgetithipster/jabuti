import shutil
from pathlib import Path

from po.validar.check_estado import checar_estado

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"


def test_exemplo_total_bate():
    erros, _ = checar_estado(EXEMPLO)
    assert erros == []


def test_total_divergente_e_erro(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    estado = ws / "estado" / "ESTADO.md"
    texto = estado.read_text(encoding="utf-8")
    estado.write_text(texto.replace("R$ 12.000,00", "R$ 99.000,00"), encoding="utf-8")
    erros, _ = checar_estado(ws)
    assert any("Total investido" in e for e in erros)


def test_ticker_sem_cotacao_vira_aviso(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    cot = ws / "dados" / "cotacoes.csv"
    linhas = [l for l in cot.read_text(encoding="utf-8").splitlines() if "HGLG11" not in l]
    cot.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    erros, avisos = checar_estado(ws)
    assert erros == []      # sem cotação para todos, o check do total é suspenso...
    assert any("HGLG11" in a for a in avisos)   # ...mas avisa


def test_ultima_cotacao_por_data_nao_por_linha(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    cot = ws / "dados" / "cotacoes.csv"
    cot.write_text(cot.read_text(encoding="utf-8") +
                   "2026-09-01,18:00,PETR4,10.00,BRL,manual\n", encoding="utf-8")
    erros, _ = checar_estado(ws)
    assert erros == []  # linha velha appendada depois não vence a data mais nova


def test_moeda_nao_brl_suspende(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    pos = ws / "dados" / "posicoes.csv"
    pos.write_text(pos.read_text(encoding="utf-8") +
                   "VOO,rv-int,corretora-br,2,500.00,USD\n", encoding="utf-8")
    cot = ws / "dados" / "cotacoes.csv"
    cot.write_text(cot.read_text(encoding="utf-8") +
                   "2026-09-08,18:00,VOO,510.00,USD,manual\n", encoding="utf-8")
    erros, avisos = checar_estado(ws)
    assert erros == []
    assert any("BRL" in a for a in avisos)


def test_mensagem_de_divergencia_em_ptbr(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    estado = ws / "estado" / "ESTADO.md"
    estado.write_text(estado.read_text(encoding="utf-8").replace("R$ 12.000,00", "R$ 9.000,00"),
                      encoding="utf-8")
    erros, _ = checar_estado(ws)
    assert any("R$ 9.000,00" in e and "12.000,00" in e for e in erros)


def test_dados_com_erro_suspende_com_aviso(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    (ws / "dados" / "posicoes.csv").write_text(
        "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,corretora-br,cem,30.00,BRL\n",
        encoding="utf-8")
    erros, avisos = checar_estado(ws)
    assert erros == []
    assert any("suspenso" in a for a in avisos)


def test_estado_nao_utf8_vira_erro(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    (ws / "estado" / "ESTADO.md").write_bytes(
        "---\ntipo: estado\n---\nTotal investido: R$ 1,00 ação\n".encode("latin-1"))
    erros, _ = checar_estado(ws)
    assert any("UTF-8" in e for e in erros)
