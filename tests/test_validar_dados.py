import re
import shutil
from pathlib import Path

from po.validar.check_dados import checar_dados

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"
MOTOR = EXEMPLO.parent.parent


def copia_exemplo(tmp_path):
    """Copia o exemplo e absolutiza o motor (o '../..' relativo só vale in-place)."""
    destino = tmp_path / "ws"
    shutil.copytree(EXEMPLO, destino)
    cfg = destino / "vault.config.yaml"
    texto = re.sub(r"motor: '[^']*'", f"motor: '{MOTOR.as_posix()}'",
                   cfg.read_text(encoding="utf-8"))
    cfg.write_text(texto, encoding="utf-8")
    return destino


def test_workspace_exemplo_sem_erros():
    erros, _ = checar_dados(EXEMPLO)
    assert erros == []


def test_fills_incoerentes_com_posicao(tmp_path):
    ws = copia_exemplo(tmp_path)
    fills = ws / "dados" / "fills.csv"
    fills.write_text(
        "data,ticker,tipo,qty,preco,taxa,conta,moeda\n"
        "2026-08-05,PETR4,compra,60,29.50,0,corretora-br,BRL\n",  # só 60, posição diz 100
        encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("PETR4" in e and "fills" in e for e in erros)


def test_fill_sem_posicao_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    fills = ws / "dados" / "fills.csv"
    conteudo = fills.read_text(encoding="utf-8")
    fills.write_text(conteudo + "2026-09-06,VALE3,compra,10,60.00,0,corretora-br,BRL\n",
                     encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("VALE3" in e for e in erros)


def test_conta_desconhecida_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    pos = ws / "dados" / "posicoes.csv"
    conteudo = pos.read_text(encoding="utf-8")
    pos.write_text(conteudo.replace("corretora-br", "conta-fantasma"), encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("conta" in e for e in erros)


def test_posicao_sem_fills_e_permitida():
    # HGLG11 no exemplo não tem fills (posição importada) e o exemplo valida limpo
    erros, _ = checar_dados(EXEMPLO)
    assert erros == []


def test_motor_nao_substituido(tmp_path):
    ws = copia_exemplo(tmp_path)
    cfg = ws / "vault.config.yaml"
    texto = re.sub(r"motor: '[^']*'", "motor: __MOTOR__", cfg.read_text(encoding="utf-8"))
    cfg.write_text(texto, encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("não foi substituído" in e for e in erros)


def test_motor_invalido(tmp_path):
    ws = copia_exemplo(tmp_path)
    cfg = ws / "vault.config.yaml"
    texto = re.sub(r"motor: '[^']*'", "motor: 'C:/nao/existe'", cfg.read_text(encoding="utf-8"))
    cfg.write_text(texto, encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("motor" in e for e in erros)
