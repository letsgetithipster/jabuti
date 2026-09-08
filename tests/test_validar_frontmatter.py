from pathlib import Path

from po.validar.check_frontmatter import checar_frontmatter

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"


def test_workspace_exemplo_sem_erros():
    erros, _ = checar_frontmatter(EXEMPLO)
    assert erros == []


def test_tipo_fora_do_vocabulario(tmp_path):
    doc = tmp_path / "politica"
    doc.mkdir()
    (doc / "x.md").write_text("---\ntipo: invencao\ndata-criacao: 2026-09-08\n---\ncorpo",
                              encoding="utf-8")
    erros, _ = checar_frontmatter(tmp_path)
    assert any("tipo" in e for e in erros)


def test_sem_frontmatter_e_erro(tmp_path):
    doc = tmp_path / "teses"
    doc.mkdir()
    (doc / "X.md").write_text("# sem frontmatter", encoding="utf-8")
    erros, _ = checar_frontmatter(tmp_path)
    assert any("frontmatter" in e for e in erros)


def test_alias_proibido(tmp_path):
    doc = tmp_path / "politica"
    doc.mkdir()
    (doc / "x.md").write_text(
        "---\ntipo: perfil\ncriado: 2026-09-08\ndata-criacao: 2026-09-08\n---\ncorpo",
        encoding="utf-8")
    erros, _ = checar_frontmatter(tmp_path)
    assert any("alias" in e for e in erros)


def test_semente_validada_true_e_erro(tmp_path):
    doc = tmp_path / "teses"
    doc.mkdir()
    (doc / "X.md").write_text(
        "---\ntipo: tese-semente\nticker: X\nclasse: acoes-br\nvalidada: true\n"
        "data-criacao: 2026-09-08\norigem: refinar-micro\n---\ncorpo",
        encoding="utf-8")
    erros, _ = checar_frontmatter(tmp_path)
    assert any("validada" in e for e in erros)


def test_readme_e_ignorado(tmp_path):
    doc = tmp_path / "logs"
    doc.mkdir()
    (doc / "README.md").write_text("# sem frontmatter, e tudo bem", encoding="utf-8")
    erros, _ = checar_frontmatter(tmp_path)
    assert erros == []
