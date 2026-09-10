import subprocess
import sys
from pathlib import Path

import pytest

from po.cotacoes.atualizar import atualizar
from po.cotacoes.tipos import Cotacao, SemRede
from po.csvs import ler_csv
from test_validar_dados import copia_exemplo

RAIZ = Path(__file__).resolve().parent.parent
CLI = RAIZ / "scripts" / "atualizar_cotacoes.py"

CONFIG_DUAS_CONTAS = """versao: 1
idioma: pt-BR
moeda_base: BRL
harness: [claude-code]
cotacoes:
  provider: yahoo
  cambio: bcb-sgs
contas:
  - id: corretora-br
    nome: BR
    moeda: BRL
  - id: corretora-us
    nome: US
    moeda: USD
caminhos:
  motor: '{motor}'
"""


class ProviderFalso:
    nome = "yahoo"

    def __init__(self, precos: dict[str, float], data="2026-09-09", hora="18:00"):
        self.precos, self.data, self.hora = precos, data, hora

    def cotar(self, pedidos):
        cot, falhas = [], []
        for p in pedidos:
            if p.ticker in self.precos:
                cot.append(Cotacao(self.data, self.hora, p.ticker, self.precos[p.ticker], p.moeda, "yahoo"))
            else:
                falhas.append(f"{p.ticker}: sem preço no provider falso")
        return cot, falhas


class ProviderSemRede:
    nome = "yahoo"

    def cotar(self, pedidos):
        raise SemRede("getaddrinfo failed")


def _ws_yahoo(tmp_path):
    ws = copia_exemplo(tmp_path)
    cfg = ws / "vault.config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("provider: manual", "provider: yahoo"), encoding="utf-8")
    return ws


def test_anexa_cotacoes_com_fonte_data_hora(tmp_path):
    ws = _ws_yahoo(tmp_path)
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 41.0, "HGLG11": 161.0}))
    assert rel.gravadas == 2 and rel.falhas == [] and rel.propostas == []
    linhas, erros = ler_csv("cotacoes", ws / "dados" / "cotacoes.csv")
    assert erros == []
    ultima = linhas[-1]
    assert (ultima["ticker"], ultima["preco"], ultima["fonte"], ultima["data"], ultima["hora"]) == ("HGLG11", 161.0, "yahoo", "2026-09-09", "18:00")
    assert rel.variacoes["PETR4"] == pytest.approx(0.025)


def test_dry_run_nao_grava(tmp_path):
    ws = _ws_yahoo(tmp_path)
    antes = (ws / "dados" / "cotacoes.csv").read_text(encoding="utf-8")
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 41.0, "HGLG11": 161.0}), dry_run=True)
    assert rel.gravadas == 0 and len(rel.obtidas) == 2
    assert (ws / "dados" / "cotacoes.csv").read_text(encoding="utf-8") == antes


def test_sem_rede_propaga_e_nada_e_gravado(tmp_path):
    ws = _ws_yahoo(tmp_path)
    antes = (ws / "dados" / "cotacoes.csv").read_text(encoding="utf-8")
    with pytest.raises(SemRede):
        atualizar(ws, provider=ProviderSemRede())
    assert (ws / "dados" / "cotacoes.csv").read_text(encoding="utf-8") == antes


def test_variacao_anomala_grava_cotacao_e_propoe_evento_sem_duplicar(tmp_path):
    ws = _ws_yahoo(tmp_path)
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 20.0, "HGLG11": 160.0}))   # -50%
    assert any("PETR4" in a for a in rel.anomalias)
    assert rel.gravadas == 2
    eventos, _ = ler_csv("eventos", ws / "dados" / "eventos.csv")
    assert len(eventos) == 1
    assert (eventos[0]["ticker"], eventos[0]["tipo"], eventos[0]["confirmado"]) == ("PETR4", "variacao-anomala", "nao")
    assert "-50.0%" in eventos[0]["razao"]
    # segunda rodada com o mesmo preço: proposta aberta já existe, não duplica
    rel2 = atualizar(ws, provider=ProviderFalso({"PETR4": 20.0, "HGLG11": 160.0}, data="2026-09-10"))
    assert rel2.propostas == []
    eventos, _ = ler_csv("eventos", ws / "dados" / "eventos.csv")
    assert len(eventos) == 1


def test_manual_cobre_classe_sem_mercado_e_provider_faz_o_resto(tmp_path):
    ws = _ws_yahoo(tmp_path)
    pos = ws / "dados" / "posicoes.csv"
    pos.write_text(pos.read_text(encoding="utf-8") + "CDB-X,rf-br,corretora-br,1,1000.00,BRL\n", encoding="utf-8")
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8") + "2026-08-01,CDB-X,saldo-inicial,1,1000.00,0,corretora-br,BRL\n", encoding="utf-8")
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 40.0, "HGLG11": 160.0}), manual={"CDB-X": 1050.0})
    assert rel.falhas == [] and rel.gravadas == 3
    assert any(c.ticker == "CDB-X" and c.fonte == "manual" for c in rel.obtidas)


