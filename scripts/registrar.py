"""Registra em dados/ o que VOCÊ fez: a compra, a venda e a classe de um ticker.

Uso:
  python scripts/registrar.py <raiz> ativo  TICKER=classe [TICKER=classe ...]
  python scripts/registrar.py <raiz> compra TICKER QTY PRECO [--taxa V] [--data AAAA-MM-DD]
                                            [--conta ID] [--sim] [--dry-run]
  python scripts/registrar.py <raiz> venda  TICKER QTY PRECO [--taxa V] [--data AAAA-MM-DD]
                                            [--conta ID] [--sim] [--dry-run]

A fronteira (GUARDRAILS, camada 1): preço de MERCADO entra por atualizar_cotacoes.py, com fonte,
data e hora. OPERAÇÃO SUA entra por aqui, com eco de confirmação, --dry-run e log datado. O que
você digita é DECLARADO POR VOCÊ e não conferido contra documento; a conferência acontece quando
a foto da corretora chegar (importar_extrato.py --conferir).

Este CLI não calcula posição. Ele monta o fill novo, entrega a linha do tempo inteira ao ledger e
imprime o que o ledger devolveu — venda acima do saldo e abertura fora de ordem já têm frase
acionável lá, e uma segunda aritmética aqui seria a segunda fonte que este desenho não tem.

Número em pt-BR: 36,00 e 36.00 valem; 1.802,90 vale.

Códigos de saída: 0 gravado (ou --dry-run) · 1 erro que impediu a rodada (nada gravado)
· 2 uso inválido (argparse) · 3 não confirmado (nada gravado)
"""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from po.cli import caminho_motor, mensagem_os, preparar_console  # noqa: E402

preparar_console()   # antes dos demais imports de po.*

from po.ativos import ler_ativos  # noqa: E402
from po.config import carregar_config, moedas_por_conta  # noqa: E402
from po.csvs import CLASSES, anexar_csv, ler_csv  # noqa: E402
from po.ingestao.artefatos import caminho_datado_livre  # noqa: E402
from po.ledger import calcular_saldos  # noqa: E402
from po.numeros import formatar_brl, parse_valor  # noqa: E402

ESTE = Path(__file__).resolve()
# (pasta do log, tipo no frontmatter) — o tipo é o vocabulário de check_frontmatter.TIPOS
LOG = {"compra": ("aportes", "log-aporte"), "venda": ("vendas", "log-venda")}


def _num(texto, rotulo):
    v = parse_valor(str(texto))
    if v is None:
        raise ValueError(f"{rotulo} não é um número que eu saiba ler: {texto!r} — "
                         "use 36,00 (ou 36.00)")
    return v


def _data(texto):
    if not texto:
        return datetime.date.today().isoformat()
    try:
        return datetime.date.fromisoformat(texto).isoformat()
    except ValueError:
        raise ValueError(f"--data inválida: {texto!r} — use AAAA-MM-DD") from None


def _conta(cfg, pedida):
    moedas = moedas_por_conta(cfg)
    if pedida:
        if pedida not in moedas:
            raise ValueError(f"conta {pedida!r} não declarada na config "
                             f"(contas: {sorted(moedas)})")
        return pedida, moedas[pedida]
    if len(moedas) == 1:
        return next(iter(moedas.items()))
    raise ValueError(f"a config declara {len(moedas)} contas ({sorted(moedas)}) — "
                     "diga em qual foi a operação com --conta")


def _fills(raiz):
    linhas, erros = ler_csv("fills", raiz / "dados" / "fills.csv")
    if erros:
        raise ValueError("dados/fills.csv com erros — corrija antes (rode o validador): "
                         f"{erros[0]}")
    return linhas


def _confirmar(args) -> bool:
    if args.sim:
        return True
    if not sys.stdin.isatty():
        print("  Nada gravado: esta sessão não tem terminal para perguntar. Confirme com --sim, "
              "ou veja de novo com --dry-run.")
        return False
    return input("  Confirma? [s/N] ").strip().lower() in ("s", "sim")


def _log(raiz, tipo, f, custo, saldo) -> Path:
    pasta, tipo_log = LOG[tipo]
    caminho = caminho_datado_livre(raiz / "logs" / pasta,
                                   f"{f['data']}-{f['ticker']}", ".md")
    caminho.write_text(
        "---\n"
        f"tipo: {tipo_log}\ndata: {f['data']}\nticker: {f['ticker']}\nconta: {f['conta']}\n"
        "origem: declarado-por-voce\n---\n\n"
        f"# {tipo.capitalize()} {f['data']} — {f['ticker']}\n\n"
        f"- Quantidade: {f['qty']:g}\n"
        f"- Preço: R$ {formatar_brl(f['preco'])}\n"
        f"- Taxa: R$ {formatar_brl(f['taxa'])}\n"
        f"- Custo total: R$ {formatar_brl(custo)}\n"
        f"- Saldo depois: {saldo.qty:g} @ R$ {formatar_brl(saldo.pm)}\n\n"
        "Valores declarados por você em `registrar.py`, não conferidos contra documento de "
        "corretora. A conferência acontece quando a foto da corretora chegar "
        "(`importar_extrato.py --conferir`).\n",
        encoding="utf-8", newline="\n")
    return caminho


