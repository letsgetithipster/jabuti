import csv
import datetime
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import atualizar_cotacoes as cli_mod
from po.cotacoes.atualizar import Relatorio, atualizar
from po.cotacoes.tipos import Cotacao, SemRede
from po.carteira import valorar
from po.csvs import anexar_csv, ler_csv
from test_validar_dados import _anexa, _troca, copia_exemplo

RAIZ = Path(__file__).resolve().parent.parent
CLI = RAIZ / "scripts" / "atualizar_cotacoes.py"
GERADOR = RAIZ / "scripts" / "gerar_estado.py"

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
    # A ordem dos pedidos é a do ledger (sorted por ticker/conta), não a de um arquivo: prender o
    # conjunto das linhas novas, não a última.
    novas = [l for l in linhas if l["fonte"] == "yahoo"]
    assert {(l["ticker"], l["preco"], l["data"], l["hora"]) for l in novas} == \
        {("PETR4", 41.0, "2026-09-09", "18:00"), ("HGLG11", 161.0, "2026-09-09", "18:00")}
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
    assert "-50,00%" in eventos[0]["razao"]
    # segunda rodada com o mesmo preço: proposta aberta já existe, não duplica
    rel2 = atualizar(ws, provider=ProviderFalso({"PETR4": 20.0, "HGLG11": 160.0}, data="2026-09-10"))
    assert rel2.propostas == []
    eventos, _ = ler_csv("eventos", ws / "dados" / "eventos.csv")
    assert len(eventos) == 1


def test_anomalia_ja_aberta_e_sinalizada_no_relatorio(tmp_path):
    ws = _ws_yahoo(tmp_path)
    atualizar(ws, provider=ProviderFalso({"PETR4": 20.0, "HGLG11": 160.0}))   # -50%, abre a proposta
    rel2 = atualizar(ws, provider=ProviderFalso({"PETR4": 5.0, "HGLG11": 160.0}, data="2026-09-10"))   # -75%
    assert any("PETR4" in a and "já existe proposta aberta em eventos.csv" in a for a in rel2.anomalias)
    assert rel2.propostas == []   # não duplica: a de PETR4 já está aberta


def test_preco_zero_no_arquivo_para_a_rodada_com_frase(tmp_path):
    """Preço zerado é o que a fonte devolve para ativo parado, e a régua única do CSV passou a
    recusá-lo. Antes ele era aceito no arquivo e tratado como "sem base" adiante, e o total do
    bloco ia a zero com o validador verde. Agora a rodada para e diz o que corrigir."""
    ws = _ws_yahoo(tmp_path)
    cot = ws / "dados" / "cotacoes.csv"
    cot.write_text(cot.read_text(encoding="utf-8") + "2026-09-01,18:00,VALE3,0.00,BRL,manual" + chr(10),
                   encoding="utf-8")
    with pytest.raises(ValueError, match="preço deve ser positivo"):
        atualizar(ws, provider=ProviderFalso({"PETR4": 40.0, "HGLG11": 160.0}))


def test_proposta_nao_gravada_vira_aviso_sem_perder_a_cotacao(tmp_path, monkeypatch):
    """Reproduz o Critical: eventos.csv trancado (Excel/OneDrive) não pode apagar a proposta em
    silêncio nem perder a cotação já obtida. -62,5% em PETR4 (40,00 -> 15,00), igual ao repro do
    revisor."""
    import po.cotacoes.atualizar as mod
    original = mod.anexar_csv

    def _falha_so_em_eventos(nome, caminho, linhas):
        if nome == "eventos":
            raise PermissionError("[Errno 13] Permission denied")
        return original(nome, caminho, linhas)

    monkeypatch.setattr(mod, "anexar_csv", _falha_so_em_eventos)
    ws = _ws_yahoo(tmp_path)
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 15.0, "HGLG11": 160.0}))
    assert rel.gravadas == 2   # a cotação (o preço real) foi gravada mesmo assim
    assert rel.propostas_nao_gravadas is not None
    motivo, linhas = rel.propostas_nao_gravadas
    assert "Permission denied" in motivo
    assert linhas and linhas[0]["ticker"] == "PETR4"
    linhas_cot, erros = ler_csv("cotacoes", ws / "dados" / "cotacoes.csv")
    assert erros == [] and any(l["ticker"] == "PETR4" and l["preco"] == 15.0 for l in linhas_cot)
    eventos, _ = ler_csv("eventos", ws / "dados" / "eventos.csv")
    assert eventos == []   # nada meio-escrito em eventos.csv


