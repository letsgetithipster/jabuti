"""Ledger cronológico: fills + eventos societários → saldo de quantidade e preço médio, e daí a
posição derivada de toda a carteira.

É a única fonte de qty e PM do motor: `carteira.valorar` deriva a posição daqui e não lê mais
`dados/posicoes.csv`. `dados/` guarda evento e uma declaração estática; saldo, total e banda são
derivados na leitura, e não existe arquivo cuja edição mude o seu patrimônio. Enquanto
`posicoes.csv` ainda existir no workspace, ele é só a tabela antiga onde `po.ativos` ainda vai
buscar a classe de um ticker que ninguém declarou no arquivo novo.

Ordem do replay: data, depois tipo (`saldo-inicial` < `compra` < `evento` < `venda`), depois a
ordem do arquivo. Evento aplica ANTES de venda no mesmo dia porque desdobramento costuma ser
efetivo na abertura. `compra` e `saldo-inicial` somam custo (qty × preço + taxa); `venda` baixa ao
PM corrente (taxa de venda não altera PM) e não pode exceder o saldo daquele momento.

`estorno` não é inverso aritmético: é "remova da linha do tempo o fill que este estorno casa
exatamente", e o replay inteiro é refeito sem a linha. Por isso ele é exato para compra, venda e
abertura, e por isso a `data` do estorno é a do fill anulado — é o que torna o casamento único.
Append-only preservado: anexar_csv continua sendo o único writer.

Eventos aplicáveis: split, grupamento e bonificação confirmados, com razão em `novas:antigas`.
Split e grupamento são a MESMA fórmula (a/b, com a<b no grupamento). Tipo confirmado que o ledger
não sabe aplicar é ERRO NOMEADO, nunca no-op: com posição derivada, um `cisao` ignorado em
silêncio seria patrimônio errado com o validador verde.
"""
import re
from dataclasses import dataclass

from po.numeros import formatar_brl, formatar_decimal_brl

TOLERANCIA_QTY = 1e-6
_ORDEM_TIPO = {"saldo-inicial": 0, "compra": 1, "evento": 2, "venda": 3}
RAZAO_RE = re.compile(r"^(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)$")
EVENTOS_APLICAVEIS = {"split", "grupamento", "bonificacao"}


@dataclass
class Saldo:
    qty: float = 0.0
    custo: float = 0.0

    @property
    def pm(self) -> float:
        return self.custo / self.qty if self.qty > TOLERANCIA_QTY else 0.0


def _chave_de_casamento(f: dict) -> tuple:
    return (f["data"], f["ticker"], f["conta"],
            round(float(f["qty"]), 6), round(float(f["preco"]), 4), round(float(f["taxa"]), 2))


def casamentos_de_estornos(fills: list[dict]) -> dict[int, list[int]]:
    """{índice do estorno: índices dos fills que ele casa exatamente}, na ordem do arquivo.

    Um fill já anulado por estorno anterior não é candidato de novo. É a ÚNICA lógica de
    casamento: o replay a usa para decidir o que sai da linha do tempo e registrar.py a usa para
    recusar gravar um estorno que casaria zero ou mais de um fill."""
    estornados: set[int] = set()
    mapa: dict[int, list[int]] = {}
    for i, f in enumerate(fills):
        if f["tipo"] != "estorno":
            continue
        alvo = _chave_de_casamento(f)
        casam = [j for j, g in enumerate(fills)
                 if g["tipo"] in ("compra", "venda", "saldo-inicial") and j not in estornados
                 and _chave_de_casamento(g) == alvo]
        mapa[i] = casam
        if len(casam) == 1:
            estornados.add(casam[0])
    return mapa


def eventos_vigentes(eventos: list[dict]) -> list[dict]:
    """A última linha por (data, ticker) vence, espelhando csvs.ultimas_cotacoes: confirmar um
    evento é ANEXAR uma linha com confirmado=sim e a razão, nunca reescrever a proposta."""
    melhor: dict[tuple[str, str], tuple[int, dict]] = {}
    for i, e in enumerate(eventos):
        melhor[(e["data"], e["ticker"])] = (i, e)
    return [e for _, (_, e) in sorted(melhor.items(), key=lambda kv: (kv[0][0], kv[1][0]))]


