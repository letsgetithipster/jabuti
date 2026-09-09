from pathlib import Path

from po.validar import validar

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"


def test_exemplo_valida_verde():
    erros, avisos = validar(EXEMPLO)
    assert erros == []
    assert avisos == []


def test_workspace_inexistente(tmp_path):
    erros, _ = validar(tmp_path / "nao-existe")
    assert erros


def test_mesmo_erro_de_dois_checks_aparece_uma_vez(tmp_path):
    import shutil
    ws = tmp_path / "ws"
    shutil.copytree(EXEMPLO, ws)
    cfg = ws / "vault.config.yaml"
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace("motor: '../..'", f"motor: '{EXEMPLO.parent.parent.as_posix()}'"),
        encoding="utf-8")
    alvo = ws / "politica" / "01-alocacao-alvo.md"
    # bytes latin-1 (\xed, \xe1) que não decodificam como UTF-8 — check_frontmatter e
    # check_politica batem no mesmo arquivo e devem emitir a mesma linha uma única vez.
    alvo.write_bytes(b"---\ntipo: alocacao\n---\n\n## Bandas por bloco\n\n"
                      b"| Bloco | M\xedn % | Alvo % | M\xe1x % |\n|---|---|---|---|\n")
    erros, _ = validar(ws)
    assert sum(1 for e in erros if "01-alocacao-alvo.md" in e and "não é UTF-8" in e) == 1
