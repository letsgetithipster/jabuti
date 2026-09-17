"""Contrato do CLI que escreve o que a PESSOA fez, por subprocesso de verdade.

É a outra metade da camada 1 do GUARDRAILS: preço de mercado entra por script de cotação;
operação sua entra por aqui, com eco, --dry-run e log datado."""
import subprocess
import sys
from pathlib import Path

from test_validar_dados import copia_exemplo

RAIZ = Path(__file__).resolve().parent.parent
CLI = RAIZ / "scripts" / "registrar.py"


def roda(ws, *args):
    return subprocess.run([sys.executable, str(CLI), str(ws), *args], input="",
                          capture_output=True, text=True, encoding="utf-8")


def fills(ws):
    return (ws / "dados" / "fills.csv").read_text(encoding="utf-8")


def test_compra_grava_um_fill_e_o_ledger_ve(tmp_path):
    ws = copia_exemplo(tmp_path)
    r = roda(ws, "compra", "PETR4", "50", "36,00", "--taxa", "2,90",
             "--data", "2026-09-05", "--sim")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "custo total R$ 1.802,90" in r.stdout
    assert "saldo depois: 150 @ R$ 32,02" in r.stdout
    assert "fills +1" in r.stdout
    assert fills(ws).strip().splitlines()[-1] == \
        "2026-09-05,PETR4,compra,50,36,2.9,corretora-br,BRL"


def test_dry_run_nao_toca_dados(tmp_path):
    ws = copia_exemplo(tmp_path)
    antes = fills(ws)
    r = roda(ws, "compra", "PETR4", "50", "36,00", "--dry-run")
    assert r.returncode == 0 and "--dry-run: nada gravado" in r.stdout
    assert fills(ws) == antes


def test_sem_sim_e_sem_terminal_nao_grava_e_diz_como(tmp_path):
    """Pergunta interativa dentro de uma skill é travamento, não guardrail."""
    ws = copia_exemplo(tmp_path)
    antes = fills(ws)
    r = roda(ws, "compra", "PETR4", "50", "36,00")
    assert r.returncode == 3, r.stdout
    assert "--sim" in r.stdout and "nada gravado" in r.stdout.lower()
    assert fills(ws) == antes


def test_ticker_sem_classe_recusa_e_entrega_o_comando(tmp_path):
    ws = copia_exemplo(tmp_path)
    r = roda(ws, "compra", "ITSA4", "10", "10,00", "--sim")
    assert r.returncode == 1
    assert "ITSA4=" in r.stdout and " ativo " in r.stdout
    assert "ITSA4" not in fills(ws)


def test_ativo_declara_a_classe_e_a_compra_passa(tmp_path):
    ws = copia_exemplo(tmp_path)
    assert roda(ws, "ativo", "ITSA4=acoes-br").returncode == 0
    assert "ITSA4,acoes-br" in (ws / "dados" / "ativos.csv").read_text(encoding="utf-8")
    r = roda(ws, "compra", "ITSA4", "10", "10,00", "--sim")
    assert r.returncode == 0, r.stdout


def test_ativo_recusa_classe_fora_do_vocabulario(tmp_path):
    ws = copia_exemplo(tmp_path)
    r = roda(ws, "ativo", "ITSA4=acoes")
    assert r.returncode == 1 and "acoes-br" in r.stdout


def test_venda_acima_do_saldo_recusa_com_a_frase_do_ledger(tmp_path):
    """O CLI não tem aritmética própria: quem recusa é o ledger, e a frase é a dele."""
    ws = copia_exemplo(tmp_path)
    r = roda(ws, "venda", "PETR4", "500", "41,00", "--sim")
    assert r.returncode == 1 and "excede o saldo" in r.stdout
    assert ",venda," not in fills(ws)


def test_venda_imprime_o_resultado_realizado(tmp_path):
    ws = copia_exemplo(tmp_path)
    r = roda(ws, "venda", "PETR4", "50", "41,00", "--data", "2026-10-02", "--sim")
    assert r.returncode == 0, r.stdout
    assert "resultado realizado R$ 550,00" in r.stdout
    assert "saldo depois: 50 @ R$ 30,00" in r.stdout


def test_o_log_nasce_datado_e_declara_a_procedencia(tmp_path):
    ws = copia_exemplo(tmp_path)
    roda(ws, "compra", "PETR4", "50", "36,00", "--data", "2026-09-05", "--sim")
    log = ws / "logs" / "aportes" / "2026-09-05-PETR4.md"
    assert log.exists()
    texto = log.read_text(encoding="utf-8")
    assert "declarado-por-voce" in texto
    assert "não conferidos contra documento" in texto
    # O fluxo real da rotina: registrou, regerou o ESTADO, validou. O validador cobre logs/, então
    # o frontmatter do log nasce no vocabulário de check_frontmatter ou nada disto passa.
    g = subprocess.run([sys.executable, str(RAIZ / "scripts" / "gerar_estado.py"), str(ws),
                        "--data", "2026-09-08"], capture_output=True, text=True, encoding="utf-8")
    assert g.returncode == 0, g.stdout + g.stderr
    v = subprocess.run([sys.executable, str(RAIZ / "scripts" / "validar_workspace.py"), str(ws)],
                       capture_output=True, text=True, encoding="utf-8")
    assert v.returncode == 0 and "0 erro(s)" in v.stdout, v.stdout
