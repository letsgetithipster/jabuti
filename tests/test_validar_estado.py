import shutil
from pathlib import Path

from po.validar.check_estado import checar_estado
from test_atualizar_cotacoes import CONFIG_DUAS_CONTAS
from test_validar_dados import MOTOR, _anexa, copia_exemplo

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"


def test_exemplo_total_bate():
    erros, _ = checar_estado(EXEMPLO)
    assert erros == []


def test_total_divergente_e_erro(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    estado = ws / "estado" / "ESTADO.md"
    texto = estado.read_text(encoding="utf-8")
    estado.write_text(texto.replace("R$ 12.000,00", "R$ 99.000,00"), encoding="utf-8")
    erros, _ = checar_estado(ws)
    assert any("Total investido" in e for e in erros)


def test_ticker_sem_cotacao_vira_aviso(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    cot = ws / "dados" / "cotacoes.csv"
    linhas = [l for l in cot.read_text(encoding="utf-8").splitlines() if "HGLG11" not in l]
    cot.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    erros, avisos = checar_estado(ws)
    assert erros == []      # sem cotação para todos, o check do total é suspenso...
    assert any("HGLG11" in a for a in avisos)   # ...mas avisa


def test_ultima_cotacao_por_data_nao_por_linha(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    cot = ws / "dados" / "cotacoes.csv"
    cot.write_text(cot.read_text(encoding="utf-8") +
                   "2026-09-01,18:00,PETR4,10.00,BRL,manual\n", encoding="utf-8")
    erros, _ = checar_estado(ws)
    assert erros == []  # linha velha appendada depois não vence a data mais nova


def test_moeda_sem_cambio_declarado_suspende(tmp_path):
    """Antes este teste se chamava test_moeda_nao_brl_suspende, e o nome era verdade:
    qualquer posição não-BRL desligava o check. Não é mais — o que suspende é a FALTA do par
    de câmbio, e o aviso tem que nomear o par que falta para a suspensão ser acionável."""
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    pos = ws / "dados" / "posicoes.csv"
    pos.write_text(pos.read_text(encoding="utf-8") +
                   "VOO,rv-int,corretora-br,2,500.00,USD\n", encoding="utf-8")
    cot = ws / "dados" / "cotacoes.csv"
    cot.write_text(cot.read_text(encoding="utf-8") +
                   "2026-09-08,18:00,VOO,510.00,USD,manual\n", encoding="utf-8")
    erros, avisos = checar_estado(ws)
    assert erros == []
    assert any("suspenso" in a and "sem câmbio USDBRL" in a for a in avisos)


def test_mensagem_de_divergencia_em_ptbr(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    estado = ws / "estado" / "ESTADO.md"
    estado.write_text(estado.read_text(encoding="utf-8").replace("R$ 12.000,00", "R$ 9.000,00"),
                      encoding="utf-8")
    erros, _ = checar_estado(ws)
    assert any("R$ 9.000,00" in e and "12.000,00" in e for e in erros)


def test_dados_com_erro_suspende_com_aviso(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    (ws / "dados" / "posicoes.csv").write_text(
        "ticker,classe,conta,qty,pm,moeda\nPETR4,acoes-br,corretora-br,cem,30.00,BRL\n",
        encoding="utf-8")
    erros, avisos = checar_estado(ws)
    assert erros == []
    assert any("suspenso" in a for a in avisos)


def test_estado_nao_utf8_vira_erro(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    (ws / "estado" / "ESTADO.md").write_bytes(
        "---\ntipo: estado\n---\nTotal investido: R$ 1,00 ação\n".encode("latin-1"))
    erros, _ = checar_estado(ws)
    assert any("UTF-8" in e for e in erros)


# --- C2: o check consome po/carteira.py, o cálculo único, em vez de recalcular por conta ---

def test_total_adulterado_com_carteira_multi_moeda_e_erro(tmp_path):
    """O check antigo não conhecia câmbio: bastava UMA posição não-BRL para o único guarda-corpo
    do arquivo gerado desligar inteiro, com aviso e zero erros. Medido: total trocado à mão para
    R$ 999.999,00 contra R$ 14.300,00 reais, e o validador passava."""
    ws = copia_exemplo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=MOTOR.as_posix()), encoding="utf-8")
    _anexa(ws, "dados/posicoes.csv", "AAPL,rv-int,corretora-us,2,200.00,USD")
    _anexa(ws, "dados/fills.csv", "2026-08-01,AAPL,saldo-inicial,2,200.00,0,corretora-us,USD")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,AAPL,230.00,USD,manual")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,00:00,USDBRL,5.00,BRL,manual")
    estado = ws / "estado" / "ESTADO.md"
    estado.write_text(estado.read_text(encoding="utf-8").replace("R$ 12.000,00", "R$ 999.999,00"),
                      encoding="utf-8")
    erros, avisos = checar_estado(ws)
    assert any("999.999,00" in e and "14.300,00" in e for e in erros), (erros, avisos)
    assert not any("suspenso" in a for a in avisos)


def test_multi_moeda_com_total_correto_nao_acusa(tmp_path):
    """A outra ponta: o check passou a valer para carteira em dólar, então ele tem que ficar
    calado quando o número está certo, e não trocar um falso-negativo por um falso-positivo."""
    ws = copia_exemplo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=MOTOR.as_posix()), encoding="utf-8")
    _anexa(ws, "dados/posicoes.csv", "AAPL,rv-int,corretora-us,2,200.00,USD")
    _anexa(ws, "dados/fills.csv", "2026-08-01,AAPL,saldo-inicial,2,200.00,0,corretora-us,USD")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,AAPL,230.00,USD,manual")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,00:00,USDBRL,5.00,BRL,manual")
    estado = ws / "estado" / "ESTADO.md"
    estado.write_text(estado.read_text(encoding="utf-8").replace("R$ 12.000,00", "R$ 14.300,00"),
                      encoding="utf-8")
    assert checar_estado(ws) == ([], [])


def test_posicao_sem_cotacao_continua_suspendendo_com_aviso_e_nao_erro(tmp_path):
    """A suspensão legítima não virou erro no caminho: quando a valoração recusa número parcial,
    o check do total suspende e nomeia a causa. Quem acusa a origem é o check de dados."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/posicoes.csv", "VALE3,acoes-br,corretora-br,10,60.00,BRL")
    erros, avisos = checar_estado(ws)
    assert erros == []
    assert any("suspenso" in a and "VALE3 sem cotação" in a for a in avisos)
