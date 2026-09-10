"""CLI do validador. Uso: python scripts/validar_workspace.py <raiz> [--errors-only]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):   # console cp1252 do Windows não escreve ≤ nem →
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from po.validar import validar  # noqa: E402


def _mensagem_os(e: OSError, raiz: str | Path) -> str:
    """PermissionError/IsADirectoryError etc. viram frase acionável, com caminho relativo ao
    workspace quando possível — não um repr de exceção nem um traceback."""
    caminho = e.filename or str(e)
    try:
        caminho = Path(caminho).resolve().relative_to(Path(raiz).resolve()).as_posix()
    except (ValueError, TypeError, OSError):
        pass
    motivo = e.strerror or str(e)
    return (f"erro: não consegui ler/gravar {caminho} ({motivo}). "
           "O arquivo está aberto no Excel ou o OneDrive está sincronizando?")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("raiz", nargs="?", default=".", help="raiz do workspace (default: .)")
    ap.add_argument("--errors-only", action="store_true", help="omite avisos na saída")
    args = ap.parse_args()
    try:
        erros, avisos = validar(args.raiz)
    except OSError as e:
        print(_mensagem_os(e, args.raiz))
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
