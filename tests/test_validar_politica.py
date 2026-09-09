from pathlib import Path

from po.validar.check_politica import checar_politica
from test_politica import _ws

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"


def test_exemplo_sem_erros():
    assert checar_politica(EXEMPLO) == ([], [])


def test_tabela_vazia_e_aviso(tmp_path):
    erros, avisos = checar_politica(_ws(tmp_path, ""))
    assert erros == [] and any("nenhuma banda" in a for a in avisos)


def test_soma_diferente_de_100_e_erro(tmp_path):
    erros, _ = checar_politica(_ws(tmp_path, "| acoes-br | 25 | 35 | 45 |\n| fiis | 20 | 30 | 40 |"))
    assert any("somam 65%" in e for e in erros)


def test_min_alvo_max_fora_de_ordem(tmp_path):
    erros, _ = checar_politica(_ws(tmp_path, "| acoes-br | 40 | 35 | 45 |\n| fiis | 20 | 65 | 40 |"))
    assert any("acoes-br" in e and "mín ≤ alvo ≤ máx" in e for e in erros)
    assert any("fiis" in e and "mín ≤ alvo ≤ máx" in e for e in erros)


def test_bloco_fora_do_vocabulario_e_duplicado(tmp_path):
    erros, _ = checar_politica(_ws(tmp_path, "| acoes | 0 | 50 | 100 |\n| fiis | 0 | 25 | 100 |\n| fiis | 0 | 25 | 100 |"))
    assert any("'acoes'" in e and "vocabulário" in e for e in erros)
    assert any("'fiis'" in e and "duplicado" in e for e in erros)
