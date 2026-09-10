from pathlib import Path

from po.politica import Banda, ler_bandas

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"


def _ws(tmp_path, tabela: str):
    (tmp_path / "politica").mkdir()
    (tmp_path / "politica" / "01-alocacao-alvo.md").write_text(
        "---\ntipo: alocacao\n---\n\n# Alocação\n\n## Bandas por bloco\n\n"
        "| Bloco | Mín % | Alvo % | Máx % |\n|---|---|---|---|\n" + tabela +
        "\n\n## Caps de concentração\n", encoding="utf-8")
    return tmp_path


def test_le_exemplo():
    bandas, erros = ler_bandas(EXEMPLO)
    assert erros == []
    assert bandas[0] == Banda("acoes-br", 25.0, 35.0, 45.0)
    assert [b.bloco for b in bandas] == ["acoes-br", "fiis", "rf-br"]


def test_tabela_vazia_retorna_lista_vazia_sem_erro(tmp_path):
    bandas, erros = ler_bandas(_ws(tmp_path, ""))
    assert bandas == [] and erros == []


def test_valor_nao_numerico_e_erro(tmp_path):
    _, erros = ler_bandas(_ws(tmp_path, "| acoes-br | 25 | trinta | 45 |"))
    assert any("acoes-br" in e and "não numérico" in e for e in erros)


def test_colunas_erradas_e_erro(tmp_path):
    _, erros = ler_bandas(_ws(tmp_path, "| acoes-br | 25 | 35 |"))
    assert any("colunas" in e for e in erros)


def test_percentual_com_simbolo_aceito(tmp_path):
    bandas, erros = ler_bandas(_ws(tmp_path, "| rf-br | 25% | 35% | 45% |"))
    assert erros == [] and bandas[0].alvo == 35.0


def test_arquivo_ausente(tmp_path):
    _, erros = ler_bandas(tmp_path)
    assert any("ausente" in e for e in erros)


def test_secao_ausente(tmp_path):
    (tmp_path / "politica").mkdir()
    (tmp_path / "politica" / "01-alocacao-alvo.md").write_text("---\ntipo: alocacao\n---\n# x\n", encoding="utf-8")
    _, erros = ler_bandas(tmp_path)
    assert any("Bandas por bloco" in e for e in erros)


def test_linha_com_espaco_a_esquerda_nao_encerra_a_tabela(tmp_path):
    bandas, erros = ler_bandas(_ws(tmp_path, "  | acoes-br | 25 | 35 | 45 |\n | fiis | 20 | 30 | 40 |"))
    assert erros == [] and [b.bloco for b in bandas] == ["acoes-br", "fiis"]


def test_bloco_duplicado_e_erro_na_leitura(tmp_path):
    """A detecção mora aqui, e não só no check_politica: o gerador de ESTADO lê por esta função e
    precisa recusar antes de gravar, senão o bloco repetido sai duas vezes na tabela e a soma dela
    passa do 'Total investido' impresso logo acima."""
    bandas, erros = ler_bandas(_ws(tmp_path, "| acoes-br | 25 | 35 | 45 |\n| acoes-br | 25 | 35 | 45 |"))
    assert any("'acoes-br' duplicado na tabela de bandas" in e for e in erros)
    assert len(erros) == 1      # uma frase por bloco repetido, não uma por repetição
    assert bandas                # a tabela segue legível: quem chama decide o que fazer com ela
