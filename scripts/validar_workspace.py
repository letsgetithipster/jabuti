"""CLI do validador. Uso: python scripts/validar_workspace.py <raiz> [--errors-only]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from po.cli import mensagem_os, preparar_console  # noqa: E402

preparar_console()   # antes dos demais imports de po.*: se um deles
                     # quebrar, o traceback ainda sai legível no cp1252

from po.validar import validar  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("raiz", nargs="?", default=".", help="raiz do workspace (default: .)")
    ap.add_argument("--errors-only", action="store_true", help="omite avisos na saída")
    args = ap.parse_args()
    try:
        erros, avisos = validar(args.raiz)
    except OSError as e:
        print(mensagem_os(e, args.raiz))
        sys.exit(1)
    for e in erros:
        print(f"ERRO  {e}")
    if not args.errors_only:
        for a in avisos:
            print(f"aviso {a}")
    print(f"{len(erros)} erro(s), {len(avisos)} aviso(s)")
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
