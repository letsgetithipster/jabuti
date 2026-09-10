"""Atualiza cotações do workspace: posicoes.csv → provider → append em dados/cotacoes.csv.

Uso: python scripts/atualizar_cotacoes.py <raiz> [--dry-run] [--manual TICKER=PRECO ...]

Sem rede: nada é gravado (nunca preço de memória). Cada linha carrega fonte, data e hora.
Variação > 30% contra a última cotação grava a cotação E propõe linha em eventos.csv
(variacao-anomala, confirmado nao) para você confirmar.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):   # console cp1252 do Windows não escreve ≤ nem →
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from po.cotacoes.atualizar import atualizar  # noqa: E402
from po.cotacoes.tipos import SemRede  # noqa: E402
from po.numeros import formatar_brl, parse_valor  # noqa: E402


def _manual(itens: list[str]) -> dict[str, float]:
    out = {}
    for item in itens:
        if "=" not in item:
            raise SystemExit(f"erro: --manual espera TICKER=PRECO, recebi {item!r}")
        ticker, preco = item.split("=", 1)
        valor = parse_valor(preco)
        if valor is None or valor <= 0:
            raise SystemExit(f"erro: preço inválido em --manual {item!r}")
        out[ticker.strip().upper()] = valor
    return out


def _pct(fracao: float | None) -> str:
    return "primeira cotação" if fracao is None else f"{fracao * 100:+.1f}%".replace(".", ",")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", help="raiz do workspace")
    ap.add_argument("--dry-run", action="store_true", help="busca e reporta, não grava")
    ap.add_argument("--manual", nargs="*", default=[], metavar="TICKER=PRECO",
                    help="cotação colada pelo usuário (fonte gravada como manual)")
    args = ap.parse_args()
    try:
        rel = atualizar(args.raiz, manual=_manual(args.manual), dry_run=args.dry_run)
    except SemRede as e:
        print(f"Sem acesso à rede ({e}). Nada gravado — não uso preço de memória. "
              "Tente de novo com conexão ou passe --manual TICKER=PRECO.")
        sys.exit(2)
    except (FileNotFoundError, ValueError) as e:
        print(f"erro: {e}")
        sys.exit(1)
    for c in rel.obtidas:
        marca = "  (saldo: 1,00 por definição da unidade)" if c.ticker in rel.sinteticas else ""
        print(f"  {c.ticker:<10} {formatar_brl(c.preco):>12} {c.moeda}  {c.fonte:<8} {c.data} {c.hora}  "
              f"{_pct(rel.variacoes.get(c.ticker))}{marca}")
    for f in rel.falhas:
        print(f"  FALHA  {f}")
    if rel.anomalias:
        print("\nATENÇÃO — variação acima de 30% (conferir split/evento antes de confiar):")
        for a in rel.anomalias:
            print(f"  {a}")
    if rel.dry_run:
        print(f"\n--dry-run: nada gravado ({len(rel.obtidas)} cotação(ões) obtida(s), {len(rel.falhas)} falha(s))")
    elif rel.gravadas:
        extra = f"; dados/eventos.csv +{len(rel.propostas)} proposta(s) para confirmar" if rel.propostas else ""
        print(f"\nGravado: dados/cotacoes.csv +{rel.gravadas}{extra}")
    else:
        print("\nNada gravado: nenhuma cotação obtida.")
    sys.exit(1 if rel.falhas else 0)


if __name__ == "__main__":
    main()
