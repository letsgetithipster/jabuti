"""Mostra a estrutura de um documento de corretora (abas, cabeçalhos, amostra) para
desenhar o mapeamento. Não converte nem grava nada.

Uso: python scripts/inspecionar_extrato.py <arquivo> [--aba NOME|N] [--linhas N]

Códigos de saída:
  0  documento inspecionado (o dump saiu no stdout)
  1  não deu para inspecionar: arquivo inexistente, travado, aba que não existe ou
     dependência ausente (openpyxl para xlsx)
  2  uso inválido (argumento faltando ou desconhecido)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from po.cli import mensagem_os, preparar_console  # noqa: E402

preparar_console()   # antes dos demais imports de po.*: se um deles
                     # quebrar, o traceback ainda sai legível no cp1252

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
    except (DependenciaAusente, ValueError) as e:
        print(f"erro: {e}")
        sys.exit(1)
    except FileNotFoundError as e:   # antes de OSError: "aberto no Excel?" não ajuda quem errou o caminho
        print(f"erro: {e}")
        sys.exit(1)
    except OSError as e:   # PermissionError é irmã de FileNotFoundError, não filha — pega as duas
        print(mensagem_os(e, padrao=args.arquivo))
        sys.exit(1)


if __name__ == "__main__":
    main()
