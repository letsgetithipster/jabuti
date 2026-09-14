import datetime

import pytest

from po.carteira import valorar
from po.csvs import anexar_csv
from test_atualizar_cotacoes import CONFIG_DUAS_CONTAS, RAIZ
from test_validar_dados import EXEMPLO, _anexa, copia_exemplo


def test_valora_exemplo():
    c = valorar(EXEMPLO)
    assert c.total_brl == 12000.0
    assert c.por_bloco == {"acoes-br": 4000.0, "fiis": 8000.0, "rf-br": 0.0}
    assert [b.bloco for b in c.bandas] == ["acoes-br", "fiis", "rf-br"]
    petr = next(l for l in c.linhas if l.ticker == "PETR4")
    assert (petr.preco, petr.cambio_cotacao, petr.valor_brl, petr.custo_brl, petr.data_cotacao, petr.fonte) == \
        (40.0, 1.0, 4000.0, 3000.0, "2026-09-08", "manual")
    assert c.data_cotacao_mais_antiga == "2026-09-08"
    assert c.avisos == []


def test_posicao_sem_cotacao_e_erro_acionavel(tmp_path):
    """A posição entra pelo ledger (o fill) e a classe pela declaração (ativos.csv). Antes bastava
    uma linha em posicoes.csv, porque a tabela ERA a posição."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/ativos.csv", "VALE3,acoes-br")
    _anexa(ws, "dados/fills.csv", "2026-08-01,VALE3,saldo-inicial,10,60.00,0,corretora-br,BRL")
    with pytest.raises(ValueError, match="VALE3 sem cotação"):
        valorar(ws)


def test_usd_converte_pelo_cambio_e_exige_usdbrl(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=RAIZ.as_posix()), encoding="utf-8")
    _anexa(ws, "dados/ativos.csv", "AAPL,rv-int")
    _anexa(ws, "dados/fills.csv", "2026-08-01,AAPL,saldo-inicial,2,200.00,0,corretora-us,USD")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,AAPL,230.00,USD,manual")
    with pytest.raises(ValueError, match="USDBRL"):
        valorar(ws)
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,00:00,USDBRL,5.00,BRL,manual")
    c = valorar(ws)
    aapl = next(l for l in c.linhas if l.ticker == "AAPL")
    assert (aapl.cambio_cotacao, aapl.valor_brl, aapl.custo_brl) == (5.0, 2300.0, 2000.0)
    assert c.total_brl == 14300.0 and c.por_bloco["rv-int"] == 2300.0
    assert any("rv-int" in a and "nenhuma banda" in a for a in c.avisos)


def test_dados_sujos_e_erro(tmp_path):
    """O arquivo sujo que derruba a valoração passa a ser o ledger, não mais a tabela de posições:
    é dele que sai o número agora."""
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "fills.csv").write_text("data\n", encoding="utf-8")
    with pytest.raises(ValueError, match="corrija antes"):
        valorar(ws)


def test_cotacao_em_moeda_diferente_da_posicao_levanta(tmp_path):
    """Uma cotação de AAPL digitada em BRL com a posição em USD dava valor 5× errado sem exceção.
    O validador também pega isto, mas o gerador de ESTADO grava antes de alguém rodar o validador,
    então a guarda tem que estar na valoração."""
    ws = copia_exemplo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=RAIZ.as_posix()), encoding="utf-8")
    _anexa(ws, "dados/ativos.csv", "AAPL,rv-int")
    _anexa(ws, "dados/fills.csv", "2026-08-01,AAPL,saldo-inicial,2,200.00,0,corretora-us,USD")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,00:00,USDBRL,5.00,BRL,manual")
    _anexa(ws, "dados/cotacoes.csv", "2026-09-08,18:00,AAPL,1150.00,BRL,manual")
    with pytest.raises(ValueError, match="AAPL: cotação em BRL mas a posição está em USD"):
        valorar(ws)


def test_cotacao_velha_vira_aviso_e_nao_erro(tmp_path):
    """Cotação velha não é erro (o mercado fecha, o ativo pode ser ilíquido), mas virar patrimônio
    de hoje sem uma palavra é. O `hoje` é parâmetro para o limiar não depender do relógio."""
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "cotacoes.csv").write_text(
        "data,hora,ticker,preco,moeda,fonte\n"
        "2026-09-08,18:00,PETR4,40.00,BRL,manual\n"
        "2026-08-20,18:00,HGLG11,160.00,BRL,manual\n", encoding="utf-8")
    c = valorar(ws, hoje=datetime.date(2026, 9, 10))
    assert c.total_brl == 12000.0                       # o número continua saindo
    assert any("HGLG11 (2026-08-20, 21 dias)" in a for a in c.avisos)
    assert valorar(ws, hoje=datetime.date(2026, 8, 25)).avisos == []   # dentro do limiar, calado


def test_valorar_deriva_a_posicao_do_ledger(tmp_path):
    ws = copia_exemplo(tmp_path)
    c = valorar(ws, hoje=datetime.date(2026, 9, 8))
    por_ticker = {l.ticker: l for l in c.linhas}
    assert por_ticker["PETR4"].qty == 100 and round(por_ticker["PETR4"].pm, 2) == 30.00
    assert round(c.total_brl, 2) == 12000.00


def test_valorar_ve_o_fill_que_a_tabela_nao_via(tmp_path):
    """O defeito crítico da fase: um fill anexado pelo mesmo writer da ingestão deixava o
    validador vermelho e o gerador de ESTADO publicando o total antigo com exit 0."""
    ws = copia_exemplo(tmp_path)
    anexar_csv("fills", ws / "dados" / "fills.csv", [
        {"data": "2026-09-10", "ticker": "PETR4", "tipo": "compra", "qty": 50.0, "preco": 36.0,
         "taxa": 0.0, "conta": "corretora-br", "moeda": "BRL"}])
    c = valorar(ws, hoje=datetime.date(2026, 9, 10))
    por_ticker = {l.ticker: l for l in c.linhas}
    assert por_ticker["PETR4"].qty == 150 and round(por_ticker["PETR4"].pm, 2) == 32.00
    assert round(c.total_brl, 2) == 14000.00


def test_valorar_aplica_evento_confirmado(tmp_path):
    ws = copia_exemplo(tmp_path)
    anexar_csv("eventos", ws / "dados" / "eventos.csv", [
        {"data": "2026-09-06", "ticker": "PETR4", "tipo": "split", "razao": "2:1",
         "confirmado": "sim"}])
    c = valorar(ws, hoje=datetime.date(2026, 9, 8))
    por_ticker = {l.ticker: l for l in c.linhas}
    assert por_ticker["PETR4"].qty == 200 and round(por_ticker["PETR4"].pm, 2) == 15.00


def test_valorar_com_ate_devolve_a_posicao_daquela_data(tmp_path):
    """O corte que posicoes.csv estruturalmente não dava: a base do preparar-ir.

    As cotações de agosto entram aqui porque o corte vale para elas também: o exemplo só tem preço
    de setembro, e sem série naquela data a foto histórica não existe (é o teste logo abaixo)."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/cotacoes.csv", "2026-08-31,18:00,PETR4,35.00,BRL,manual")
    _anexa(ws, "dados/cotacoes.csv", "2026-08-31,18:00,HGLG11,150.00,BRL,manual")
    c = valorar(ws, hoje=datetime.date(2026, 9, 8), ate="2026-08-31")
    por_ticker = {l.ticker: l for l in c.linhas}
    assert por_ticker["PETR4"].qty == 60 and round(por_ticker["PETR4"].pm, 2) == 29.50
    assert por_ticker["PETR4"].preco == 35.00        # agosto, não os 40,00 de 08/09


