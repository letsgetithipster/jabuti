"""Atualiza cotações do workspace: carteira derivada do ledger (fills + eventos + ativos.csv) →
provider → append em dados/cotacoes.csv.

Uso: python scripts/atualizar_cotacoes.py <raiz> [--dry-run] [--manual TICKER=PRECO ...]

Sem rede: nada é gravado (nunca preço de memória). Cada linha carrega fonte, data e hora.
Variação > 30% contra a última cotação grava a cotação E propõe linha em eventos.csv
(variacao-anomala, confirmado nao) para você confirmar.

Códigos de saída: 0 tudo obtido e gravado · 1 erro que impediu a rodada (nada gravado)
· 2 sem rede (nada gravado)
· 3 resultado parcial: parte obtida e parte falhou (inclui --dry-run com falha; o texto diz o que foi gravado)

O que a rodada não alcançou sozinha (fundo, previdência, renda fixa, ticker que o provider não
achou) sai nomeado no fim, com o último valor conhecido e o comando --manual pronto. Enquanto essa
lista existir, a posição do mês não está atualizada.
"""
import argparse
import csv
import io
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from po.cli import mensagem_os, preparar_console  # noqa: E402

preparar_console()   # antes dos demais imports de po.*: se um deles
                     # quebrar, o traceback ainda sai legível no cp1252

from po.cotacoes.atualizar import atualizar  # noqa: E402
from po.cotacoes.tipos import SemRede  # noqa: E402
from po.csvs import SCHEMAS  # noqa: E402
from po.numeros import formatar_brl, formatar_canonico  # noqa: E402


ESTE = Path(__file__).resolve()
# A skill /jabuti-mes ramifica por esta frase; tests/test_skills_catalogo.py cobra que ela a cite.
FALTA_VOCE = "Falta você informar (não consegui atualizar sozinho):"

_ESPACO = re.compile(r"\s+")
_COM_MOEDA = re.compile(r"^([+-]?)(?:r\$|us\$|\$)?(.*)$", re.IGNORECASE)
_MILHAR_PONTO = re.compile(r"^\d{1,3}(\.\d{3}){2,}$")   # 12.345.678: vários grupos, só milhar
_AMBIGUO = re.compile(r"^[1-9]\d{0,2}\.\d{3}$")         # 5.432: milhar (pt-BR) ou decimal (en-US)
_NUMERO = re.compile(r"^\d+(\.\d+)?$")


def _preco_digitado(texto: str) -> float:
    """Preço que o USUÁRIO digita. A regra é explícita porque ler errado aqui vira preço
    errado gravado, e este é o único lugar do sistema onde um humano digita um número:

      1.234,56 e 1,234.56  → o separador MAIS À DIREITA é o decimal (as duas formas valem)
      5,432                → vírgula é sempre decimal em entrada digitada
      41.50 · 0.5 · 30.00  → ponto sozinho com qualquer quantidade de casas != 3 é decimal
      0.001                → idem: parte inteira 0 não pode ser grupo de milhar
      12.345.678           → ponto formando vários grupos de 3 é milhar
      5.432 · 1.500        → RECUSADO, é o único caso ambíguo; a recusa sugere as duas formas

    Não usa parse_valor de propósito, e o motivo não é o mesmo dos dois lados. parse_valor lê
    um formato DECLARADO por um mapeamento: em pt-BR ele resolve '5.432' como 5432 sem perguntar,
    e recusa '1,234.56' por ser do outro formato. Aqui não há mapa que declare nada — há uma
    pessoa digitando, que tanto pode ter copiado de uma tela brasileira quanto de uma americana.
    Por isso esta função aceita as duas formas e, no único caso em que elas colidem ('5.432'),
    RECUSA e devolve as duas escritas possíveis. Adivinhar seria gravar preço errado em silêncio.
    """
    sinal, corpo = _COM_MOEDA.match(_ESPACO.sub("", texto)).groups()
    tem_ponto, tem_virgula = "." in corpo, "," in corpo
    if tem_ponto and tem_virgula:
        if corpo.rfind(",") > corpo.rfind("."):
            corpo = corpo.replace(".", "").replace(",", ".")
        else:
            corpo = corpo.replace(",", "")
    elif tem_virgula:
        corpo = corpo.replace(",", ".")
    elif _AMBIGUO.fullmatch(corpo):
        raise SystemExit(
            f"erro: --manual {texto.strip()!r} é ambíguo: '{corpo}' pode ser milhar ou decimal. "
            f"Escreva {sinal}{corpo.replace('.', ',')} para decimal, "
            f"ou {sinal}{corpo.replace('.', '')} para milhar.")
    elif _MILHAR_PONTO.fullmatch(corpo):
        corpo = corpo.replace(".", "")
    if not _NUMERO.fullmatch(corpo):
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", help="raiz do workspace")
    ap.add_argument("--dry-run", action="store_true", help="busca e reporta, não grava")
    # action=append + nargs=+ e achatamento: com nargs="*", `--manual PETR4=36 --manual HGLG11=160`
    # devolvia só o segundo, em silêncio (decisão 16). `--manual A=1 B=2` numa flag só continua valendo.
    ap.add_argument("--manual", action="append", nargs="+", default=None, metavar="TICKER=PRECO",
                    help="cotação colada pelo usuário (fonte gravada como manual); "
                         "vários por flag, e a flag pode repetir")
    args = ap.parse_args()
    manual = [item for grupo in (args.manual or []) for item in grupo]
    try:
        rel = atualizar(args.raiz, manual=_manual(manual), dry_run=args.dry_run)
    except SemRede as e:
        print(f"Sem acesso à rede ({e}). Nada gravado — não uso preço de memória. "
              "Tente de novo com conexão ou passe --manual TICKER=PRECO.")
        sys.exit(2)
    except OSError as e:
        print(mensagem_os(e, args.raiz))
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
            print("\nNada gravado: o ledger não tem posições ainda (dados/fills.csv sem fill — "
                  "importe um extrato ou registre um saldo-inicial).")
        else:
            print("\nNada gravado: nada novo a buscar.")
    else:
        print("\nNada gravado: nenhuma cotação obtida.")
    if rel.pendentes:
        print(f"\n{FALTA_VOCE}")
        for ticker, ultima in rel.pendentes:
            if ultima:
                print(f"  {ticker:<10} último valor: {formatar_brl(ultima['preco'])} {ultima['moeda']} "
                      f"em {ultima['data']} ({ultima['fonte']})")
            else:
                print(f"  {ticker:<10} nenhum valor ainda")
        print("Pegue o valor atual na corretora ou no banco e rode:")
        print(f"  python {ESTE} {args.raiz} --manual "
              + " ".join(f"{ticker}=VALOR" for ticker, _ in rel.pendentes))
        print("VALOR é o preço de UMA unidade, na base em que a quantidade foi registrada "
              "(posição lançada com quantidade 1: o saldo atual).")
        print("Enquanto esta lista existir, a posição do mês NÃO está atualizada: "
              "não avalie aporte antes.")
    parcial = bool(rel.falhas or rel.propostas_nao_gravadas) and bool(rel.gravadas or (rel.dry_run and rel.obtidas))
    sys.exit(3 if parcial else (1 if rel.falhas else 0))


if __name__ == "__main__":
    main()