def test_saldo_em_conta_vale_um_por_definicao(tmp_path):
    ws = _ws_yahoo(tmp_path)
    pos = ws / "dados" / "posicoes.csv"
    pos.write_text(pos.read_text(encoding="utf-8") + "CAIXA,caixa,corretora-br,5000,1.00,BRL\n", encoding="utf-8")
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8") + "2026-08-01,CAIXA,saldo-inicial,5000,1.00,0,corretora-br,BRL\n", encoding="utf-8")
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 40.0, "HGLG11": 160.0}))
    assert rel.falhas == [] and rel.sinteticas == ["CAIXA"]
    assert any(c.ticker == "CAIXA" and c.preco == 1.0 and c.fonte == "manual" for c in rel.obtidas)
    rf = ws / "dados" / "posicoes.csv"          # rf-br continua exigindo --manual: o valor muda
    rf.write_text(rf.read_text(encoding="utf-8") + "CDB-X,rf-br,corretora-br,1,1000.00,BRL\n", encoding="utf-8")
    fills.write_text(fills.read_text(encoding="utf-8") + "2026-08-02,CDB-X,saldo-inicial,1,1000.00,0,corretora-br,BRL\n", encoding="utf-8")
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 40.0, "HGLG11": 160.0}), dry_run=True)
    assert any("CDB-X" in f for f in rel.falhas)


def test_provider_manual_na_config_sem_manual_lista_falhas(tmp_path):
    ws = copia_exemplo(tmp_path)   # provider: manual
    rel = atualizar(ws)
    assert rel.obtidas == [] and rel.gravadas == 0
    assert any("PETR4" in f and "--manual PETR4=" in f for f in rel.falhas)


def test_posicao_em_usd_pede_cambio_ao_provider_de_cambio(tmp_path):
    ws = _ws_yahoo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=RAIZ.as_posix()), encoding="utf-8")
    pos = ws / "dados" / "posicoes.csv"
    pos.write_text(pos.read_text(encoding="utf-8") + "AAPL,rv-int,corretora-us,2,200.00,USD\n", encoding="utf-8")
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8") + "2026-08-01,AAPL,saldo-inicial,2,200.00,0,corretora-us,USD\n", encoding="utf-8")
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 40.0, "HGLG11": 160.0, "AAPL": 230.0}),
                    cambio=ProviderFalso({"USDBRL": 5.43}))
    assert rel.falhas == []
    assert {c.ticker for c in rel.obtidas} == {"PETR4", "HGLG11", "AAPL", "USDBRL"}


def test_cambio_manual_na_config_sem_cambio_lista_falha(tmp_path):
    ws = _ws_yahoo(tmp_path)
    (ws / "vault.config.yaml").write_text(
        CONFIG_DUAS_CONTAS.format(motor=RAIZ.as_posix()).replace("cambio: bcb-sgs", "cambio: manual"),
        encoding="utf-8")
    pos = ws / "dados" / "posicoes.csv"
    pos.write_text(pos.read_text(encoding="utf-8") + "AAPL,rv-int,corretora-us,2,200.00,USD\n", encoding="utf-8")
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8") + "2026-08-01,AAPL,saldo-inicial,2,200.00,0,corretora-us,USD\n", encoding="utf-8")
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 40.0, "HGLG11": 160.0, "AAPL": 230.0}))
    assert any("USDBRL" in f and "--manual USDBRL=" in f for f in rel.falhas)
    assert "USDBRL" not in {c.ticker for c in rel.obtidas}


def test_sem_rede_no_cambio_depois_do_mercado_ok_nao_grava_nada(tmp_path):
    ws = _ws_yahoo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=RAIZ.as_posix()), encoding="utf-8")
    pos = ws / "dados" / "posicoes.csv"
    pos.write_text(pos.read_text(encoding="utf-8") + "AAPL,rv-int,corretora-us,2,200.00,USD\n", encoding="utf-8")
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8") + "2026-08-01,AAPL,saldo-inicial,2,200.00,0,corretora-us,USD\n", encoding="utf-8")
    antes = (ws / "dados" / "cotacoes.csv").read_text(encoding="utf-8")
    with pytest.raises(SemRede):
        atualizar(ws, provider=ProviderFalso({"PETR4": 40.0, "HGLG11": 160.0, "AAPL": 230.0}),
                  cambio=ProviderSemRede())
    # o mercado (PETR4, HGLG11, AAPL) já tinha cotação obtida quando o câmbio caiu — nada foi
    # gravado mesmo assim, porque a escrita acontece uma vez só, no final da rodada inteira
    assert (ws / "dados" / "cotacoes.csv").read_text(encoding="utf-8") == antes


def test_dados_sujos_barram_a_rodada(tmp_path):
    ws = _ws_yahoo(tmp_path)
    (ws / "dados" / "cotacoes.csv").write_text("data,ticker\n", encoding="utf-8")
    with pytest.raises(ValueError, match="corrija antes"):
        atualizar(ws, provider=ProviderFalso({"PETR4": 41.0}))


def test_cli_dry_run_com_manual(tmp_path):
    ws = copia_exemplo(tmp_path)
    r = subprocess.run([sys.executable, str(CLI), str(ws), "--dry-run", "--manual", "PETR4=41,50", "HGLG11=160"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PETR4" in r.stdout and "41,50" in r.stdout and "--dry-run" in r.stdout


def test_cli_sem_cotacao_obtida_exit_1(tmp_path):
    ws = copia_exemplo(tmp_path)
    r = subprocess.run([sys.executable, str(CLI), str(ws)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 1 and "FALHA" in r.stdout and "Nada gravado" in r.stdout