def test_valorar_com_ate_sem_serie_naquela_data_e_erro_acionavel(tmp_path):
    """A outra ponta do corte de cotações, e o limite honesto do `ate`: quem não guardou preço
    daquela data não tem foto histórica, e ouve isso com o comando, em vez de receber o preço de
    hoje com cara de fechamento de dezembro."""
    ws = copia_exemplo(tmp_path)
    with pytest.raises(ValueError, match=r"sem cotação em cotacoes\.csv.*--manual"):
        valorar(ws, hoje=datetime.date(2026, 9, 8), ate="2026-08-31")


def test_valorar_com_ate_usa_a_cotacao_daquela_data(tmp_path):
    """Quantidade de agosto com preço de hoje pareceria foto histórica e não seria."""
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/cotacoes.csv", "2026-08-31,18:00,HGLG11,150.00,BRL,manual")
    c = valorar(ws, hoje=datetime.date(2026, 9, 8), ate="2026-09-01")
    por_ticker = {l.ticker: l for l in c.linhas}
    assert por_ticker["PETR4"].preco == 38.00 and por_ticker["PETR4"].data_cotacao == "2026-09-01"


def test_valorar_omite_posicao_zerada_por_venda(tmp_path):
    ws = copia_exemplo(tmp_path)
    anexar_csv("fills", ws / "dados" / "fills.csv", [
        {"data": "2026-09-07", "ticker": "PETR4", "tipo": "venda", "qty": 100.0, "preco": 41.0,
         "taxa": 0.0, "conta": "corretora-br", "moeda": "BRL"}])
    c = valorar(ws, hoje=datetime.date(2026, 9, 8))
    assert {l.ticker for l in c.linhas} == {"HGLG11"}


def test_valorar_recusa_fill_sem_classe_declarada(tmp_path):
    ws = copia_exemplo(tmp_path)
    anexar_csv("fills", ws / "dados" / "fills.csv", [
        {"data": "2026-09-07", "ticker": "ITSA4", "tipo": "compra", "qty": 10.0, "preco": 10.0,
         "taxa": 0.0, "conta": "corretora-br", "moeda": "BRL"}])
    with pytest.raises(ValueError, match=r"ativos\.csv.*ITSA4"):
        valorar(ws, hoje=datetime.date(2026, 9, 8))
