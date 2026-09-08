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


def test_dados_com_erro_suspende_com_aviso(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    (ws / "dados" / "posicoes.csv").write_text(
        "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,corretora-br,cem,30.00,BRL\n",
        encoding="utf-8")
    erros, avisos = checar_estado(ws)
    assert erros == []
    assert any("suspenso" in a for a in avisos)
