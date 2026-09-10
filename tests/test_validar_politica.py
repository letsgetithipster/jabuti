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


def test_tolerancia_da_soma_e_deterministica(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    erros, _ = checar_politica(_ws(a, "| acoes-br | 0 | 33,33 | 100 |\n| fiis | 0 | 33,33 | 100 |\n| rf-br | 0 | 33,33 | 100 |"))
    assert erros == []                                   # 99,99 está dentro da tolerância
    erros, _ = checar_politica(_ws(b, "| acoes-br | 0 | 33 | 100 |\n| fiis | 0 | 33 | 100 |\n| rf-br | 0 | 33 | 100 |"))
    assert any("somam 99%" in e for e in erros)


def test_duplicado_nao_esconde_os_demais_erros_da_tabela(tmp_path):
    """O check parou de curto-circuitar na primeira leva de erros do ler_bandas: com o duplicado
    passando a vir de lá, um `if erros: return` faria o erro de vocabulário sumir da mesma tabela."""
    erros, _ = checar_politica(_ws(
        tmp_path, "| acoes | 0 | 50 | 100 |\n| fiis | 0 | 25 | 100 |\n| fiis | 0 | 25 | 100 |\n"
                  "| rf-br | 60 | 25 | 100 |"))
    assert any("'acoes'" in e and "vocabulário" in e for e in erros)
    assert any("'fiis'" in e and "duplicado" in e for e in erros)
    assert any("rf-br" in e and "mín ≤ alvo ≤ máx" in e for e in erros)


def test_tabela_ilegivel_ainda_curto_circuita(tmp_path):
    """Quando não deu para ler banda nenhuma, o resto dos checks não teria o que dizer: a soma de
    uma lista vazia viraria um segundo erro que só confunde."""
    erros, avisos = checar_politica(tmp_path)      # sem politica/01-alocacao-alvo.md
    assert len(erros) == 1 and "ausente" in erros[0] and avisos == []
