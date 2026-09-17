"""A fila do aporte. O número que move dinheiro tem que ser confrontável por teste — na aba
Aporte do cockpit ele não era: toda célula de fórmula volta None em openpyxl."""
import subprocess
import sys
from pathlib import Path

import pytest

from po.aporte import distribuir
from po.politica import Banda
from test_validar_dados import copia_exemplo

RAIZ = Path(__file__).resolve().parent.parent
CLI = RAIZ / "scripts" / "consultar_aporte.py"
BANDAS = [Banda("acoes-br", 25, 35, 45), Banda("fiis", 20, 30, 40), Banda("rf-br", 25, 35, 45)]
CARTEIRA = {"acoes-br": 4000.0, "fiis": 8000.0, "rf-br": 0.0}


def como_dict(itens):
    return {i.bloco: (i.gap, i.sugerido) for i in itens}


def test_cascata_enche_o_bloco_mais_fora_primeiro():
    itens, sobra = distribuir(CARTEIRA, BANDAS, 1500.0)
    assert como_dict(itens) == {"rf-br": (4725.0, 1500.0), "acoes-br": (725.0, 0.0),
                                "fiis": (0.0, 0.0)}
    assert sobra == 0.0


def test_a_fila_sai_por_gap_decrescente():
    itens, _ = distribuir(CARTEIRA, BANDAS, 10000.0)
    assert [i.bloco for i in itens] == ["rf-br", "acoes-br", "fiis"]
    assert [i.sugerido for i in itens] == [7700.0, 2300.0, 0.0]


def test_aporte_zero_devolve_fila_zerada_e_sobra_zero():
    """O mês em que não se aportou usa o MESMO comando. Ritual separado para o mês vazio é o
    que faz o produto ser abandonado no terceiro mês."""
    itens, sobra = distribuir(CARTEIRA, BANDAS, 0.0)
    assert sobra == 0.0
    assert all(i.sugerido == 0.0 for i in itens)
    assert como_dict(itens)["rf-br"][0] == 4200.0


def test_concentrar_poe_tudo_no_primeiro_e_o_resto_vira_sobra():
    itens, sobra = distribuir(CARTEIRA, BANDAS, 10000.0, modo="concentrar")
    assert [i.sugerido for i in itens] == [7700.0, 0.0, 0.0]
    assert sobra == 2300.0


def test_proporcional_reparte_pelo_peso_do_gap_sem_perder_centavo():
    itens, sobra = distribuir(CARTEIRA, BANDAS, 1000.0, modo="proporcional")
    assert [i.sugerido for i in itens] == [892.16, 107.84, 0.0]
    assert round(sum(i.sugerido for i in itens) + sobra, 2) == 1000.0


def test_modo_desconhecido_levanta():
    with pytest.raises(ValueError, match="modo de distribuição desconhecido"):
        distribuir(CARTEIRA, BANDAS, 100.0, modo="cascada")


def test_aporte_negativo_levanta():
    with pytest.raises(ValueError, match="não pode ser negativo"):
        distribuir(CARTEIRA, BANDAS, -1.0)


def roda(ws, *args):
    return subprocess.run([sys.executable, str(CLI), str(ws), *args],
                          capture_output=True, text=True, encoding="utf-8")


@pytest.mark.slow
def test_cli_imprime_a_fila_e_o_rodape_que_nega_recomendacao(tmp_path):
    ws = copia_exemplo(tmp_path)
    r = roda(ws, "1500", "--data", "2026-09-08")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Total investido: R$ 12.000,00" in r.stdout
    assert "rf-br" in r.stdout and "1.500,00" in r.stdout
    assert "sobra: R$ 0,00" in r.stdout
    assert "não é recomendação de investimento" in r.stdout


@pytest.mark.slow
def test_cli_com_todos_imprime_as_tres_alternativas(tmp_path):
    """As três alternativas da camada 4 calculadas, não narradas: é o que impede a skill de
    dividir o dinheiro de cabeça."""
    ws = copia_exemplo(tmp_path)
    r = roda(ws, "10000", "--todos", "--data", "2026-09-08")
    assert r.returncode == 0, r.stdout
    for modo in ("cascata", "concentrar", "proporcional"):
        assert modo in r.stdout
    assert "2.300,00" in r.stdout      # a sobra que concentrar deixa, e cascata não
