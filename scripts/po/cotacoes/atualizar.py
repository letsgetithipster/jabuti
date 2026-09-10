"""Orquestração do /atualizar-cotacoes: posições → pedidos → providers → append em cotacoes.csv.

Regras: sem rede, SemRede sobe e nada é gravado; cada cotação carrega fonte, data e hora;
variação > 30% contra a última cotação vencedora grava a cotação (é o preço real) E propõe
uma linha em eventos.csv (tipo variacao-anomala, confirmado nao) sem duplicar proposta aberta.
Saldo em conta (classe caixa sem código da B3) vale 1,00 na própria moeda por definição da
unidade — não é preço de mercado inventado, é a identidade que o encoding qty×pm já assume.
Renda fixa (rf-br) NÃO ganha esse tratamento: o valor dela muda e exige --manual.
"""
import datetime
from dataclasses import dataclass, field
from pathlib import Path

from po.config import carregar_config, provider_cambio
from po.cotacoes.providers import criar_provider
from po.cotacoes.providers.manual import ManualProvider
from po.cotacoes.tipos import Cotacao, pedidos_de_posicoes, sem_cotacao_de_mercado
from po.csvs import anexar_csv, ler_csv, ultimas_cotacoes

LIMIAR_ANOMALIA = 0.30


@dataclass
class Relatorio:
    obtidas: list[Cotacao] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)
    variacoes: dict[str, float | None] = field(default_factory=dict)  # ticker -> fração vs última (None = primeira)
    anomalias: list[str] = field(default_factory=list)
    propostas: list[dict] = field(default_factory=list)                # linhas propostas em eventos.csv
    sinteticas: list[str] = field(default_factory=list)                # tickers precificados por definição (saldo)
    gravadas: int = 0
    dry_run: bool = False


def _ler_limpo(nome: str, raiz: Path) -> list[dict]:
    linhas, erros = ler_csv(nome, raiz / "dados" / f"{nome}.csv")
    if erros:
        raise ValueError(f"dados/{nome}.csv com erros — corrija antes (rode o validador): {erros[0]}")
    return linhas


def atualizar(raiz: str | Path, *, manual: dict[str, float] | None = None, dry_run: bool = False,
              agora: datetime.datetime | None = None, buscar=None, provider=None, cambio=None) -> Relatorio:
    """provider/cambio: instâncias prontas (injeção em teste); default vem da config via criar_provider."""
    raiz = Path(raiz)
    agora = agora or datetime.datetime.now()
    hoje, hora_agora = agora.strftime("%Y-%m-%d"), agora.strftime("%H:%M")
    cfg = carregar_config(raiz)
    posicoes = _ler_limpo("posicoes", raiz)
    cotacoes_atuais = _ler_limpo("cotacoes", raiz)
    eventos = _ler_limpo("eventos", raiz)
    rel = Relatorio(dry_run=dry_run)
    pedidos = pedidos_de_posicoes(posicoes)
    if not pedidos:
        return rel

    manual = manual or {}
    if manual:
        prov_manual = ManualProvider(manual, hoje, hora_agora)
        obtidas, _ = prov_manual.cotar([p for p in pedidos if p.ticker in manual])
        rel.obtidas.extend(obtidas)
        sobras = sorted(set(manual) - {p.ticker for p in pedidos})
        if sobras:
            rel.falhas.append(f"--manual para ticker sem posição: {', '.join(sobras)} (ignorado)")
    restantes = [p for p in pedidos if p.ticker not in manual]

    # Saldo em conta: 1,00 na própria moeda por definição da unidade (não é cotação de mercado).
    saldos = [p for p in restantes if p.classe == "caixa" and sem_cotacao_de_mercado(p)]
    for p in saldos:
        rel.obtidas.append(Cotacao(hoje, "00:00", p.ticker, 1.0, p.moeda, "manual"))
        rel.sinteticas.append(p.ticker)
    restantes = [p for p in restantes if p not in saldos]

    mercado = [p for p in restantes if p.classe != "cambio"]
    fx = [p for p in restantes if p.classe == "cambio"]

    nome_prov = cfg["cotacoes"]["provider"]
    if mercado:
        if nome_prov == "manual" and provider is None:
            rel.falhas.extend(f"{p.ticker}: provider da config é 'manual' — passe --manual {p.ticker}=PRECO "
                              "(ou troque cotacoes.provider para yahoo/brapi)" for p in mercado)
        else:
            prov = provider or criar_provider(nome_prov, buscar=buscar)
            obtidas, falhas = prov.cotar(mercado)
            rel.obtidas.extend(obtidas)
            rel.falhas.extend(falhas)
    if fx:
        nome_fx = provider_cambio(cfg)
        if nome_fx == "manual" and cambio is None:
            rel.falhas.extend(f"{p.ticker}: câmbio da config é 'manual' — passe --manual {p.ticker}=TAXA" for p in fx)
        else:
            prov_fx = cambio or criar_provider(nome_fx, buscar=buscar)
            obtidas, falhas = prov_fx.cotar(fx)
            rel.obtidas.extend(obtidas)
            rel.falhas.extend(falhas)

    ultimas = ultimas_cotacoes(cotacoes_atuais)
    abertas = {e["ticker"] for e in eventos if e["tipo"] == "variacao-anomala" and e["confirmado"] == "nao"}
    for c in rel.obtidas:
        ant = ultimas.get(c.ticker)
        if not ant or ant["preco"] == 0:
            rel.variacoes[c.ticker] = None
            continue
        pct = c.preco / ant["preco"] - 1
        rel.variacoes[c.ticker] = pct
        if abs(pct) > LIMIAR_ANOMALIA:
            rel.anomalias.append(f"{c.ticker}: {ant['preco']:g} ({ant['data']}) -> {c.preco:g} ({pct:+.1%}) "
                                 "— split, grupamento ou ticker trocado? confirme em eventos.csv")
            if c.ticker not in abertas:
                rel.propostas.append({"data": c.data, "ticker": c.ticker, "tipo": "variacao-anomala",
                                      "razao": f"{pct:+.1%} vs {ant['data']} ({ant['preco']:g} -> {c.preco:g})",
                                      "confirmado": "nao"})
                abertas.add(c.ticker)

    if not dry_run and rel.obtidas:
        rel.gravadas = anexar_csv("cotacoes", raiz / "dados" / "cotacoes.csv", [c.como_linha() for c in rel.obtidas])
        if rel.propostas:
            anexar_csv("eventos", raiz / "dados" / "eventos.csv", rel.propostas)
    return rel
