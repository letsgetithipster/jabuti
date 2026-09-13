"""Instancia um workspace jabuti a partir de templates/workspace.

Uso: python scripts/criar_workspace.py C:\\caminho\\meu-vault [--sem-git] [--data AAAA-MM-DD]
        [--motor CAMINHO] [--harness claude-code] [--casa NOME] [--usuario NOME] [--so-skills]
"""
import argparse
import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from po.cli import preparar_console  # noqa: E402

preparar_console()

from po.config import HARNESSES, NOMES_PADRAO  # noqa: E402
from po.harness import escrever_harness, instalar_skills  # noqa: E402,F401  (reexportado: os testes importam daqui)

MOTOR = Path(__file__).resolve().parent.parent
TEMPLATE = MOTOR / "templates" / "workspace"
SKILLS = MOTOR / "skills"


def _yaml_str(valor: str) -> str:
    """String YAML entre aspas simples, com a aspa interna dobrada."""
    return "'" + valor.replace("'", "''") + "'"


def criar(destino: str | Path, com_git: bool = True, data: str | None = None,
          motor: str | None = None, harness: str = "claude-code",
          casa: str | None = None, usuario: str | None = None) -> Path:
    """Copia o template, resolve placeholders, compila o harness e (opcional) inicializa git com hooks.

    motor: valor gravado em caminhos.motor (default: caminho absoluto deste motor; fixtures
    versionadas passam relativo, ex. '../..'). harness: alvo gravado em `harness:` (um dos
    HARNESSES; só claude-code é compilado hoje). Em falha após a cópia, o destino desta execução
    é limpo — nunca sobra workspace pela metade.
    """
    destino = Path(destino).resolve()
    if harness not in HARNESSES:
        raise SystemExit(f"erro: harness {harness!r} desconhecido — use um de {sorted(HARNESSES)}")
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
        texto_cfg = (cfg.read_text(encoding="utf-8")
                     .replace("__MOTOR__", _yaml_str(valor_motor))
                     .replace("harness: [claude-code]", f"harness: [{harness}]")
                     .replace("__CASA__", _yaml_str(casa or NOMES_PADRAO["casa"]))
                     .replace("__USUARIO__", _yaml_str(usuario or NOMES_PADRAO["usuario"])))
        cfg.write_text(texto_cfg, encoding="utf-8")
        for md in destino.rglob("*.md"):
            texto = md.read_text(encoding="utf-8")
            if "__DATA__" in texto:
                md.write_text(texto.replace("__DATA__", data), encoding="utf-8")
        escrever_harness(destino, motor=MOTOR)   # CLAUDE.md, .claude/rules/, .claude/skills/
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
    ap.add_argument("--harness", default="claude-code", choices=sorted(HARNESSES),
                    help="alvo do harness (default: claude-code; os demais são reservados)")
    ap.add_argument("--casa", help="nome da sua casa de gestão (default: %(default)s)",
                    default=NOMES_PADRAO["casa"])
    ap.add_argument("--usuario", help="como o coordenador se dirige a você (default: %(default)s)",
                    default=NOMES_PADRAO["usuario"])
    ap.add_argument("--so-skills", action="store_true",
                    help="só (re)instala as skills em .claude/skills/ de um workspace existente")
    args = ap.parse_args()
    if args.so_skills:
        n = instalar_skills(args.destino)
        print(f"{n} skill(s) instalada(s) em {Path(args.destino).resolve() / '.claude' / 'skills'}")
        return
    destino = criar(args.destino, com_git=not args.sem_git, data=args.data, motor=args.motor,
                    harness=args.harness, casa=args.casa, usuario=args.usuario)
    print(f"Workspace criado em {destino}")
    print("Próximo passo: abra o Claude Code na pasta e cole /jabuti-init")
    print("Este workspace é PRIVADO por desenho: não publique este repositório.")


if __name__ == "__main__":
    main()
