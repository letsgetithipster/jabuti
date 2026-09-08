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
