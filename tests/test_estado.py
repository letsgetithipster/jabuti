import datetime
import subprocess
import sys
from pathlib import Path

from po.estado import gerar_estado, render_estado
from po.validar import validar
from test_validar_dados import _anexa, copia_exemplo

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"


def test_exemplo_esta_regenerado_pelo_gerador():
    """O ESTADO.md do exemplo é exatamente o que o gerador produz (drift = teste vermelho)."""
    esperado = render_estado(EXEMPLO, hoje=datetime.date(2026, 9, 8))
    assert (EXEMPLO / "estado" / "ESTADO.md").read_text(encoding="utf-8") == esperado


def test_gera_total_tabela_e_pendencias(tmp_path):
    ws = copia_exemplo(tmp_path)
    caminho = gerar_estado(ws, hoje=datetime.date(2026, 9, 8))
    texto = caminho.read_text(encoding="utf-8")
    assert "gerado-por: gerar-estado" in texto and "data-referencia: 2026-09-08" in texto
    assert "Total investido: R$ 12.000,00" in texto
    assert "| acoes-br | R$ 4.000,00 | 33 | 25-45 | dentro |" in texto
    assert "| fiis | R$ 8.000,00 | 67 | 20-40 | acima |" in texto
    assert "| rf-br | R$ 0,00 | 0 | 25-45 | abaixo |" in texto
    assert "- fiis acima da banda máxima (67% vs 40%)" in texto
    assert "- rf-br abaixo do mínimo (0% vs 25%)" in texto
    erros, avisos = validar(ws)
    assert erros == [] and avisos == []


def test_evento_pendente_e_bloco_sem_banda_viram_pendencia(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/eventos.csv", "2026-09-08,PETR4,variacao-anomala,-50%,nao")
    _anexa(ws, "dados/posicoes.csv", "BTC,cripto,corretora-br,0.01,300000.00,BRL")
    _anexa(ws, "dados/fills.csv", "2026-08-01,BTC,saldo-inicial,0.01,300000.00,0,corretora-br,BRL")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,BTC,400000.00,BRL,manual")
    texto = gerar_estado(ws, hoje=datetime.date(2026, 9, 8)).read_text(encoding="utf-8")
    assert "| cripto | R$ 4.000,00 | 25 | — | sem banda |" in texto
    assert "- cripto tem posição mas nenhuma banda declarada" in texto
    assert "- 1 evento(s) em eventos.csv aguardando confirmação (PETR4)" in texto
    erros, _ = validar(ws)
    assert erros == []


def test_sem_cotacao_nao_gera_e_declara(tmp_path):
    ws = copia_exemplo(tmp_path)
    antes = (ws / "estado" / "ESTADO.md").read_text(encoding="utf-8")
    _anexa(ws, "dados/posicoes.csv", "VALE3,acoes-br,corretora-br,10,60.00,BRL")
    try:
        gerar_estado(ws)
        assert False, "deveria ter levantado"
    except ValueError as e:
        assert "VALE3 sem cotação" in str(e)
    assert (ws / "estado" / "ESTADO.md").read_text(encoding="utf-8") == antes


# --- CLI scripts/gerar_estado.py: todo erro é frase acionável, nunca traceback ---

MOTOR = Path(__file__).resolve().parent.parent
GERADOR = MOTOR / "scripts" / "gerar_estado.py"


def _roda(*args, env=None):
    import os
    return subprocess.run([sys.executable, str(GERADOR), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          env={**os.environ, **(env or {})})


def test_cli_regenera_e_imprime_total_e_pendencias(tmp_path):
    ws = copia_exemplo(tmp_path)
    r = _roda(str(ws), "--data", "2026-09-08")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "estado/ESTADO.md regenerado — Total investido: R$ 12.000,00" in r.stdout
    assert "- fiis acima da banda máxima (67% vs 40%)" in r.stdout
    assert "data-referencia: 2026-09-08" in (ws / "estado" / "ESTADO.md").read_text(encoding="utf-8")


def test_cli_caminho_relativo_funciona(tmp_path):
    """O comando documentado passa caminho relativo; o relative_to do print exige raiz resolvida."""
    ws = copia_exemplo(tmp_path)
    r = subprocess.run([sys.executable, str(GERADOR), "ws"], cwd=tmp_path, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0 and "estado/ESTADO.md regenerado" in r.stdout, r.stdout + r.stderr
    assert ws.exists()


def test_cli_data_malformada_e_frase_e_nao_grava(tmp_path):
    ws = copia_exemplo(tmp_path)
    antes = (ws / "estado" / "ESTADO.md").read_text(encoding="utf-8")
    r = _roda(str(ws), "--data", "08/09/2026")
    assert r.returncode == 1 and "Traceback" not in r.stderr
    assert "--data inválida" in r.stdout and "AAAA-MM-DD" in r.stdout
    assert (ws / "estado" / "ESTADO.md").read_text(encoding="utf-8") == antes


def test_cli_workspace_inexistente_e_frase(tmp_path):
    r = _roda(str(tmp_path / "nao-existe"))
    assert r.returncode == 1 and "Traceback" not in r.stderr
    assert "não existe" in r.stdout


def test_cli_csv_ausente_e_frase_nao_errno_cru(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "cotacoes.csv").unlink()
    r = _roda(str(ws))
    assert r.returncode == 1 and "Traceback" not in r.stderr
    assert "dados/cotacoes.csv não encontrado" in r.stdout
    assert "Errno" not in r.stdout


def test_cli_estado_travado_vira_frase_de_arquivo_aberto(tmp_path):
    """Pasta no lugar do ESTADO.md: OSError que não é FileNotFoundError, o caso 'aberto no Excel'."""
    ws = copia_exemplo(tmp_path)
    alvo = ws / "estado" / "ESTADO.md"
    alvo.unlink()
    alvo.mkdir()
    r = _roda(str(ws))
    assert r.returncode == 1 and "Traceback" not in r.stderr
    assert "não consegui ler/gravar estado/ESTADO.md" in r.stdout
    assert "aberto no Excel" in r.stdout


def test_cli_sobrevive_a_console_cp1252(tmp_path):
    """A saída tem — e ·, que não existem em cp1252: sem preparar_console() o CLI morria
    com UnicodeEncodeError em vez de imprimir o total."""
    ws = copia_exemplo(tmp_path)
    r = _roda(str(ws), "--data", "2026-09-08", env={"PYTHONIOENCODING": "cp1252"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Total investido: R$ 12.000,00" in r.stdout
