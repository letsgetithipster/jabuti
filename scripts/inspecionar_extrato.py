"""Mostra a estrutura de um documento de corretora (abas, cabeçalhos, amostra) para
desenhar o mapeamento. Não converte nem grava nada.

Uso: python scripts/inspecionar_extrato.py <arquivo> [--aba NOME|N] [--linhas N]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):   # console cp1252 do Windows não escreve ≤ nem →
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from po.ingestao.inspecao import N_PADRAO, inspecionar  # noqa: E402
from po.ingestao.leitores import DependenciaAusente  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivo")
    ap.add_argument("--aba", help="xlsx: nome ou índice (0-based) da aba; default: todas")
    ap.add_argument("--linhas", type=int, default=N_PADRAO, help=f"linhas de amostra (default {N_PADRAO})")
    args = ap.parse_args()
    aba = int(args.aba) if args.aba is not None and args.aba.isdigit() else args.aba
    try:
        print(inspecionar(args.arquivo, aba=aba, n=args.linhas))
    except DependenciaAusente as e:
        print(f"erro: {e}")
        sys.exit(1)
    except OSError as e:   # PermissionError é irmã de FileNotFoundError, não filha — pega as duas
        caminho = e.filename or args.arquivo
        motivo = e.strerror or str(e)
        print(f"erro: não consegui ler {caminho} ({motivo}). O arquivo está aberto no Excel "
             "ou o OneDrive está sincronizando?")
        sys.exit(1)


if __name__ == "__main__":
    main()
