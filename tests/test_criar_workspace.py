import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from criar_workspace import criar  # noqa: E402


def test_cria_workspace_completo(tmp_path):
    destino = tmp_path / "meu-vault"
    criar(destino, com_git=False, data="2026-09-08")
    assert (destino / "vault.config.yaml").exists()
    assert (destino / "dados" / "posicoes.csv").exists()
    assert (destino / "estado" / "SETUP.md").exists()
    assert (destino / ".githooks" / "pre-commit").exists()
    assert (destino / ".gitattributes").exists()
    assert (destino / ".gitignore").exists()          # renomeado de gitignore.template
    assert not (destino / "gitignore.template").exists()
    cfg_texto = (destino / "vault.config.yaml").read_text(encoding="utf-8")
    assert "__MOTOR__" not in cfg_texto
    cfg = yaml.safe_load(cfg_texto)
    assert Path(cfg["caminhos"]["motor"]).is_dir()    # aponta pro motor real


def test_substitui_data_nos_md(tmp_path):
    destino = tmp_path / "ws"
    criar(destino, com_git=False, data="2026-09-08")
    estado = (destino / "estado" / "ESTADO.md").read_text(encoding="utf-8")
    assert "__DATA__" not in estado
    assert "data-referencia: 2026-09-08" in estado
    sobras = [p for p in destino.rglob("*.md") if "__DATA__" in p.read_text(encoding="utf-8")]
    assert sobras == []


def test_recusa_destino_nao_vazio(tmp_path):
    destino = tmp_path / "ocupado"
    destino.mkdir()
    (destino / "x.txt").write_text("x")
    with pytest.raises(SystemExit):
        criar(destino, com_git=False)


def test_com_git_inicializa_repo(tmp_path):
    destino = tmp_path / "com-git"
    criar(destino, com_git=True)
    assert (destino / ".git").exists()