def test_manual_cobre_classe_sem_mercado_e_provider_faz_o_resto(tmp_path):
    ws = _ws_yahoo(tmp_path)
    _anexa(ws, "dados/ativos.csv", "CDB-X,rf-br")
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8") + "2026-08-01,CDB-X,saldo-inicial,1,1000.00,0,corretora-br,BRL\n", encoding="utf-8")
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 40.0, "HGLG11": 160.0}), manual={"CDB-X": 1050.0})
    assert rel.falhas == [] and rel.gravadas == 3
    assert any(c.ticker == "CDB-X" and c.fonte == "manual" for c in rel.obtidas)


def test_manual_sobrepoe_provider_para_o_mesmo_ticker(tmp_path):
    """restantes filtra por p.ticker not in manual — sem isso o provider cotaria PETR4 de novo
    e uma segunda linha (com o preço do provider) apareceria ao lado da manual."""
    ws = _ws_yahoo(tmp_path)
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 41.0, "HGLG11": 161.0}), manual={"PETR4": 99.0})
    petr4 = [c for c in rel.obtidas if c.ticker == "PETR4"]
    assert len(petr4) == 1
    assert petr4[0].preco == 99.0 and petr4[0].fonte == "manual"


def test_manual_ticker_sem_posicao_vira_falha_mas_nao_trava_o_resto(tmp_path):
    ws = _ws_yahoo(tmp_path)
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 41.0, "HGLG11": 161.0}), manual={"FANTASMA": 10.0})
    assert any("FANTASMA" in f and "sem posição" in f for f in rel.falhas)
    assert "FANTASMA" not in {c.ticker for c in rel.obtidas}
    assert rel.gravadas == 2   # PETR4 e HGLG11 seguem normalmente


def test_saldo_em_conta_vale_um_por_definicao(tmp_path):
    ws = _ws_yahoo(tmp_path)
    _anexa(ws, "dados/ativos.csv", "CAIXA,caixa")
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8") + "2026-08-01,CAIXA,saldo-inicial,5000,1.00,0,corretora-br,BRL\n", encoding="utf-8")
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 40.0, "HGLG11": 160.0}))
    assert rel.falhas == [] and rel.sinteticas == ["CAIXA"]
    assert any(c.ticker == "CAIXA" and c.preco == 1.0 and c.fonte == "definicao" for c in rel.obtidas)
    _anexa(ws, "dados/ativos.csv", "CDB-X,rf-br")          # rf-br continua exigindo --manual: o valor muda
    fills.write_text(fills.read_text(encoding="utf-8") + "2026-08-02,CDB-X,saldo-inicial,1,1000.00,0,corretora-br,BRL\n", encoding="utf-8")
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 40.0, "HGLG11": 160.0}), dry_run=True)
    assert any("CDB-X" in f for f in rel.falhas)


def test_saldo_ja_sintetizado_hoje_nao_duplica(tmp_path):
    ws = _ws_yahoo(tmp_path)
    _anexa(ws, "dados/ativos.csv", "CAIXA,caixa")
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8") + "2026-08-01,CAIXA,saldo-inicial,5000,1.00,0,corretora-br,BRL\n", encoding="utf-8")
    agora = datetime.datetime(2026, 9, 9, 12, 0)
    rel1 = atualizar(ws, provider=ProviderFalso({"PETR4": 40.0, "HGLG11": 160.0}), agora=agora)
    assert rel1.sinteticas == ["CAIXA"] and rel1.ja_atualizadas == []
    rel2 = atualizar(ws, provider=ProviderFalso({"PETR4": 41.0, "HGLG11": 161.0}), agora=agora)
    assert rel2.sinteticas == [] and "CAIXA" not in {c.ticker for c in rel2.obtidas}
    assert rel2.ja_atualizadas == ["CAIXA"]   # não é silêncio: o relatório registra o skip
    linhas, _ = ler_csv("cotacoes", ws / "dados" / "cotacoes.csv")
    assert sum(1 for l in linhas if l["ticker"] == "CAIXA") == 1   # append-only, sem duplicar


