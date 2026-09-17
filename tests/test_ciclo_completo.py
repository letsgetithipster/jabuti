import re
import shutil
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


def _verde(ws, passo):
    """Validador exit 0 neste passo. Aviso não conta; erro conta."""
    r = _roda("validar_workspace.py", str(ws))
    assert r.returncode == 0 and "0 erro(s)" in r.stdout, f"[{passo}] validador:\n{r.stdout}{r.stderr}"


def _estado(ws, data, total, passo):
    """ESTADO regenerado com --data fixo e o total AFIRMADO: é o número que o defeito crítico
    publicou errado com exit 0."""
    r = _roda("gerar_estado.py", str(ws), "--data", data)
    assert r.returncode == 0 and f"R$ {total}" in r.stdout, f"[{passo}] esperava R$ {total}:\n{r.stdout}{r.stderr}"


def test_o_ciclo_completo_percorre_o_mes_inteiro(tmp_path):
    """Spec §8.9: a sonda que teria matado o defeito crítico no dia em que nasceu. O teste
    anterior terminava reimportando o mesmo documento da carga inicial, e por isso um ESTADO
    publicado com o total velho passava verde. Aqui cada operação do mês é seguida do ESTADO
    com o total NOVO afirmado e do validador em 0 erro(s). Tudo por subprocesso, com --data
    fixo em todo comando que aceita (atualizar_cotacoes não aceita: a cotação manual carrega a
    data do relógio, que não entra em nenhum número afirmado)."""
    ws = criar(tmp_path / "ws", com_git=False, data="2026-09-08")
    # bandas: o template nasce sem política declarada, e sem política não há fila de aporte
    shutil.copy(MOTOR / "exemplos" / "workspace-exemplo" / "politica" / "01-alocacao-alvo.md",
                ws / "politica" / "01-alocacao-alvo.md")

    # 1. carga inicial: PETR4 100 @ 30 e HGLG11 50 @ 155 abrem o livro em 01/08
    r = _roda("importar_extrato.py", str(ws), str(FIX / "posicoes-exemplo.csv"), "--data", "2026-08-01")
    assert r.returncode == 0 and "fills +2 (2 aberturas, tipo=saldo-inicial) · ativos +2" in r.stdout, r.stdout + r.stderr
    r = _roda("atualizar_cotacoes.py", str(ws), "--manual", "PETR4=40", "HGLG11=160")
    assert r.returncode == 0, r.stdout + r.stderr
    _estado(ws, "2026-09-08", "12.000,00", "carga inicial")          # 100×40 + 50×160
    _verde(ws, "carga inicial")

    # 2. compra de ticker existente: o total NOVO é o que o defeito crítico não publicava
    r = _roda("registrar.py", str(ws), "compra", "PETR4", "50", "36,00", "--data", "2026-09-09", "--sim")
    assert r.returncode == 0 and "saldo depois: 150 @ R$ 32,00" in r.stdout, r.stdout + r.stderr
    _estado(ws, "2026-09-10", "14.000,00", "compra PETR4")           # 150×40 + 50×160
    _verde(ws, "compra PETR4")

    # 3. a fila do aporte: rf-br está em 0% contra alvo 35%, então recebe os 1.500 inteiros
    r = _roda("consultar_aporte.py", str(ws), "1500", "--data", "2026-09-10")
    assert r.returncode == 0, r.stdout + r.stderr
    assert re.search(r"rf-br\s+atual\s+0,00\s+gap\s+[\d.,]+\s+sugerido\s+1\.500,00", r.stdout), r.stdout
    assert "sobra: R$ 0,00" in r.stdout and "não é recomendação de investimento" in r.stdout
    r = _roda("consultar_aporte.py", str(ws), "0", "--data", "2026-09-10")   # o mês sem aporte
    assert r.returncode == 0 and "sobra: R$ 0,00" in r.stdout, r.stdout + r.stderr
    assert not re.search(r"sugerido\s+[1-9]", r.stdout), r.stdout

    # 4. ticker novo: declara a classe, compra, cota
    r = _roda("registrar.py", str(ws), "ativo", "LFTS11=rf-br")
    assert r.returncode == 0, r.stdout + r.stderr
    r = _roda("registrar.py", str(ws), "compra", "LFTS11", "10", "100,00", "--data", "2026-09-11", "--sim")
    assert r.returncode == 0 and "fills +1" in r.stdout, r.stdout + r.stderr
    r = _roda("validar_workspace.py", str(ws), "--errors-only")
    assert r.returncode == 1 and "LFTS11 sem nenhuma cotação" in r.stdout, r.stdout   # o único erro: cotar
    # --manual com subconjunto é exit 3 (parcial: o resto falha no provider manual); cota tudo
    r = _roda("atualizar_cotacoes.py", str(ws), "--manual", "PETR4=40", "HGLG11=160", "LFTS11=100")
    assert r.returncode == 0, r.stdout + r.stderr
    _estado(ws, "2026-09-11", "15.000,00", "compra LFTS11")          # 14.000 + 10×100
    _verde(ws, "compra LFTS11")

    # 5. split 2:1 confirmado: a qty DERIVADA dobra, o custo não, e o ESTADO vê
    r = _roda("registrar.py", str(ws), "evento", "PETR4", "split", "--razao", "2:1",
              "--data", "2026-09-12", "--confirmar", "--sim")
    assert r.returncode == 0 and "150 @ R$ 32,00 -> 300 @ R$ 16,00" in r.stdout, r.stdout + r.stderr
    _estado(ws, "2026-09-12", "21.000,00", "split (cotação ainda a 40)")   # 300×40 + 8.000 + 1.000
    r = _roda("atualizar_cotacoes.py", str(ws), "--manual", "PETR4=20", "HGLG11=160", "LFTS11=100")
    assert r.returncode == 0, r.stdout + r.stderr
    _estado(ws, "2026-09-12", "15.000,00", "split (cotação a 20)")        # 300×20 + 8.000 + 1.000
    _verde(ws, "split")

    # 6. venda parcial ao PM corrente
    r = _roda("registrar.py", str(ws), "venda", "PETR4", "100", "21,00", "--data", "2026-09-14", "--sim")
    assert r.returncode == 0 and "saldo depois: 200 @ R$ 16,00" in r.stdout, r.stdout + r.stderr
    assert "resultado realizado R$ 500,00" in r.stdout                  # (21 − 16) × 100
    _estado(ws, "2026-09-14", "13.000,00", "venda PETR4")             # 200×20 + 8.000 + 1.000
    _verde(ws, "venda PETR4")

    # 7. a foto da corretora diz PETR4 250 @ 16,80: 50 unidades por R$ 1.000,00 que o livro não
    #    tem (preço implícito 20,00). A conferência explica e entrega os comandos, exit 3.
    foto = ws / "inbox" / "foto.csv"
    foto.write_text("Ativo;Classe;Quantidade;Preço médio;Valor investido\n"
                    "PETR4;acoes-br;250;16,80;4.200,00\n"
                    "HGLG11;fiis;50;155,00;7.750,00\n"
                    "LFTS11;rf-br;10;100,00;1.000,00\n"
                    "Total;;;;12.950,00\n", encoding="utf-8-sig")
    args = (str(ws), str(foto), "--mapeamento", "exemplo-posicoes-csv", "--data", "2026-09-15")
    r = _roda("importar_extrato.py", *args, "--conferir")
    assert r.returncode == 3, r.stdout + r.stderr
    assert "PETR4 (corretora-br): o ledger tem 200 @ R$ 16,00 em 2026-09-15; o documento diz 250 @ R$ 16,80." in r.stdout
    assert "preço implícito R$ 20,00" in r.stdout and " compra PETR4 50 20,00 --data" in r.stdout
    assert " evento PETR4 split" in r.stdout and "--aceitar-como compra" in r.stdout
    assert "HGLG11 (corretora-br): OK" in r.stdout and "LFTS11 (corretora-br): OK" in r.stdout
    r = _roda("importar_extrato.py", *args)                            # sem --conferir: o mesmo
    assert r.returncode == 3 and "preço implícito R$ 20,00" in r.stdout, r.stdout + r.stderr
    _verde(ws, "foto divergente recusada")                             # nada entrou

    # 8. a pessoa confia na foto: o fill implícito fecha o ledger, datado na foto, com o caveat
    r = _roda("importar_extrato.py", *args, "--aceitar-como", "compra")
    assert r.returncode == 0 and "fills +1" in r.stdout, r.stdout + r.stderr
    assert "datado na foto, não na operação" in r.stdout
    assert "2026-09-15,PETR4,compra,50,20,0,corretora-br,BRL" in (ws / "dados" / "fills.csv").read_text(encoding="utf-8")
    r = _roda("importar_extrato.py", *args, "--conferir")
    assert r.returncode == 0 and "PETR4 (corretora-br): OK — 250 @ 16,80" in r.stdout, r.stdout + r.stderr
    _estado(ws, "2026-09-15", "14.000,00", "aceitar-como compra")     # 250×20 + 8.000 + 1.000
    _verde(ws, "aceitar-como compra")
