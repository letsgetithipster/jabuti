import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = RAIZ / "exemplos" / "workspace-exemplo"
CLI = RAIZ / "scripts" / "validar_workspace.py"
MOTOR = EXEMPLO.parent.parent


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
    # copytree não absolutiza o motor ('../..' só vale in-place) — sem isso o check
    # de config já acusaria erro e mascararia o que este teste quer exercitar.
    cfg = ws / "vault.config.yaml"
    texto = re.sub(r"motor: '[^']*'", f"motor: '{MOTOR.as_posix()}'",
                   cfg.read_text(encoding="utf-8"))
    cfg.write_text(texto, encoding="utf-8")
    cot = ws / "dados" / "cotacoes.csv"
    cot.write_text(cot.read_text(encoding="utf-8") + "2026-08-15,18:00,PETR4,37.00,BRL,manual\n",
                   encoding="utf-8")
    r = roda(str(ws))
    assert "aviso " in r.stdout
    r = roda(str(ws), "--errors-only")
    assert r.returncode == 0
    assert "aviso " not in r.stdout
    assert "aviso(s)" in r.stdout  # linha de resumo permanece
