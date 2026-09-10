"""Instancia um workspace PatrimonioOS a partir de templates/workspace.

Uso: python scripts/criar_workspace.py C:\\caminho\\meu-vault [--sem-git] [--data AAAA-MM-DD] [--motor CAMINHO]
"""
import argparse
import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):   # console cp1252 do Windows não escreve ≤ nem →
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

MOTOR = Path(__file__).resolve().parent.parent
TEMPLATE = MOTOR / "templates" / "workspace"


def criar(destino: str | Path, com_git: bool = True, data: str | None = None,
          motor: str | None = None) -> Path:
    """Copia o template, resolve placeholders e (opcional) inicializa git com hooks.

    motor: valor gravado em caminhos.motor (default: caminho absoluto deste
    motor; fixtures versionadas passam relativo, ex. '../..').
    Em falha após a cópia, o destino desta execução é limpo — nunca sobra
    workspace pela metade.
    """
    destino = Path(destino).resolve()
    if destino.exists() and not destino.is_dir():
        raise SystemExit(f"erro: destino {destino} existe e não é uma pasta")
    if destino.exists() and any(destino.iterdir()):
        raise SystemExit(
            f"erro: destino {destino} não está vazio — escolha uma pasta nova ou vazia")
    if not TEMPLATE.is_dir():
        raise SystemExit(
            "erro: templates/workspace ausente — instalação do motor incompleta, clone novamente")
    data = data or datetime.date.today().isoformat()
    valor_motor = motor if motor is not None else MOTOR.as_posix()
    shutil.copytree(TEMPLATE, destino, dirs_exist_ok=True)
    try:
        (destino / "gitignore.template").rename(destino / ".gitignore")
        cfg = destino / "vault.config.yaml"
        motor_yaml = "'" + valor_motor.replace("'", "''") + "'"
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
            try:
                subprocess.run(["git", "init"], cwd=destino, check=True, capture_output=True)
                subprocess.run(["git", "config", "core.hooksPath", ".githooks"],
                               cwd=destino, check=True, capture_output=True)
            except FileNotFoundError:
                raise SystemExit(
                    "erro: git não encontrado no PATH — instale o git ou rode com --sem-git "
                    "(o destino foi limpo; rode de novo após corrigir)")
            except subprocess.CalledProcessError as e:
                stderr = (e.stderr or b"").decode(errors="replace").strip()
                raise SystemExit(
                    f"erro: git falhou: {stderr} (o destino foi limpo; rode de novo após corrigir)")
    except BaseException:
        shutil.rmtree(destino, ignore_errors=True)
        raise
    return destino


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("destino", help="pasta nova (ou vazia) onde o workspace nasce")
    ap.add_argument("--sem-git", action="store_true", help="não inicializa repositório git")
    ap.add_argument("--data", help="data AAAA-MM-DD gravada nos documentos (default: hoje)")
    ap.add_argument("--motor",
                    help="valor de caminhos.motor (default: este motor; fixture usa relativo)")
    args = ap.parse_args()
    destino = criar(args.destino, com_git=not args.sem_git, data=args.data, motor=args.motor)
    print(f"Workspace criado em {destino}")
    print("Próximos passos: abra seu agente (Claude Code) na pasta e rode /init (Fase 3).")
    print("Este workspace é PRIVADO por desenho: não publique este repositório.")


if __name__ == "__main__":
    main()
