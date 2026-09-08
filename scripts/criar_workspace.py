"""Instancia um workspace PatrimonioOS a partir de templates/workspace.

Uso: python scripts/criar_workspace.py C:\\caminho\\meu-vault [--sem-git]
"""
import argparse
import datetime
import os
import shutil
import subprocess
from pathlib import Path

MOTOR = Path(__file__).resolve().parent.parent
TEMPLATE = MOTOR / "templates" / "workspace"


def criar(destino: str | Path, com_git: bool = True, data: str | None = None) -> Path:
    """Copia o template, resolve placeholders e (opcional) inicializa git com hooks."""
    destino = Path(destino).resolve()
    if destino.exists() and any(destino.iterdir()):
        raise SystemExit(f"erro: destino {destino} não está vazio")
    data = data or datetime.date.today().isoformat()
    shutil.copytree(TEMPLATE, destino, dirs_exist_ok=True)
    (destino / "gitignore.template").rename(destino / ".gitignore")

    cfg = destino / "vault.config.yaml"
    motor_yaml = "'" + MOTOR.as_posix().replace("'", "''") + "'"
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace("__MOTOR__", motor_yaml),
        encoding="utf-8",
    )
    for md in destino.rglob("*.md"):
        texto = md.read_text(encoding="utf-8")
        if "__DATA__" in texto:
            md.write_text(texto.replace("__DATA__", data), encoding="utf-8")

    os.chmod(destino / ".githooks" / "pre-commit", 0o755)
    if com_git:
        subprocess.run(["git", "init"], cwd=destino, check=True, capture_output=True)
        subprocess.run(["git", "config", "core.hooksPath", ".githooks"],
                       cwd=destino, check=True, capture_output=True)
    return destino


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("destino")
    ap.add_argument("--sem-git", action="store_true")
    args = ap.parse_args()
    destino = criar(args.destino, com_git=not args.sem_git)
    print(f"Workspace criado em {destino}")
    print("Próximos passos: abra seu agente (Claude Code) na pasta e rode /init (Fase 3).")
    print("Este workspace é PRIVADO por desenho: não publique este repositório.")


if __name__ == "__main__":
    main()
