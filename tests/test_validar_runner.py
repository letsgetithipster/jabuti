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
