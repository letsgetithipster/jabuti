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
    # v2 exige cotação para toda posição (deferral pago nesta task); sem isso o cross-check
    # de fills (o que este teste exercita) fica mascarado por um erro de cotação ausente.
    cot = ws / "dados" / "cotacoes.csv"
    cot.write_text(cot.read_text(encoding="utf-8") +
                   "2026-09-08,18:00,ITSA4,9.60,BRL,manual\n", encoding="utf-8")
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
    # v2 também confere o PM recalculado pelo ledger contra posicoes.csv (deferral pago
    # nesta task); este fills.csv substitui o do exemplo, então o PM correto para 90@29.50
    # + 30@30.00 é 29.625 (a venda de 20 não altera o PM corrente).
    _troca(ws, "dados/posicoes.csv", "PETR4,acoes-br,corretora-br,100,30.00",
          "PETR4,acoes-br,corretora-br,100,29.625")
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
    # moeda da linha precisa bater com a moeda da conta (deferral pago nesta task);
    # corretora-us é USD, então a linha declara USD, não BRL.
    pos.write_text(pos.read_text(encoding="utf-8") +
                   "PETR4,acoes-br,corretora-us,50,28.00,USD\n", encoding="utf-8")
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


def _troca(ws, rel, antigo, novo):
    p = ws / rel
    p.write_text(p.read_text(encoding="utf-8").replace(antigo, novo), encoding="utf-8")


def _anexa(ws, rel, linha):
    p = ws / rel
    p.write_text(p.read_text(encoding="utf-8") + linha + "\n", encoding="utf-8")


def test_pm_divergente_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    _troca(ws, "dados/posicoes.csv", "PETR4,acoes-br,corretora-br,100,30.00", "PETR4,acoes-br,corretora-br,100,31.00")
    erros, _ = checar_dados(ws)
    assert any("PETR4" in e and "pm 31.00" in e and "recalculado 30.00" in e for e in erros)


def test_posicao_sem_fills_avisa_pm_nao_verificavel(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/posicoes.csv", "VALE3,acoes-br,corretora-br,10,60.00,BRL")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,VALE3,61.00,BRL,manual")
    erros, avisos = checar_dados(ws)
    assert erros == []
    assert any("VALE3" in a and "PM não verificável" in a for a in avisos)


def test_venda_que_zera_posicao_nao_exige_linha_em_posicoes(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/fills.csv", "2026-07-01,VALE3,compra,10,60.00,0,corretora-br,BRL")
    _anexa(ws, "dados/fills.csv", "2026-07-15,VALE3,venda,10,65.00,0,corretora-br,BRL")
    erros, _ = checar_dados(ws)
    assert not any("VALE3" in e for e in erros)


def test_venda_acima_do_saldo_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/fills.csv", "2026-09-06,PETR4,venda,500,40.00,0,corretora-br,BRL")
    erros, _ = checar_dados(ws)
    assert any("excede o saldo" in e for e in erros)


def test_moeda_da_linha_diferente_da_conta_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    _troca(ws, "dados/posicoes.csv", "HGLG11,fiis,corretora-br,50,155.00,BRL", "HGLG11,fiis,corretora-br,50,155.00,USD")
    erros, _ = checar_dados(ws)
    assert any("HGLG11" in e and "USD" in e and "conta corretora-br é BRL" in e for e in erros)


def test_posicao_sem_cotacao_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    cot = ws / "dados" / "cotacoes.csv"
    cot.write_text("\n".join(l for l in cot.read_text(encoding="utf-8").splitlines() if "HGLG11" not in l) + "\n",
                   encoding="utf-8")
    erros, _ = checar_dados(ws)
    assert any("HGLG11" in e and "sem nenhuma cotação" in e for e in erros)


def test_cotacao_fora_de_ordem_e_aviso(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/cotacoes.csv", "2026-08-15,18:00,PETR4,37.00,BRL,manual")
    erros, avisos = checar_dados(ws)
    assert erros == []
    assert any("PETR4" in a and "fora de ordem" in a for a in avisos)


def test_provento_sem_posicao_e_aviso(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/proventos.csv", "2026-09-05,VALE3,,dividendo,10.00,10.00,corretora-br,BRL")
    erros, avisos = checar_dados(ws)
    assert erros == []
    assert any("VALE3" in a and "sem posição" in a for a in avisos)


def test_evento_anomalo_confirmado_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/eventos.csv", "2026-09-08,PETR4,variacao-anomala,-52.3% vs 2026-09-01,sim")
    erros, _ = checar_dados(ws)
    assert any("variacao-anomala" in e and "troque o tipo" in e for e in erros)


def test_split_confirmado_sem_razao_e_aviso(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/eventos.csv", "2026-09-08,PETR4,split,,sim")
    erros, avisos = checar_dados(ws)
    assert erros == [] and any("split" in a and "sem razão" in a for a in avisos)
