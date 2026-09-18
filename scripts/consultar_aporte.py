"""Diz para onde vai o aporte, pela política que VOCÊ declarou.

Uso: python scripts/consultar_aporte.py <raiz> VALOR [--modo cascata|concentrar|proporcional]
                                        [--todos] [--data AAAA-MM-DD]

Não grava nada. Lê dados/ e politica/01-alocacao-alvo.md, valora a carteira e imprime a fila por
BLOCO. Aporte zero é uso legítimo: é o mês em que você não aportou, e o texto diz o que o mercado
moveu nas bandas.

Cote antes de decidir: a fila é aritmética sobre o preço que está em dados/cotacoes.csv. Se a
cotação estiver velha, a pendência aparece impressa.

Códigos de saída: 0 fila impressa · 1 dados/ ou política não sustentam o número
· 2 uso inválido (argparse)
"""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from po.cli import caminho_do_erro, mensagem_os, preparar_console  # noqa: E402

preparar_console()   # antes dos demais imports de po.*

from po.aporte import MODOS, distribuir  # noqa: E402
from po.carteira import valorar  # noqa: E402
from po.numeros import formatar_brl, parse_valor  # noqa: E402

RODAPE = "isto executa a política que você declarou; não é recomendação de investimento"


def _fila(c, aporte, modo):
    itens, sobra = distribuir(c.por_bloco, c.bandas, aporte, modo)
    print(f"\n  modo: {modo}")
    for i in itens:
        print(f"  {i.bloco:<10} atual {formatar_brl(i.atual):>12}   "
              f"gap {formatar_brl(i.gap):>12}   sugerido {formatar_brl(i.sugerido):>12}")
    print(f"  sobra: R$ {formatar_brl(sobra)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", help="raiz do workspace")
    ap.add_argument("valor", help="quanto você tem para aportar (0 é válido: o mês sem aporte)")
    ap.add_argument("--modo", default="cascata", choices=MODOS)
    ap.add_argument("--todos", action="store_true",
                    help="imprime as três alternativas, para você comparar antes de escolher")
    ap.add_argument("--data", help="AAAA-MM-DD a usar como hoje (default: hoje)")
    args = ap.parse_args()
    raiz = Path(args.raiz).resolve()
    if not raiz.is_dir():
        print(f"erro: workspace {args.raiz} não existe")
        sys.exit(1)
    aporte = parse_valor(args.valor)
    if aporte is None:
        print(f"erro: VALOR não é um número que eu saiba ler: {args.valor!r} — use 1500 ou 1.500,00")
        sys.exit(1)
    hoje = None
    if args.data:
        try:
            hoje = datetime.date.fromisoformat(args.data)
        except ValueError:
            print(f"erro: --data inválida: {args.data!r} — use AAAA-MM-DD")
            sys.exit(1)
    try:
        c = valorar(raiz, hoje=hoje)
        print(f"Total investido: R$ {formatar_brl(c.total_brl)} · "
              f"aporte consultado: R$ {formatar_brl(aporte)}")
        if not c.bandas:
            print("\nNenhuma banda declarada em politica/01-alocacao-alvo.md — sem política não há "
                  "fila. Rode /jabuti-estrategia para declarar as suas.")
            sys.exit(1)
        # ANTES da fila, não depois: fila calculada sobre valor velho (o fundo que ninguém
        # atualizou) é lida como resposta, e o aviso no rodapé chega tarde.
        if c.avisos:
            print("\nAntes de decidir:")
            for a in c.avisos:
                print(f"  - {a}")
        for modo in (MODOS if args.todos else (args.modo,)):
            _fila(c, aporte, modo)
    except ValueError as e:
        print(f"erro: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"erro: {caminho_do_erro(e, raiz, args.raiz)} não encontrado — confira a raiz do "
              "workspace.")
        sys.exit(1)
    except OSError as e:
        print(mensagem_os(e, raiz))
        sys.exit(1)
    print(f"\n{RODAPE}")


if __name__ == "__main__":
    main()
