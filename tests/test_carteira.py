import pytest

from po.carteira import valorar
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
    ws = copia_exemplo(tmp_path)
    _anexa(ws, "dados/posicoes.csv", "VALE3,acoes-br,corretora-br,10,60.00,BRL")
    with pytest.raises(ValueError, match="VALE3 sem cotação"):
        valorar(ws)


def test_usd_converte_pelo_cambio_e_exige_usdbrl(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / "vault.config.yaml").write_text(CONFIG_DUAS_CONTAS.format(motor=RAIZ.as_posix()), encoding="utf-8")
    _anexa(ws, "dados/posicoes.csv", "AAPL,rv-int,corretora-us,2,200.00,USD")
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
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "posicoes.csv").write_text("ticker\n", encoding="utf-8")
    with pytest.raises(ValueError, match="corrija antes"):
        valorar(ws)