def fator_de_eventos(eventos: list[dict], ticker: str, depois_de: str, ate: str) -> float:
    """Multiplicador de quantidade dos eventos CONFIRMADOS e aplicáveis de `ticker` com data em
    (depois_de, ate]. É o que o cotador usa para ajustar a base da comparação: um split 2:1
    confirmado divide o preço por 2, e sem isso recotar depois de confirmar propunha um SEGUNDO
    split. Razão ilegível vale 1,0 aqui: quem a acusa é o replay do ledger, na leitura."""
    fator = 1.0
    for e in eventos_vigentes(list(eventos)):
        if e["ticker"] != ticker or e["confirmado"] != "sim" or e["tipo"] not in EVENTOS_APLICAVEIS:
            continue
        if not (depois_de < e["data"] <= ate):
            continue
        f = _fator(e.get("razao"))
        if f is not None:
            fator *= (1.0 + f) if e["tipo"] == "bonificacao" else f
    return fator


def _fator(razao: str | None) -> float | None:
    m = RAZAO_RE.match(razao or "")
    if not m:
        return None
    novas, antigas = float(m.group(1)), float(m.group(2))
    if novas <= 0 or antigas <= 0:
        return None
    return novas / antigas


def _aplicar_evento(ev: dict, saldos: dict, erros: list[str], suspeitas: set) -> None:
    ticker, tipo = ev["ticker"], ev["tipo"]
    chaves = [k for k in saldos if k[0] == ticker]

    def suspender(msg: str) -> None:
        erros.append(msg)
        suspeitas.update(chaves)

    if tipo not in EVENTOS_APLICAVEIS:
        suspender(f"eventos.csv: {ticker} confirmado como {tipo!r} em {ev['data']} — o ledger não "
                  f"sabe o efeito desse tipo no saldo. Registre o efeito como fill "
                  f"(compra/venda/estorno) e deixe o evento como registro não aplicável, "
                  f"ou troque o tipo por um de {sorted(EVENTOS_APLICAVEIS)}")
        return
    fator = _fator(ev.get("razao"))
    if fator is None:
        suspender(f"eventos.csv: {ticker} {tipo} em {ev['data']} com razão {ev.get('razao')!r} — "
                  "o ledger precisa de 'novas:antigas' (ex.: 2:1 para split, 1:10 para grupamento)")
        return
    if tipo == "bonificacao":
        fator = 1.0 + fator     # bonificação SOMA as novas; split e grupamento SUBSTITUEM
    for k in chaves:
        if saldos[k].qty > TOLERANCIA_QTY:
            saldos[k].qty = round(saldos[k].qty * fator, 8)


