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


def _com_perfil(tmp_path, tabela: str, vetadas: str):
    """Workspace com a tabela de bandas dada e um perfil preenchido com as classes vetadas dadas."""
    ws = _ws(tmp_path, tabela)
    (ws / "politica" / "00-perfil.md").write_text(
        "---\ntipo: perfil\ndata-criacao: 2026-09-08\ndata-revisao: 2026-09-08\n"
        "idade: 35\ndependentes: 0\nhorizonte-anos: 30\ncusto-vida-mensal: 7000\n"
        "funcao-objetivo-provisoria: false\ncapacidade-aporte-mensal: 2000\nreserva-meses: 6\n"
        "risco-declarado: moderado\nrisco-testado: medio\nrisco-testado-base: [mantem, mantem, mantem]\n"
        "metas:\n  - {tipo: independencia, valor: 2584615, prazo: 2056}\n"
        f"classes-vetadas: {vetadas}\nliquidez-minima-meses: 6\ndegrau-if: 2584615\n---\n\n# Perfil\n",
        encoding="utf-8")
    return ws


def test_classe_vetada_no_perfil_com_alvo_e_erro(tmp_path):
    ws = _com_perfil(tmp_path, "| acoes-br | 25 | 35 | 45 |\n| fiis | 20 | 30 | 40 |\n| cripto | 0 | 35 | 45 |",
                     "[cripto]")
    erros, _ = checar_politica(ws)
    assert any("cripto" in e and "vetada" in e and "35%" in e for e in erros)


def test_classe_vetada_com_alvo_zero_ou_ausente_passa(tmp_path):
    ws = _com_perfil(tmp_path, "| acoes-br | 25 | 50 | 55 |\n| fiis | 20 | 50 | 60 |\n| cripto | 0 | 0 | 0 |",
                     "[cripto, commodities]")
    assert checar_politica(ws) == ([], [])


def test_sem_perfil_preenchido_o_cruzamento_nao_roda(tmp_path):
    ws = _ws(tmp_path, "| acoes-br | 25 | 50 | 55 |\n| cripto | 0 | 50 | 60 |")   # sem 00-perfil.md
    assert checar_politica(ws) == ([], [])


def test_classes_vetadas_malformada_nao_derruba_o_cruzamento(tmp_path):
    """YAML resolve `5` para int, `on` para bool e `[[cripto]]` para lista aninhada. As duas
    guardas do cruzamento existem para isso: sem `isinstance(..., list)` um int vira
    `TypeError: 'int' object is not iterable`, e sem `em_vocabulario` uma lista aninhada vira
    `TypeError: unhashable type: 'list'` no `alvos.get`. Erro é frase acionável, nunca traceback;
    o tipo errado é assunto do check_perfil, e aqui o cruzamento só não pode explodir nem
    inventar veto a partir de lixo."""
    tabela = "| acoes-br | 25 | 50 | 55 |\n| cripto | 0 | 50 | 60 |"
    for i, vetadas in enumerate(("[[cripto]]", "5", "cripto", "{cripto: 1}", "on", "null")):
        raiz = tmp_path / f"caso{i}"
        raiz.mkdir()          # _ws faz mkdir() sem parents
        ws = _com_perfil(raiz, tabela, vetadas)
        erros, _ = checar_politica(ws)
        assert not any("vetada" in e for e in erros), f"{vetadas!r} inventou veto: {erros}"
