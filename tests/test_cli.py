import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = RAIZ / "exemplos" / "workspace-exemplo"
CLI = RAIZ / "scripts" / "validar_workspace.py"


def roda(*args):
    return subprocess.run([sys.executable, str(CLI), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def test_cli_exemplo_exit_0():
    r = roda(str(EXEMPLO))
    assert r.returncode == 0
    assert "0 erro(s)" in r.stdout


def test_cli_workspace_quebrado_exit_1(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    estado = ws / "estado" / "ESTADO.md"
    estado.write_text(estado.read_text(encoding="utf-8").replace("R$ 12.000,00", "R$ 1,00"),
                      encoding="utf-8")
    r = roda(str(ws))
    assert r.returncode == 1
    assert "ERRO" in r.stdout


def test_cli_errors_only_omite_avisos(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    cot = ws / "dados" / "cotacoes.csv"
    linhas = [l for l in cot.read_text(encoding="utf-8").splitlines() if "HGLG11" not in l]
    cot.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    r = roda(str(ws), "--errors-only")
    assert "aviso " not in r.stdout
    assert "aviso(s)" in r.stdout  # linha de resumo permanece