def calcular_saldos(fills: list[dict], eventos: list[dict] | tuple = (), *,
                    ate: str | None = None) -> tuple[dict[tuple[str, str], Saldo], list[str], set]:
    """({(ticker, conta): Saldo}, erros, chaves suspeitas). Fills já validados (floats).

    `ate` (AAAA-MM-DD, inclusive) corta a linha do tempo: é o que devolve a posição de 31/12 lida
    em março. Chave em 'suspeitas' tem saldo derivado não confiável; quem for somar erro em cima
    dela suspende, para não empilhar erro derivado sobre erro de origem.
    """
    erros: list[str] = []
    suspeitas: set[tuple[str, str]] = set()
    saldos: dict[tuple[str, str], Saldo] = {}
    aberturas: set[tuple[str, str]] = set()

    fills = [f for f in fills if not ate or f["data"] <= ate]
    eventos = [e for e in eventos_vigentes(list(eventos))
               if e["confirmado"] == "sim" and (not ate or e["data"] <= ate)]

    estornados: set[int] = set()
    efetivos: list[tuple[int, dict]] = []
    casamentos = casamentos_de_estornos(fills)
    for i, f in enumerate(fills):
        if f["tipo"] != "estorno":
            efetivos.append((i, f))
            continue
        casam = casamentos[i]
        if len(casam) != 1:
            erros.append(f"fills.csv: estorno de {formatar_decimal_brl(f['qty'])} {f['ticker']} "
                         f"em {f['data']} (conta {f['conta']}, R$ {formatar_brl(f['preco'])}, "
                         f"taxa {formatar_brl(f['taxa'])}) casa "
                         f"{len(casam)} fill(s) — o estorno tem que repetir exatamente a linha "
                         "que anula, e casar uma só")
            suspeitas.add((f["ticker"], f["conta"]))
        else:
            estornados.add(casam[0])
    efetivos = [(i, f) for i, f in efetivos if i not in estornados]

    itens = [(f["data"], _ORDEM_TIPO.get(f["tipo"], 9), i, "fill", f) for i, f in efetivos]
    itens += [(e["data"], _ORDEM_TIPO["evento"], 10 ** 9 + k, "evento", e)
              for k, e in enumerate(eventos)]
    itens.sort(key=lambda t: (t[0], t[1], t[2]))

    for _, _, _, especie, x in itens:
        if especie == "evento":
            _aplicar_evento(x, saldos, erros, suspeitas)
            continue
        f = x
        chave = (f["ticker"], f["conta"])
        tipo = f["tipo"]
        if tipo in ("compra", "saldo-inicial"):
            if tipo == "saldo-inicial":
                if chave in aberturas:
                    erros.append(f"fills.csv: {f['ticker']} tem mais de um saldo-inicial na conta "
                                 f"{f['conta']} — a posição herdada abre uma vez só (o resto são compras)")
                    suspeitas.add(chave)
                    continue
                if chave in saldos:
                    erros.append(f"fills.csv: saldo-inicial de {f['ticker']} em {f['data']} vem depois de "
                                 f"outros fills na conta {f['conta']} — a abertura é o primeiro evento da posição")
                    suspeitas.add(chave)
                    continue
                aberturas.add(chave)
            s = saldos.setdefault(chave, Saldo())
            s.custo += f["qty"] * f["preco"] + f["taxa"]
            s.qty += f["qty"]
        elif tipo == "venda":
            s = saldos.get(chave)      # nunca cria entrada no caminho de erro
            disponivel = s.qty if s else 0.0
            if s is None or f["qty"] > disponivel + TOLERANCIA_QTY:
                erros.append(
                    f"fills.csv: venda de {formatar_decimal_brl(f['qty'])} {f['ticker']} em "
                    f"{f['data']} excede o saldo na conta {f['conta']} "
                    f"({formatar_decimal_brl(disponivel)}) — confira a ordem cronológica ou registre "
                    "um saldo-inicial anterior")
                suspeitas.add(chave)
                continue
            s.custo -= f["qty"] * s.pm
            s.qty -= f["qty"]
            if s.qty <= TOLERANCIA_QTY:
                s.qty, s.custo = 0.0, 0.0
        else:
            erros.append(f"fills.csv: tipo de fill desconhecido {tipo!r} em {f['ticker']} ({f['data']}) — "
                         "o ledger não sabe o efeito dessa linha no saldo")
            suspeitas.add(chave)
    return saldos, erros, suspeitas


def posicoes_de_fills(fills: list[dict], eventos: list[dict] | tuple = (),
                      classes: dict[str, str] | None = None, *,
                      ate: str | None = None) -> tuple[list[dict], list[str]]:
    """(posições, erros). Uma linha por (ticker, conta) com saldo > 0, no formato que o resto do
    motor já lê: ticker, classe, conta, qty, pm, moeda.

    `classes` é {ticker: classe}, a declaração da pessoa em dados/ativos.csv — o único campo de
    uma posição que não é derivável de um fill nem é fato de mercado. Ticker com fill e sem
    declaração sai com classe "" e um erro nomeado: sem classe não há bloco, e sem bloco a banda
    não tem como ser conferida. A moeda vem do fill (check_dados já cobra moeda da linha contra
    moeda da conta declarada na config).
    """
    classes = classes or {}
    saldos, erros, _ = calcular_saldos(fills, eventos, ate=ate)
    moedas = {(f["ticker"], f["conta"]): f["moeda"]
              for f in fills if not ate or f["data"] <= ate}
    posicoes, sem_classe = [], []
    for (ticker, conta), s in sorted(saldos.items()):
        if s.qty <= TOLERANCIA_QTY:
            continue
        if ticker not in classes and ticker not in sem_classe:
            sem_classe.append(ticker)
        posicoes.append({"ticker": ticker, "classe": classes.get(ticker, ""), "conta": conta,
                         "qty": round(s.qty, 8), "pm": round(s.pm, 8),
                         "moeda": moedas.get((ticker, conta), "BRL")})
    for ticker in sem_classe:
        erros.append(f"dados/ativos.csv: {ticker} tem fill mas nenhuma classe declarada — "
                     f"rode: python <motor>/scripts/registrar.py <raiz> ativo {ticker}=<classe> "
                     "(acoes-br, fiis, rv-int, reits-us, rf-br, cripto, caixa, commodities)")
    return posicoes, erros
