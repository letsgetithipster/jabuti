import subprocess
from pathlib import Path

import pytest
import yaml

from criar_workspace import criar


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


def test_com_git_configura_hookspath(tmp_path):
    destino = tmp_path / "com-git"
    criar(destino, com_git=True)
    assert (destino / ".git").exists()
    out = subprocess.run(["git", "config", "core.hooksPath"], cwd=destino,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == ".githooks"


def test_falha_no_git_limpa_destino(tmp_path, monkeypatch):
    def git_quebrado(*args, **kwargs):
        raise FileNotFoundError("git")
    monkeypatch.setattr("criar_workspace.subprocess.run", git_quebrado)
    destino = tmp_path / "ws-git-quebrado"
    with pytest.raises(SystemExit, match="git"):
        criar(destino, com_git=True)
    assert not destino.exists()


def test_motor_relativo(tmp_path):
    destino = tmp_path / "ws-rel"
    criar(destino, com_git=False, data="2026-09-08", motor="../..")
    cfg = yaml.safe_load((destino / "vault.config.yaml").read_text(encoding="utf-8"))
    assert cfg["caminhos"]["motor"] == "../.."


def test_destino_e_arquivo(tmp_path):
    arq = tmp_path / "arquivo.txt"
    arq.write_text("x")
    with pytest.raises(SystemExit, match="não é uma pasta"):
        criar(arq, com_git=False)
