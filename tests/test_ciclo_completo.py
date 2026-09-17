import subprocess
import sys
from pathlib import Path

import pytest

from criar_workspace import criar

MOTOR = Path(__file__).resolve().parent.parent
FIX = MOTOR / "tests" / "fixtures" / "extratos"

pytestmark = pytest.mark.slow


def _roda(script, *args):
    return subprocess.run([sys.executable, str(MOTOR / "scripts" / script), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def test_extrato_ate_validador_verde(tmp_path):
    ws = criar(tmp_path / "ws", com_git=False, data="2026-09-08")

    r = _roda("importar_extrato.py", str(ws), str(FIX / "posicoes-exemplo.csv"), "--dry-run", "--data", "2026-08-01")
    assert r.returncode == 0 and "Conciliação OK" in r.stdout and "nada gravado" in r.stdout, r.stdout + r.stderr

    r = _roda("importar_extrato.py", str(ws), str(FIX / "posicoes-exemplo.csv"), "--data", "2026-08-01")
    assert r.returncode == 0 and "fills +2 (2 aberturas, tipo=saldo-inicial) · ativos +2" in r.stdout, r.stdout + r.stderr
    assert not (ws / "dados" / "posicoes.csv").exists()
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
    assert r.returncode == 0 and "0 erro(s), 2 aviso(s)" in r.stdout
    assert "nenhuma banda" in r.stdout and "perfil: ainda não preenchido" in r.stdout

    r = _roda("importar_extrato.py", str(ws), str(FIX / "posicoes-exemplo.csv"), "--data", "2026-08-01")
    assert r.returncode == 0 and "Nada novo" in r.stdout and "+" not in r.stdout.split("Log:")[0].split("Gravado")[-1]   # reimportar não duplica

    r = _roda("importar_extrato.py", str(ws), str(FIX / "posicoes-exemplo.csv"), "--data", "2026-08-01", "--conferir")
    assert r.returncode == 0 and "PETR4 (corretora-br): OK" in r.stdout


def test_fill_anexado_muda_o_estado_e_o_validador_fica_verde(tmp_path):
    """Critério 4 do 'Pronto quando' da F1, que ficou aberto: a sonda do defeito crítico, pelos
    CLIs. Um fill anexado pelo writer da ingestão (não por registrar.py) tem que aparecer no
    ESTADO gerado e deixar o validador em 0 erro(s). Antes, o gerador publicava o total antigo
    com exit 0 e o validador acusava posicoes.csv; agora não há segunda fonte para divergir."""
    from po.csvs import anexar_csv
    from test_validar_dados import copia_exemplo
    ws = copia_exemplo(tmp_path)
    anexar_csv("fills", ws / "dados" / "fills.csv", [
        {"data": "2026-09-09", "ticker": "PETR4", "tipo": "compra", "qty": 50.0, "preco": 36.0,
         "taxa": 0.0, "conta": "corretora-br", "moeda": "BRL"}])
    r = _roda("gerar_estado.py", str(ws), "--data", "2026-09-10")
    assert r.returncode == 0 and "R$ 14.000,00" in r.stdout, r.stdout + r.stderr   # 150×40 + 50×160
    r = _roda("validar_workspace.py", str(ws))
    assert r.returncode == 0 and "0 erro(s)" in r.stdout, r.stdout + r.stderr
