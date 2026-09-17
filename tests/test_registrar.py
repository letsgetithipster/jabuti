"""Contrato do CLI que escreve o que a PESSOA fez, por subprocesso de verdade.

É a outra metade da camada 1 do GUARDRAILS: preço de mercado entra por script de cotação;
operação sua entra por aqui, com eco, --dry-run e log datado."""
import subprocess
import sys
from pathlib import Path

from po.csvs import ler_csv
from po.ledger import posicoes_de_fills
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


def proventos(ws):
    return (ws / "dados" / "proventos.csv").read_text(encoding="utf-8")


def saldos(ws):
    linhas, erros = ler_csv("fills", ws / "dados" / "fills.csv")
    assert erros == [], erros
    pos, erros = posicoes_de_fills(linhas, classes={"PETR4": "acoes-br", "HGLG11": "fiis"})
    assert erros == [], erros
    return {(p["ticker"], p["conta"]): (p["qty"], round(p["pm"], 4)) for p in pos}


def valida(ws):
    g = subprocess.run([sys.executable, str(RAIZ / "scripts" / "gerar_estado.py"), str(ws),
                        "--data", "2026-09-08"], capture_output=True, text=True, encoding="utf-8")
    assert g.returncode == 0, g.stdout + g.stderr
    return subprocess.run([sys.executable, str(RAIZ / "scripts" / "validar_workspace.py"), str(ws)],
                          capture_output=True, text=True, encoding="utf-8")


def test_provento_grava_e_o_validador_fica_verde(tmp_path):
    ws = copia_exemplo(tmp_path)
    r = roda(ws, "provento", "HGLG11", "45,30", "--tipo", "rendimento", "--data", "2026-09-10", "--sim")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "bruto R$ 45,30" in r.stdout and "proventos +1" in r.stdout
    assert proventos(ws).strip().splitlines()[-1] == \
        "2026-09-10,HGLG11,,rendimento,45.3,45.3,corretora-br,BRL"
    log = ws / "logs" / "proventos" / "2026-09-10-HGLG11.md"
    assert log.exists() and "declarado-por-voce" in log.read_text(encoding="utf-8")
    v = valida(ws)
    assert v.returncode == 0 and "0 erro(s)" in v.stdout, v.stdout


def test_provento_com_tipo_fora_do_vocabulario_recusa_sem_gravar(tmp_path):
    ws = copia_exemplo(tmp_path)
    antes = proventos(ws)
    r = roda(ws, "provento", "HGLG11", "45,30", "--tipo", "rendimentos", "--sim")
    assert r.returncode == 1, r.stdout
    assert "rendimento" in r.stdout and "jcp" in r.stdout
    assert "eco:" not in r.stdout      # recusa ANTES do eco: anexar_csv é a segunda rede, não a primeira
    assert proventos(ws) == antes


def test_provento_dry_run_nao_grava(tmp_path):
    ws = copia_exemplo(tmp_path)
    antes = proventos(ws)
    r = roda(ws, "provento", "HGLG11", "45,30", "--tipo", "rendimento", "--dry-run")
    assert r.returncode == 0 and "--dry-run: nada gravado" in r.stdout
    assert proventos(ws) == antes and not (ws / "logs" / "proventos").exists()


def test_estorno_com_casamento_unico_grava_e_o_saldo_volta(tmp_path):
    """Estorno não é inverso aritmético: o replay é refeito sem a linha, e a posição derivada
    volta EXATAMENTE ao que era antes do fill anulado."""
    ws = copia_exemplo(tmp_path)
    assert saldos(ws)[("PETR4", "corretora-br")] == (100, 30.0)
    r = roda(ws, "estorno", "PETR4", "40", "30,75", "--data", "2026-09-05", "--sim")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "anula fills.csv:4" in r.stdout
    assert "saldo depois: 60 @ R$ 29,50" in r.stdout
    assert fills(ws).strip().splitlines()[-1] == \
        "2026-09-05,PETR4,estorno,40,30.75,0,corretora-br,BRL"
    assert saldos(ws)[("PETR4", "corretora-br")] == (60, 29.5)
    log = ws / "logs" / "estornos" / "2026-09-05-PETR4.md"
    assert log.exists() and "declarado-por-voce" in log.read_text(encoding="utf-8")
    v = valida(ws)
    assert v.returncode == 0 and "0 erro(s)" in v.stdout, v.stdout


def test_estorno_que_casa_zero_fills_recusa_e_nomeia_os_candidatos(tmp_path):
    ws = copia_exemplo(tmp_path)
    antes = fills(ws)
    r = roda(ws, "estorno", "PETR4", "40", "30,70", "--data", "2026-09-05", "--sim")
    assert r.returncode == 1, r.stdout
    assert "casa 0 fill" in r.stdout
    assert "fills.csv:3" in r.stdout and "fills.csv:4" in r.stdout      # os fills de PETR4 na conta
    assert "fills.csv:2" not in r.stdout                                 # HGLG11 não é candidato
    assert fills(ws) == antes


def test_estorno_ambiguo_recusa_e_nomeia_os_dois(tmp_path):
    """Duas execuções parciais iguais no mesmo dia são dois eventos reais. O CLI não escolhe."""
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "fills.csv").write_text(
        fills(ws) + "2026-09-05,PETR4,compra,40,30.75,0,corretora-br,BRL\n", encoding="utf-8")
    antes = fills(ws)
    r = roda(ws, "estorno", "PETR4", "40", "30,75", "--data", "2026-09-05", "--sim")
    assert r.returncode == 1, r.stdout
    assert "casa 2 fill" in r.stdout
    assert "fills.csv:4" in r.stdout and "fills.csv:5" in r.stdout
    assert fills(ws) == antes


def test_estorno_dry_run_nao_grava(tmp_path):
    ws = copia_exemplo(tmp_path)
    antes = fills(ws)
    r = roda(ws, "estorno", "PETR4", "40", "30,75", "--data", "2026-09-05", "--dry-run")
    assert r.returncode == 0 and "--dry-run: nada gravado" in r.stdout
    assert "saldo depois: 60 @ R$ 29,50" in r.stdout
    assert fills(ws) == antes and not (ws / "logs" / "estornos").exists()


def test_fill_ja_anulado_nao_e_candidato_de_novo(tmp_path):
    ws = copia_exemplo(tmp_path)
    assert roda(ws, "estorno", "PETR4", "40", "30,75", "--data", "2026-09-05", "--sim").returncode == 0
    antes = fills(ws)
    r = roda(ws, "estorno", "PETR4", "40", "30,75", "--data", "2026-09-05", "--sim")
    assert r.returncode == 1 and "casa 0 fill" in r.stdout, r.stdout
    assert "fills.csv:3" in r.stdout and "fills.csv:4" not in r.stdout
    assert fills(ws) == antes

