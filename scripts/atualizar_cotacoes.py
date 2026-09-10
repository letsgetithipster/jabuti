"""Atualiza cotações do workspace: posicoes.csv → provider → append em dados/cotacoes.csv.

Uso: python scripts/atualizar_cotacoes.py <raiz> [--dry-run] [--manual TICKER=PRECO ...]

Sem rede: nada é gravado (nunca preço de memória). Cada linha carrega fonte, data e hora.
Variação > 30% contra a última cotação grava a cotação E propõe linha em eventos.csv
(variacao-anomala, confirmado nao) para você confirmar.

Códigos de saída: 0 tudo obtido e gravado · 1 erro que impediu a rodada (nada gravado)
· 2 sem rede (nada gravado)
· 3 resultado parcial: parte obtida e parte falhou (inclui --dry-run com falha; o texto diz o que foi gravado)
"""
import argparse
import csv
import io
import math
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
from po.numeros import formatar_brl, formatar_canonico  # noqa: E402

_ESPACO = re.compile(r"\s+")
_COM_MOEDA = re.compile(r"^([+-]?)(?:r\$|us\$|\$)?(.*)$", re.IGNORECASE)
_TRES_CASAS = re.compile(r"[+-]?\d{1,3}\.\d{3}")


def _preco_digitado(texto: str) -> float:
    """Preço que o USUÁRIO digita, em pt-BR estrito: vírgula é decimal, ponto é milhar.

    Não usa parse_valor de propósito: aquele parser lê export de corretora, onde milhar com
    vírgula existe, e leria '5,432' como 5432 — ou seja, leria errado justamente a forma que
    esta função sugere quando recusa uma entrada ambígua. Aqui a vírgula é sempre decimal, e
    por isso toda sugestão dada numa recusa é aceita por esta mesma função.
    """
    sinal, corpo = _COM_MOEDA.match(_ESPACO.sub("", texto)).groups()
    if _TRES_CASAS.fullmatch(corpo):   # 5.432 pode ser milhar (pt-BR) ou decimal (en-US)
        raise SystemExit(
            f"erro: --manual {texto.strip()!r} é ambíguo: '{corpo}' pode ser milhar ou decimal. "
            f"Escreva {corpo.replace('.', ',')} para decimal, ou {corpo.replace('.', '')} para milhar.")
    corpo = corpo.replace(".", "").replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d+)?", corpo):
        raise SystemExit(f"erro: preço inválido em --manual {texto.strip()!r}")
    valor = float(sinal + corpo)
    if not math.isfinite(valor) or valor <= 0:
        raise SystemExit(f"erro: preço tem que ser positivo em --manual {texto.strip()!r}")
    return valor


def _manual(itens: list[str]) -> dict[str, float]:
    out = {}
    for item in itens:
        if "=" not in item:
            raise SystemExit(f"erro: --manual espera TICKER=PRECO, recebi {item!r}")
        ticker, preco = item.split("=", 1)
        out[ticker.strip().upper()] = _preco_digitado(preco)
    return out


def _pct(fracao: float | None) -> str:
    return "primeira cotação" if fracao is None else f"{fracao * 100:+.1f}%".replace(".", ",")


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
    except OSError as e:
        print(_mensagem_os(e, args.raiz))
        sys.exit(1)
    except ValueError as e:
        print(f"erro: {e}")
        sys.exit(1)
    for c in rel.obtidas:
        marca = "  (saldo: 1,00 por definição da unidade)" if c.ticker in rel.sinteticas else ""
        if c.data != rel.hoje:
            marca += "  (não é de hoje)"
        preco_txt = formatar_brl(c.preco) if c.preco >= 0.01 else formatar_canonico(c.preco)
        print(f"  {c.ticker:<10} {preco_txt:>12} {c.moeda}  {c.fonte:<8} {c.data} {c.hora}  "
              f"{_pct(rel.variacoes.get(c.ticker))}{marca}")
    for t in rel.ja_atualizadas:
        print(f"  {t}: 1,00 já definida hoje")
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
        if rel.pedidos == 0:
            print("\nNada gravado: dados/posicoes.csv não tem posições ainda.")
        else:
            print("\nNada gravado: nada novo a buscar.")
    else:
        print("\nNada gravado: nenhuma cotação obtida.")
    parcial = bool(rel.falhas or rel.propostas_nao_gravadas) and bool(rel.gravadas or (rel.dry_run and rel.obtidas))
    sys.exit(3 if parcial else (1 if rel.falhas else 0))


if __name__ == "__main__":
    main()