def _operacao(raiz, cfg, args, tipo) -> int:
    ticker = args.ticker.upper()
    conta, moeda = _conta(cfg, args.conta)
    qty, preco, taxa = _num(args.qty, "QTY"), _num(args.preco, "PRECO"), _num(args.taxa, "--taxa")
    if qty <= 0 or preco <= 0:
        raise ValueError("QTY e PRECO têm que ser maiores que zero — venda usa o subcomando "
                         "`venda`, nunca sinal negativo")
    if taxa < 0:
        raise ValueError(f"--taxa não pode ser negativa: {args.taxa!r}")
    data = _data(args.data)
    classes, _erros, _origem = ler_ativos(raiz)
    if ticker not in classes:
        raise ValueError(
            f"{ticker} não tem classe declarada, e sem classe não há bloco nem banda. "
            f"Rode, ajustando a classe:\n"
            f"  python {ESTE} {raiz} ativo {ticker}=<classe>\n"
            f"  classes: {', '.join(sorted(CLASSES))}")
    linhas = _fills(raiz)
    antes, erros, _ = calcular_saldos(linhas)
    if erros:
        raise ValueError(f"o livro já tinha um problema antes desta linha — resolva primeiro: "
                         f"{erros[0]}")
    novo = {"data": data, "ticker": ticker, "tipo": tipo, "qty": qty, "preco": preco,
            "taxa": taxa, "conta": conta, "moeda": moeda}
    depois, erros, _ = calcular_saldos(linhas + [dict(novo)])
    if erros:
        raise ValueError(erros[0])   # a frase do ledger é a frase certa; não a reescreva
    s = depois[(ticker, conta)]
    custo = qty * preco + taxa
    print(f"  eco:   {tipo} · {ticker} · {qty:g} · R$ {formatar_brl(preco)} · "
          f"taxa R$ {formatar_brl(taxa)} · conta {conta} · {data}")
    if tipo == "compra":
        print(f"         custo total R$ {formatar_brl(custo)} · "
              f"saldo depois: {s.qty:g} @ R$ {formatar_brl(s.pm)}")
    else:
        pm = antes[(ticker, conta)].pm
        print(f"         resultado realizado R$ {formatar_brl((preco - pm) * qty - taxa)} "
              f"(({formatar_brl(preco)} − {formatar_brl(pm)}) × {qty:g}, menos a taxa) · "
              f"saldo depois: {s.qty:g} @ R$ {formatar_brl(s.pm)}")
        print("         resultado BRUTO: apuração de imposto não acontece aqui.")
    print("  Valores DECLARADOS POR VOCÊ, não conferidos contra documento.")
    if args.dry_run:
        print("  --dry-run: nada gravado.")
        return 0
    if not _confirmar(args):
        return 3
    n = anexar_csv("fills", raiz / "dados" / "fills.csv", [novo])
    try:
        log = f"log: {_log(raiz, tipo, novo, custo, s).relative_to(raiz).as_posix()}"
    except OSError as e:
        # O fill já é a verdade; o log é o registro dela. Dizer que o log faltou é melhor que
        # perder a operação por causa de uma pasta travada.
        log = f"LOG NÃO ESCRITO ({mensagem_os(e, raiz)}) — o fill entrou"
    print(f"  fills +{n} · {log}")
    motor = caminho_motor(raiz, cfg)
    print(f"  Agora rode: python {motor / 'scripts' / 'atualizar_cotacoes.py'} {raiz}")
    return 0


def _ativo(raiz, args) -> int:
    novas = []
    for par in args.pares:
        ticker, _, classe = par.partition("=")
        if not ticker or not classe:
            raise ValueError(f"{par!r} não está na forma TICKER=classe (ex.: PETR4=acoes-br)")
        if classe not in CLASSES:
            raise ValueError(f"classe {classe!r} fora do vocabulário: "
                             f"{', '.join(sorted(CLASSES))}")
        novas.append({"ticker": ticker.upper(), "classe": classe})
    if args.dry_run:
        print("  --dry-run: nada gravado.")
        return 0
    n = anexar_csv("ativos", raiz / "dados" / "ativos.csv", novas)
    for l in novas:
        print(f"  {l['ticker']} → {l['classe']}")
    print(f"  ativos +{n} em dados/ativos.csv. A última linha por ticker vence: corrigir uma "
          "classe é anexar a linha certa, nunca apagar a errada.")
    return 0


def _comuns(p):
    p.add_argument("--sim", action="store_true", help="grava sem perguntar")
    p.add_argument("--dry-run", action="store_true", help="mostra o eco e não grava")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", help="raiz do workspace")
    sub = ap.add_subparsers(dest="comando", required=True)
    for tipo in ("compra", "venda"):
        p = sub.add_parser(tipo, help=f"registra uma {tipo} que você já executou")
        p.add_argument("ticker")
        p.add_argument("qty")
        p.add_argument("preco")
        p.add_argument("--taxa", default="0", help="corretagem e emolumentos (default: 0)")
        p.add_argument("--data", help="AAAA-MM-DD da operação (default: hoje)")
        p.add_argument("--conta", help="id da conta na config (default: a única, se houver uma)")
        _comuns(p)
    p = sub.add_parser("ativo", help="declara a classe (bloco da política) de um ou mais tickers")
    p.add_argument("pares", nargs="+", metavar="TICKER=classe")
    _comuns(p)
    args = ap.parse_args()
    raiz = Path(args.raiz).resolve()
    if not raiz.is_dir():
        print(f"erro: workspace {args.raiz} não existe")
        sys.exit(1)
    try:
        cfg = carregar_config(raiz)
        codigo = _ativo(raiz, args) if args.comando == "ativo" \
            else _operacao(raiz, cfg, args, args.comando)
    except ValueError as e:
        print(f"erro: {e}")
        sys.exit(1)
    except OSError as e:
        print(mensagem_os(e, raiz))
        sys.exit(1)
    sys.exit(codigo)


if __name__ == "__main__":
    main()
