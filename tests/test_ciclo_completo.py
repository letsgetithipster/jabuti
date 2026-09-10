import subprocess
import sys
from pathlib import Path

from criar_workspace import criar

MOTOR = Path(__file__).resolve().parent.parent
FIX = MOTOR / "tests" / "fixtures" / "extratos"


def _roda(script, *args):
    return subprocess.run([sys.executable, str(MOTOR / "scripts" / script), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def test_extrato_ate_validador_verde(tmp_path):
    ws = criar(tmp_path / "ws", com_git=False, data="2026-09-08")

    r = _roda("importar_extrato.py", str(ws), str(FIX / "posicoes-exemplo.csv"), "--dry-run", "--data", "2026-08-01")
    assert r.returncode == 0 and "Conciliação OK" in r.stdout and "nada gravado" in r.stdout, r.stdout + r.stderr

    r = _roda("importar_extrato.py", str(ws), str(FIX / "posicoes-exemplo.csv"), "--data", "2026-08-01")
    assert r.returncode == 0 and "posicoes +2" in r.stdout and "fills +2" in r.stdout, r.stdout + r.stderr
    assert list((ws / "logs" / "importacoes").glob("*.md"))

    r = _roda("validar_workspace.py", str(ws), "--errors-only")
    assert r.returncode == 1 and r.stdout.count("sem nenhuma cotação") == 2

    r = _roda("atualizar_cotacoes.py", str(ws), "--manual", "PETR4=40", "HGLG11=160")
    assert r.returncode == 0 and "+2" in r.stdout, r.stdout + r.stderr

    r = _roda("validar_workspace.py", str(ws), "--errors-only")
    assert r.returncode == 1 and "Total investido" in r.stdout      # ESTADO velho: o gerador resolve

    r = _roda("gerar_estado.py", str(ws))
    assert r.returncode == 0 and "R$ 12.000,00" in r.stdout, r.stdout + r.stderr

    r = _roda("validar_workspace.py", str(ws))
    assert r.returncode == 0 and "0 erro(s), 1 aviso(s)" in r.stdout and "nenhuma banda" in r.stdout

    r = _roda("importar_extrato.py", str(ws), str(FIX / "posicoes-exemplo.csv"), "--data", "2026-08-01")
    assert r.returncode == 0 and "Nada novo" in r.stdout and "posicoes 2" in r.stdout   # reimportar não duplica

    r = _roda("importar_extrato.py", str(ws), str(FIX / "posicoes-exemplo.csv"), "--data", "2026-08-01", "--conferir")
    assert r.returncode == 0 and "PETR4 (corretora-br): OK" in r.stdout
