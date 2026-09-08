import datetime

from po.frontmatter import extrair_frontmatter


def test_doc_com_frontmatter():
    texto = "---\ntipo: tese\nticker: PETR4\nnota-final: 7.5\n---\n\n# Corpo\n"
    meta, corpo = extrair_frontmatter(texto)
    assert meta == {"tipo": "tese", "ticker": "PETR4", "nota-final": 7.5}
    assert corpo == "# Corpo\n"


def test_doc_sem_frontmatter():
    meta, corpo = extrair_frontmatter("# Só corpo\n")
    assert meta == {}
    assert corpo == "# Só corpo\n"


def test_frontmatter_malformado_vira_vazio():
    texto = "---\n: [broken\n---\ncorpo"
    meta, corpo = extrair_frontmatter(texto)
    assert meta == {}
    assert corpo == texto


def test_frontmatter_sem_fechamento():
    texto = "---\ntipo: tese\ncorpo sem fechamento"
    meta, corpo = extrair_frontmatter(texto)
    assert meta == {}
    assert corpo == texto


def test_frontmatter_com_lista():
    texto = "---\ntipo: setup\nclasses:\n  - acoes-br\n  - fiis\n---\ncorpo"
    meta, _ = extrair_frontmatter(texto)
    assert meta["classes"] == ["acoes-br", "fiis"]


def test_frontmatter_crlf():
    texto = "---\r\ntipo: tese\r\nticker: PETR4\r\n---\r\ncorpo"
    meta, corpo = extrair_frontmatter(texto)
    assert meta["tipo"] == "tese"
    assert meta["ticker"] == "PETR4"
    assert corpo == "corpo"


def test_data_yaml_vira_date():
    texto = "---\ndata-criacao: 2026-09-08\n---\ncorpo"
    meta, _ = extrair_frontmatter(texto)
    assert meta["data-criacao"] == datetime.date(2026, 9, 8)


def test_frontmatter_nao_dict_vira_vazio():
    texto = "---\napenas uma string\n---\ncorpo"
    meta, corpo = extrair_frontmatter(texto)
    assert meta == {}
    assert corpo == texto


def test_fechamento_frouxo_nao_e_delimitador():
    texto = "---\ntipo: tese\n---abc\ncorpo"
    meta, corpo = extrair_frontmatter(texto)
    assert meta == {}
    assert corpo == texto