def test_carteira_so_caixa_no_segundo_dia_nao_diz_que_nao_tem_posicoes(tmp_path):
    """Achado 3 do revisor: carteira só de caixa, na segunda rodada do dia, tinha obtidas=[] e
    falhas=[] — igual a fills.csv vazio — e o CLI mentia 'não tem posições ainda'."""
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "ativos.csv").write_text("ticker,classe\nCAIXA,caixa\n", encoding="utf-8")
    fills = ws / "dados" / "fills.csv"
    fills.write_text("data,ticker,tipo,qty,preco,taxa,conta,moeda\n"
                     "2026-08-01,CAIXA,saldo-inicial,5000,1.00,0,corretora-br,BRL\n", encoding="utf-8")
    agora = datetime.datetime(2026, 9, 9, 12, 0)
    rel1 = atualizar(ws, agora=agora)
    assert rel1.pedidos == 1 and rel1.sinteticas == ["CAIXA"]
    rel2 = atualizar(ws, agora=agora)
    assert rel2.pedidos == 1 and rel2.obtidas == [] and rel2.falhas == [] and rel2.ja_atualizadas == ["CAIXA"]


@pytest.mark.slow
def test_cli_carteira_so_caixa_segundo_dia_diz_nada_novo_a_buscar(tmp_path):
    ws = copia_exemplo(tmp_path)
    cfg = ws / "vault.config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("provider: manual", "provider: yahoo"),
                   encoding="utf-8")
    (ws / "dados" / "ativos.csv").write_text("ticker,classe\nCAIXA,caixa\n", encoding="utf-8")
    fills = ws / "dados" / "fills.csv"
    fills.write_text("data,ticker,tipo,qty,preco,taxa,conta,moeda\n"
                     "2026-08-01,CAIXA,saldo-inicial,5000,1.00,0,corretora-br,BRL\n", encoding="utf-8")
    r1 = subprocess.run([sys.executable, str(CLI), str(ws)], capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    assert r1.returncode == 0 and "CAIXA: 1,00 já definida hoje" not in r1.stdout
    r2 = subprocess.run([sys.executable, str(CLI), str(ws)], capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert "CAIXA: 1,00 já definida hoje" in r2.stdout
    assert "nada novo a buscar" in r2.stdout
    assert "não tem posições ainda" not in r2.stdout   # a carteira TEM posição, só não tinha o que buscar


def test_saldo_em_conta_moeda_estrangeira(tmp_path):
    ws = _ws_yahoo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=RAIZ.as_posix()), encoding="utf-8")
    _anexa(ws, "dados/ativos.csv", "CAIXA-US,caixa")
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8") + "2026-08-01,CAIXA-US,saldo-inicial,500,1.00,0,corretora-us,USD\n", encoding="utf-8")
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 40.0, "HGLG11": 160.0}),
                    cambio=ProviderFalso({"USDBRL": 5.0}))
    assert rel.falhas == []
    assert any(c.ticker == "CAIXA-US" and c.preco == 1.0 and c.moeda == "USD" and c.fonte == "definicao"
              for c in rel.obtidas)


def test_moeda_ambigua_entre_contas_barra_a_rodada(tmp_path):
    ws = _ws_yahoo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=RAIZ.as_posix()), encoding="utf-8")
    _anexa(ws, "dados/ativos.csv", "PETR4,acoes-br")
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8") + "2026-08-01,PETR4,saldo-inicial,10,8.00,0,corretora-us,USD\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mais de uma moeda"):
        atualizar(ws, provider=ProviderFalso({"PETR4": 41.0, "HGLG11": 160.0}))


def test_provider_manual_na_config_sem_manual_lista_falhas(tmp_path):
    ws = copia_exemplo(tmp_path)   # provider: manual
    rel = atualizar(ws)
    assert rel.obtidas == [] and rel.gravadas == 0
    assert any("PETR4" in f and "--manual PETR4=" in f for f in rel.falhas)


def test_posicao_em_usd_pede_cambio_ao_provider_de_cambio(tmp_path):
    ws = _ws_yahoo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=RAIZ.as_posix()), encoding="utf-8")
    _anexa(ws, "dados/ativos.csv", "AAPL,rv-int")
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
    _anexa(ws, "dados/ativos.csv", "AAPL,rv-int")
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8") + "2026-08-01,AAPL,saldo-inicial,2,200.00,0,corretora-us,USD\n", encoding="utf-8")
    rel = atualizar(ws, provider=ProviderFalso({"PETR4": 40.0, "HGLG11": 160.0, "AAPL": 230.0}))
    assert any("USDBRL" in f and "--manual USDBRL=" in f for f in rel.falhas)
    assert "USDBRL" not in {c.ticker for c in rel.obtidas}


