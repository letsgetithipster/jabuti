"""Regenera estado/ESTADO.md a partir de dados/ (posições × cotações × câmbio) e da política.

Uso: python scripts/gerar_estado.py <raiz> [--data AAAA-MM-DD]

ESTADO.md nunca se edita à mão. Rode depois de importar extrato ou atualizar cotações.

Códigos de saída:
  0  ESTADO.md regenerado
  1  dados/ não sustenta o número, ou arquivo ilegível/travado
  2  uso inválido (argumento faltando ou desconhecido)
"""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from po.cli import caminho_do_erro, mensagem_os, preparar_console  # noqa: E402
from po.estado import gerar_estado  # noqa: E402

preparar_console()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", help="raiz do workspace")
    # --data existe para que o exemplo do repo seja regenerável pelo mesmo comando de
    # sempre, sem a edição à mão que a regra "gerado nunca se edita" proíbe.
    ap.add_argument("--data", help="data-referencia a gravar (AAAA-MM-DD; default: hoje)")
    args = ap.parse_args()
    # resolve UMA vez: o caminho devolvido tem que ser comparável com a raiz para virar relativo,
    # e `gerar_estado.py exemplos/workspace-exemplo`, o comando que regenera o exemplo do
    # repo, passa caminho relativo.
    raiz = Path(args.raiz).resolve()
    if not raiz.is_dir():   # mesma frase do validador; sem isto o erro sai como "dados/posicoes.csv não encontrado"
        print(f"erro: workspace {args.raiz} não existe")
        sys.exit(1)
    hoje = None
    if args.data:
        try:
            hoje = datetime.date.fromisoformat(args.data)
        except ValueError:
            print(f"erro: --data inválida: {args.data!r} — use AAAA-MM-DD")
            sys.exit(1)
    try:
        caminho = gerar_estado(raiz, hoje=hoje)
    except ValueError as e:
        print(f"erro: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        # arquivo que falta não está "aberto no Excel": a frase de mensagem_os mandaria
        # procurar a causa errada. É o erro mais provável aqui (raiz trocada), então tem
        # frase própria em vez do errno cru em inglês que o str(e) devolveria.
        print(f"erro: {caminho_do_erro(e, raiz, args.raiz)} não encontrado — confira a raiz do "
              "workspace (scripts/criar_workspace.py cria uma nova).")
        sys.exit(1)
    except OSError as e:
        print(mensagem_os(e, raiz))
        sys.exit(1)
    texto = caminho.read_text(encoding="utf-8")
    total = next(l for l in texto.splitlines() if l.startswith("Total investido:"))
    print(f"{caminho.relative_to(raiz).as_posix()} regenerado — {total}")
    pendencias = texto.split("## Pendências\n", 1)[1].strip()
    print("Pendências:\n" + pendencias)


if __name__ == "__main__":
    main()
