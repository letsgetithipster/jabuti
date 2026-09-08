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
    assert any("conta-fantasma" in e and "não declarada" in e for e in erros)


def test_posicao_sem_fills_e_permitida(tmp_path):
    ws = copia_exemplo(tmp_path)
    pos = ws / "dados" / "posicoes.csv"
    pos.write_text(pos.read_text(encoding="utf-8") +
                   "ITSA4,acoes-br,corretora-br,200,9.50,BRL\n", encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert erros == []


def test_venda_no_saldo(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "fills.csv").write_text(
        "data,ticker,tipo,qty,preco,taxa,conta,moeda\n"
        "2026-08-05,PETR4,compra,90,29.50,0,corretora-br,BRL\n"
        "2026-08-20,PETR4,compra,30,30.00,0,corretora-br,BRL\n"
        "2026-09-05,PETR4,venda,20,31.00,0,corretora-br,BRL\n",
        encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert erros == []  # 90 + 30 - 20 = 100 = posição


def test_venda_incoerente(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "fills.csv").write_text(
        "data,ticker,tipo,qty,preco,taxa,conta,moeda\n"
        "2026-08-05,PETR4,compra,120,29.50,0,corretora-br,BRL\n"
        "2026-09-05,PETR4,venda,10,31.00,0,corretora-br,BRL\n",
        encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("difere do saldo" in e for e in erros)


def test_posicao_duplicada_mesma_conta(tmp_path):
    ws = copia_exemplo(tmp_path)
    pos = ws / "dados" / "posicoes.csv"
    pos.write_text(pos.read_text(encoding="utf-8") +
                   "PETR4,acoes-br,corretora-br,100,30.00,BRL\n", encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("duplicada" in e for e in erros)


def test_multi_conta_importada_e_permitida(tmp_path):
    ws = copia_exemplo(tmp_path)
    cfg = ws / "vault.config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(
        "contas:", 'contas:\n  - id: corretora-us\n    nome: "US"\n    moeda: USD'),
        encoding="utf-8")
    pos = ws / "dados" / "posicoes.csv"
    pos.write_text(pos.read_text(encoding="utf-8") +
                   "PETR4,acoes-br,corretora-us,50,28.00,BRL\n", encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert erros == []  # posição importada em outra conta, sem fills: permitida


def test_leitura_suja_pula_cross_check(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "fills.csv").write_text(
        "data,ticker,tipo,qty,preco,taxa,conta,moeda\n"
        "2026-08-05,PETR4,compra,cem,29.50,0,corretora-br,BRL\n",
        encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("formato canônico" in e for e in erros)
    assert not any("difere do saldo" in e for e in erros)


def test_csv_ausente(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "indices.csv").unlink()
    erros, _ = checar_dados(ws)
    assert any("indices.csv ausente" in e for e in erros)


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
