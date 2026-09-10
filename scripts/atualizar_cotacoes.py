"""Atualiza cotações do workspace: posicoes.csv → provider → append em dados/cotacoes.csv.

Uso: python scripts/atualizar_cotacoes.py <raiz> [--dry-run] [--manual TICKER=PRECO ...]

Sem rede: nada é gravado (nunca preço de memória). Cada linha carrega fonte, data e hora.
Variação > 30% contra a última cotação grava a cotação E propõe linha em eventos.csv
(variacao-anomala, confirmado nao) para você confirmar.

Códigos de saída: 0 tudo obtido e gravado · 1 erro que impediu a rodada (nada gravado)
· 2 sem rede (nada gravado) · 3 parcial: algo foi gravado E houve falha ou proposta não gravada
"""
import argparse
import csv
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):   # console cp1252 do Windows não escreve ≤ nem →
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from po.cotacoes.atualizar import atualizar  # noqa: E402
from po.cotacoes.tipos import SemRede  # noqa: E402
from po.csvs import SCHEMAS  # noqa: E402
from po.numeros import formatar_brl, formatar_canonico, parse_valor  # noqa: E402

_TRES_CASAS = re.compile(r"^\s*[+-]?\d{1,3}\.\d{3}\s*$")


def _manual(itens: list[str]) -> dict[str, float]:
    out = {}
    for item in itens:
        if "=" not in item:
            raise SystemExit(f"erro: --manual espera TICKER=PRECO, recebi {item!r}")
        ticker, preco = item.split("=", 1)
        if _TRES_CASAS.match(preco):
            raise SystemExit(f"erro: --manual {item!r} é ambíguo: '{preco.strip()}' pode ser milhar ou decimal. "
                             f"Escreva {preco.strip().replace('.', ',')} para decimal, "
                             f"ou {preco.strip().replace('.', '')} para milhar.")
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
    except (OSError, ValueError) as e:
        print(f"erro: {e}")
        sys.exit(1)
    for c in rel.obtidas:
        marca = "  (saldo: 1,00 por definição da unidade)" if c.ticker in rel.sinteticas else ""
        if c.data != rel.hoje:
            marca += "  (não é de hoje)"
        preco_txt = formatar_brl(c.preco) if c.preco >= 0.01 else formatar_canonico(c.preco)
        print(f"  {c.ticker:<10} {preco_txt:>12} {c.moeda}  {c.fonte:<8} {c.data} {c.hora}  "
              f"{_pct(rel.variacoes.get(c.ticker))}{marca}")
    for f in rel.falhas:
        print(f"  FALHA  {f}")
    if rel.anomalias:
        print("\nATENÇÃO — variação acima de 30% (conferir split/evento antes de confiar):")
        for a in rel.anomalias:
            print(f"  {a}")
    if rel.propostas_nao_gravadas:
        motivo, linhas = rel.propostas_nao_gravadas
        print(f"\nATENÇÃO: a cotação foi gravada, mas a proposta em dados/eventos.csv NÃO ({motivo}).")
        print("Sem ela a anomalia some: o preço novo vira a base e a próxima comparação dá 0%.")
        print("Cole estas linhas no fim de dados/eventos.csv:")
        for linha in linhas:
            # csv.writer (não ",".join) porque razão carrega vírgula do formatar_brl (ex.:
            # "-62,50%"); sem aspas, colar a linha crua quebraria as colunas de eventos.csv.
            buf = io.StringIO()
            csv.writer(buf, lineterminator="").writerow([str(linha[campo]) for campo in SCHEMAS["eventos"]])
            print("  " + buf.getvalue())
    if rel.dry_run:
        print(f"\n--dry-run: nada gravado ({len(rel.obtidas)} cotação(ões) obtida(s), {len(rel.falhas)} falha(s), "
              f"{len(rel.propostas)} proposta(s) de anomalia seriam criadas)")
    elif rel.gravadas:
        # rel.propostas_nao_gravadas já foi avisado acima — não repetir aqui como se tivesse ido
        if rel.propostas_nao_gravadas:
            extra = ""
        elif rel.propostas:
            extra = f"; dados/eventos.csv +{len(rel.propostas)} proposta(s) para confirmar"
        else:
            extra = ""
        print(f"\nGravado: dados/cotacoes.csv +{rel.gravadas}{extra}")
    elif not rel.obtidas and not rel.falhas:
        print("\nNada gravado: dados/posicoes.csv não tem posições ainda.")
    else:
        print("\nNada gravado: nenhuma cotação obtida.")
    parcial = bool(rel.falhas or rel.propostas_nao_gravadas) and bool(rel.gravadas or (rel.dry_run and rel.obtidas))
    sys.exit(3 if parcial else (1 if rel.falhas else 0))


if __name__ == "__main__":
    main()
