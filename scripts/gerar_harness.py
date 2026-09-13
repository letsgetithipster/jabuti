"""Compila o harness do workspace a partir de rules/ do motor e de vault.config.yaml.

Uso: python scripts/gerar_harness.py <raiz>

Escreve CLAUDE.md e .claude/rules/00-voz.md (alvo claude-code) e reinstala as skills em
.claude/skills/. Nunca edite esses arquivos à mão: o validador acusa divergência.

Códigos de saída:
  0  harness gerado
  1  config inválida, fonte ausente ou arquivo travado
  2  uso inválido
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from po.cli import mensagem_os, preparar_console  # noqa: E402

preparar_console()

from po.harness import escrever_harness  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", help="raiz do workspace")
    args = ap.parse_args()
    raiz = Path(args.raiz).resolve()
    if not raiz.is_dir():
        print(f"erro: workspace {args.raiz} não existe")
        sys.exit(1)
    try:
        escritos = escrever_harness(raiz)
    except (ValueError, FileNotFoundError) as e:
        print(f"erro: {e}")
        sys.exit(1)
    except OSError as e:
        print(mensagem_os(e, raiz))
        sys.exit(1)
    if not escritos:
        print("nenhum alvo compilável em vault.config.yaml (harness: só claude-code é gerado hoje); skills reinstaladas")
        return
    for p in escritos:
        print(f"{p.relative_to(raiz).as_posix()} gerado")
    print("skills reinstaladas em .claude/skills/")


if __name__ == "__main__":
    main()