def test_sem_rede_no_cambio_depois_do_mercado_ok_nao_grava_nada(tmp_path):
    ws = _ws_yahoo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=RAIZ.as_posix()), encoding="utf-8")
    _anexa(ws, "dados/ativos.csv", "AAPL,rv-int")
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


@pytest.mark.slow
def test_cli_dry_run_com_manual(tmp_path):
    ws = copia_exemplo(tmp_path)
    r = subprocess.run([sys.executable, str(CLI), str(ws), "--dry-run", "--manual", "PETR4=41,50", "HGLG11=160"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PETR4" in r.stdout and "41,50" in r.stdout and "--dry-run" in r.stdout


@pytest.mark.slow
def test_cli_sem_cotacao_obtida_exit_1(tmp_path):
    ws = copia_exemplo(tmp_path)
    r = subprocess.run([sys.executable, str(CLI), str(ws)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 1 and "FALHA" in r.stdout and "Nada gravado" in r.stdout


@pytest.mark.slow
def test_cli_ledger_vazio_mensagem_clara(tmp_path):
    """Workspace sem nenhum fill: nada a cotar, exit 0, e a frase diz de onde a carteira sai."""
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "fills.csv").write_text("data,ticker,tipo,qty,preco,taxa,conta,moeda\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(CLI), str(ws)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0
    assert "não tem posições ainda" in r.stdout


@pytest.mark.slow
def test_cli_parcial_exit_3(tmp_path):
    ws = copia_exemplo(tmp_path)   # provider: manual — HGLG11 fica sem cotação, PETR4 é gravado
    r = subprocess.run([sys.executable, str(CLI), str(ws), "--manual", "PETR4=41,00"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 3, r.stdout + r.stderr
    assert "Gravado" in r.stdout and "FALHA" in r.stdout


@pytest.mark.slow
def test_cli_manual_valor_ambiguo_rejeitado(tmp_path):
    """Correção fina da sugestão (a leitura decimal sugerida tem que ser lida como decimal por
    quem recusou) é coberta por test_a_sugestao_da_recusa_e_aceita_por_quem_recusou, unitário.
    No nível de CLI, o que importa é: recusa, sai não-zero, não grava nada."""
    ws = copia_exemplo(tmp_path)
    antes = (ws / "dados" / "cotacoes.csv").read_text(encoding="utf-8")
    r = subprocess.run([sys.executable, str(CLI), str(ws), "--manual", "PETR4=1.500"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode != 0
    assert "ambíguo" in r.stderr
    assert (ws / "dados" / "cotacoes.csv").read_text(encoding="utf-8") == antes


@pytest.mark.parametrize("digitado,esperado", [
    ("5,432", 5.432), ("1500", 1500.0), ("1.234,56", 1234.56), ("R$ 41,50", 41.5),
    ("0,00012345", 0.00012345), ("US$1,5", 1.5),
    ("41.50", 41.5), ("0.5", 0.5), ("30.00", 30.0), ("160.75", 160.75),   # ponto decimal: o
    ("1,234.56", 1234.56), ("12.345.678", 12345678.0),                    # formato do próprio
    ("0.001", 0.001), ("0.00012345", 0.00012345), ("1.234.567,89", 1234567.89),  # formato canônico
])
def test_preco_digitado_em_ptbr_e_em_ponto_decimal(digitado, esperado):
    assert cli_mod._preco_digitado(digitado) == pytest.approx(esperado)


@pytest.mark.parametrize("ambiguo", ["5.432", "R$ 5.432", "1.500", "10.000"])
def test_a_sugestao_da_recusa_e_aceita_por_quem_recusou(ambiguo):
    """A recusa só serve se a forma que ela manda digitar for lida do jeito que ela promete."""
    with pytest.raises(SystemExit) as exc:
        cli_mod._preco_digitado(ambiguo)
    msg = str(exc.value)
    # não usar msg.split("ou ")[1]: "ou" aparece duas vezes ("milhar ou decimal" e
    # "para decimal, ou 5432") e pegaria o pedaço errado — ancorar no separador completo.
    resto = msg.split("Escreva ", 1)[1]
    decimal, resto = resto.split(" para decimal, ou ", 1)
    milhar = resto.split(" para milhar")[0]
    assert cli_mod._preco_digitado(decimal) == pytest.approx(float(decimal.replace(",", ".")))
    assert cli_mod._preco_digitado(milhar) == pytest.approx(float(milhar))


def test_manual_com_prefixo_de_moeda_nao_furta_a_checagem_de_ambiguidade(tmp_path):
    """Achado 2 do revisor: 'R$ 5.432' passava batido porque _TRES_CASAS via o argumento cru
    (com o prefixo) enquanto parse_valor lia o corpo já sem prefixo — aqui o prefixo é
    removido ANTES da checagem, então a ambiguidade é vista do mesmo jeito com ou sem R$."""
    with pytest.raises(SystemExit, match="ambíguo"):
        cli_mod._preco_digitado("R$ 5.432")


@pytest.mark.slow
def test_cli_dry_run_relata_quantidade_de_propostas(tmp_path):
    ws = copia_exemplo(tmp_path)
    r = subprocess.run([sys.executable, str(CLI), str(ws), "--dry-run",
                        "--manual", "PETR4=15,00", "HGLG11=160,00"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "1 proposta(s) de anomalia seriam criadas" in r.stdout


@pytest.mark.slow
def test_cli_preco_satoshi_nao_vira_0_00(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/ativos.csv", "SHIB,cripto")
    fills = ws / "dados" / "fills.csv"
    fills.write_text(fills.read_text(encoding="utf-8")
                     + "2026-08-01,SHIB,saldo-inicial,1000000,0.00000100,0,corretora-br,BRL\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(CLI), str(ws), "--dry-run",
                        "--manual", "PETR4=41,00", "HGLG11=160,00", "SHIB=0,00000123"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    linhas_shib = [l for l in r.stdout.splitlines() if "SHIB" in l]
    assert linhas_shib and "0.00000123" in linhas_shib[0]
    assert "0,00 " not in linhas_shib[0]


@pytest.mark.slow
def test_cli_proposta_nao_gravada_imprime_linha_para_colar_e_sai_parcial(tmp_path):
    """Nível CLI do Critical: eventos.csv trancado no disco de verdade (chmod), não monkeypatch."""
    ws = _ws_yahoo(tmp_path)
    eventos = ws / "dados" / "eventos.csv"
    os.chmod(eventos, stat.S_IREAD)
    try:
        r = subprocess.run([sys.executable, str(CLI), str(ws), "--manual", "PETR4=15,00", "HGLG11=160,00"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    finally:
        os.chmod(eventos, stat.S_IWRITE | stat.S_IREAD)
    assert r.returncode == 3, r.stdout + r.stderr
    assert "Cole estas linhas no fim de dados/eventos.csv" in r.stdout
    assert "PETR4" in r.stdout
    linhas, erros = ler_csv("cotacoes", ws / "dados" / "cotacoes.csv")
    assert erros == [] and any(l["ticker"] == "PETR4" and l["preco"] == 15.0 for l in linhas)
    # a razão tem vírgula do formatar_brl ("-62,50%"): a linha impressa precisa estar entre aspas
    # CSV de verdade, senão colar à mão quebra as colunas de eventos.csv em vez de corrigi-lo
    saida = r.stdout.splitlines()
    colada = saida[saida.index("Cole estas linhas no fim de dados/eventos.csv:") + 1].strip()
    campos = next(csv.reader([colada]))
    assert len(campos) == 5 and campos[1] == "PETR4" and campos[2] == "variacao-anomala"
    assert "," in campos[3]   # a vírgula sobreviveu DENTRO do campo razão, não virou coluna extra
    # a linha de resumo não pode contradizer o aviso acima alegando que a proposta foi gravada
    assert "proposta(s) para confirmar" not in r.stdout


@pytest.mark.slow
def test_cli_diretorio_no_lugar_do_csv_vira_mensagem_nao_traceback(tmp_path):
    """Achado do revisor: qualquer SO levanta OSError ao tentar abrir um diretório como
    arquivo — PermissionError no Windows, IsADirectoryError no POSIX — sem depender de chmod,
    que só derruba permissão de escrita, não de leitura."""
    ws = _ws_yahoo(tmp_path)
    cot = ws / "dados" / "cotacoes.csv"
    cot.unlink()
    cot.mkdir()
    r = subprocess.run([sys.executable, str(CLI), str(ws), "--manual", "PETR4=41,00", "HGLG11=160,00"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "Traceback" not in r.stderr and "Traceback" not in r.stdout
    assert "erro:" in r.stdout
    assert "dados/cotacoes.csv" in r.stdout
    assert "Excel" in r.stdout or "OneDrive" in r.stdout


def test_cli_sinaliza_cotacao_que_nao_e_de_hoje(tmp_path, monkeypatch, capsys):
    """--manual sempre data a cotação de hoje, então o único jeito de exercitar o aviso é
    injetar um Relatório com uma Cotacao de outro dia — equivalente a um provider real que
    devolveu o último fechamento em vez do pregão de hoje."""
    fake = Relatorio(dry_run=True, hoje="2026-09-09")
    fake.obtidas = [Cotacao("2026-09-01", "18:00", "PETR4", 41.0, "BRL", "yahoo")]
    fake.variacoes = {"PETR4": None}
    monkeypatch.setattr(cli_mod, "atualizar", lambda *a, **k: fake)
    monkeypatch.setattr(sys, "argv", ["atualizar_cotacoes.py", str(tmp_path), "--dry-run"])
    with pytest.raises(SystemExit):
        cli_mod.main()
    assert "(não é de hoje)" in capsys.readouterr().out


@pytest.mark.slow
def test_cli_sem_rede_exit_2(tmp_path):
    """O único código documentado que ainda não tinha teste de subprocesso. Não dá para
    desligar a rede da máquina de teste, então o subprocesso derruba urllib antes de rodar o
    CLI de verdade (runpy com run_name='__main__'): a falha nasce na única camada de rede do
    motor, o SemRede sobe pelo provider real e o código de saída é o do CLI."""
    ws = _ws_yahoo(tmp_path)
    antes = (ws / "dados" / "cotacoes.csv").read_text(encoding="utf-8")
    wrapper = tmp_path / "sem_rede.py"
    wrapper.write_text(
        "import runpy, sys, urllib.error, urllib.request\n"
        "def _cai(*a, **k):\n"
        "    raise urllib.error.URLError('getaddrinfo failed')\n"
        "urllib.request.urlopen = _cai\n"
        f"sys.argv = ['atualizar_cotacoes.py', {str(ws)!r}]\n"
        f"runpy.run_path({str(CLI)!r}, run_name='__main__')\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(wrapper)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "Sem acesso à rede" in r.stdout and "Nada gravado" in r.stdout
    assert "Traceback" not in r.stderr
    assert (ws / "dados" / "cotacoes.csv").read_text(encoding="utf-8") == antes
# --- Emenda A1: o universo a cotar é a carteira derivada do ledger, não posicoes.csv ---

def test_manual_cota_ticker_que_so_existe_em_fills(tmp_path):
    """O beco do fechamento da Fase 1: gerar_estado mandava rodar `--manual ITSA4=PRECO` e o
    cotador respondia 'ticker sem posição', porque o universo saía de posicoes.csv. Agora o ticker
    que entrou por fill é cotável, e o ciclo fill -> cotar -> valorar fecha."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/ativos.csv", "ITSA4,acoes-br")
    _anexa(ws, "dados/fills.csv", "2026-09-07,ITSA4,compra,10,10.00,0,corretora-br,BRL")
    rel = atualizar(ws, manual={"ITSA4": 10.5, "PETR4": 40.0, "HGLG11": 160.0})
    assert rel.falhas == [] and rel.pedidos == 3 and rel.gravadas == 3
    assert any(c.ticker == "ITSA4" and c.preco == 10.5 and c.fonte == "manual" for c in rel.obtidas)
    c = valorar(ws, hoje=datetime.date(2026, 9, 8))
    assert round(c.total_brl, 2) == 12105.00      # 12.000 + 10 × 10,50


def test_manual_com_ledger_vazio_e_falha_nomeada_nao_descarte_silencioso(tmp_path):
    """Medido em 17382c1: workspace só com fills importados e `--manual AAPL=... USDBRL=...` saía
    com exit 0 e o valor descartado em silêncio (o retorno antecipado vinha antes do bloco manual).
    Ticker sem fill não é cotável, e isso tem que ser dito."""
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "fills.csv").write_text("data,ticker,tipo,qty,preco,taxa,conta,moeda\n", encoding="utf-8")
    rel = atualizar(ws, manual={"AAPL": 230.0})
    assert rel.pedidos == 0 and rel.obtidas == [] and rel.gravadas == 0
    assert any("AAPL" in f and "sem posição" in f and "fills.csv" in f for f in rel.falhas), rel.falhas


def test_fill_sem_classe_declarada_barra_a_rodada_com_frase(tmp_path):
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/fills.csv", "2026-09-07,ITSA4,compra,10,10.00,0,corretora-br,BRL")
    with pytest.raises(ValueError, match=r"ativos\.csv.*ITSA4"):
        atualizar(ws, manual={"ITSA4": 10.5})


def test_ativos_csv_com_erro_barra_a_rodada_com_frase(tmp_path):
    """Sonda da revisão do F1.6 (RA9): apagar a guarda de `erros_ativos` do cotador passava com a
    suíte verde. Classe fora do vocabulário em ativos.csv para a rodada com a frase do validador,
    em vez de cotar com a declaração pela metade."""
    ws = copia_exemplo(tmp_path)
    _troca(ws, "dados/ativos.csv", "HGLG11,fiis", "HGLG11,fii")
    with pytest.raises(ValueError, match=r"declaração de classes tem erro.*ativos\.csv"):
        atualizar(ws, manual={"PETR4": 40.0, "HGLG11": 160.0})


def test_cotador_nao_le_posicoes_csv_e_a_skill_nao_a_cita():
    """Texto no presente só fica se o código o cumpre: a SKILL de cotações dizia que os tickers
    saem de posicoes.csv. Ela morreu (cotar é passo, não fim), e a tradução do cotar mora nas
    duas skills que mandam rodá-lo. Duas pontas presas de uma vez: o orquestrador não lê a
    tabela, e nenhuma das skills que o chamam a cita."""
    import inspect

    import po.cotacoes.atualizar as mod
    assert '_ler_limpo("posicoes"' not in inspect.getsource(mod)
    for nome in ("jabuti-mes", "jabuti-importar"):
        skill = (RAIZ / "skills" / nome / "SKILL.md").read_text(encoding="utf-8")
        assert "posicoes.csv" not in skill, nome


@pytest.mark.slow
def test_cli_ciclo_fill_cotar_gerar_estado_fecha_sem_beco(tmp_path):
    """Ponta a ponta, pelos três CLIs: o erro do gerador aponta para o cotador, o cotador resolve
    com --manual, o gerador publica o total com o ticker novo."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/ativos.csv", "ITSA4,acoes-br")
    anexar_csv("fills", ws / "dados" / "fills.csv", [
        {"data": "2026-09-07", "ticker": "ITSA4", "tipo": "compra", "qty": 10.0, "preco": 10.0,
         "taxa": 0.0, "conta": "corretora-br", "moeda": "BRL"}])
    r = subprocess.run([sys.executable, str(GERADOR), str(ws), "--data", "2026-09-08"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 1 and "ITSA4 sem cotação" in r.stdout and "--manual ITSA4=PRECO" in r.stdout, r.stdout
    r = subprocess.run([sys.executable, str(CLI), str(ws), "--manual", "ITSA4=10,50", "PETR4=40,00", "HGLG11=160,00"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0 and "+3" in r.stdout and "sem posição" not in r.stdout, r.stdout + r.stderr
    r = subprocess.run([sys.executable, str(GERADOR), str(ws), "--data", "2026-09-08"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0 and "R$ 12.105,00" in r.stdout, r.stdout + r.stderr


@pytest.mark.slow
def test_cli_manual_repetido_nao_engole_o_primeiro(tmp_path):
    """Decisão 16 da spec: `--manual PETR4=36 --manual HGLG11=160` devolvia só o segundo, em
    silêncio, e a FALHA resultante mandava a pessoa fazer o gesto que acabou de falhar."""
    ws = copia_exemplo(tmp_path)
    r = subprocess.run([sys.executable, str(CLI), str(ws), "--dry-run",
                        "--manual", "PETR4=41,50", "--manual", "HGLG11=160"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "41,50" in r.stdout and "HGLG11" in r.stdout and "FALHA" not in r.stdout, r.stdout
