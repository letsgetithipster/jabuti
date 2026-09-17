"""Orquestração do cotar: carteira derivada do ledger → pedidos → providers → append
em cotacoes.csv.

Regras: sem rede, SemRede sobe e nada é gravado; cada cotação carrega fonte, data e hora;
variação > 30% contra a última cotação vencedora grava a cotação (é o preço real) E propõe
uma linha em eventos.csv (tipo variacao-anomala, confirmado nao) sem duplicar proposta aberta.
Saldo em conta (classe caixa sem código da B3) vale 1,00 na própria moeda por definição da
unidade — não é preço de mercado inventado, é a identidade que o encoding qty×pm já assume, do
mesmo jeito que a conversão BRL→BRL é 1,0 sem consultar provider.
Renda fixa (rf-br) NÃO ganha esse tratamento: o valor dela muda e exige --manual.

Se a cotação foi gravada mas a proposta de anomalia não (arquivo travado por Excel/OneDrive,
por exemplo), perder a proposta em silêncio é pior que não gravar nada: o preço ruim vira a
base da próxima comparação e a anomalia desaparece para sempre. Por isso a escrita de
eventos.csv é isolada: falha ali vira `Relatorio.propostas_nao_gravadas`, nunca traceback.
"""
import datetime
from dataclasses import dataclass, field
from pathlib import Path

from po.ativos import ler_ativos
from po.config import carregar_config, provider_cambio
from po.cotacoes.providers import criar_provider
from po.cotacoes.providers.manual import ManualProvider
from po.cotacoes.tipos import Cotacao, pedidos_de_ativos, sem_cotacao_de_mercado
from po.csvs import anexar_csv, ler_csv, ultimas_cotacoes
from po.ledger import posicoes_de_fills
from po.numeros import formatar_brl, formatar_canonico

LIMIAR_ANOMALIA = 0.30


@dataclass
class Relatorio:
    obtidas: list[Cotacao] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)
    variacoes: dict[str, float | None] = field(default_factory=dict)  # ticker -> fração vs última (None = primeira)
    anomalias: list[str] = field(default_factory=list)
    propostas: list[dict] = field(default_factory=list)                # linhas propostas em eventos.csv
    propostas_nao_gravadas: tuple[str, list[dict]] | None = None       # (motivo, linhas) — cole à mão
    sinteticas: list[str] = field(default_factory=list)                # tickers precificados por definição (saldo)
    ja_atualizadas: list[str] = field(default_factory=list)            # já tinham cotação de hoje: nada a buscar
    pedidos: int = 0                                                   # quantos ativos a carteira pediu
    gravadas: int = 0
    dry_run: bool = False
    hoje: str = ""


def _ler_limpo(nome: str, raiz: Path) -> list[dict]:
    linhas, erros = ler_csv(nome, raiz / "dados" / f"{nome}.csv")
    if erros:
        raise ValueError(f"dados/{nome}.csv com erros — corrija antes (rode o validador): {erros[0]}")
    return linhas


def _checar_moeda_unica(posicoes: list[dict]) -> None:
    """cotacoes.csv guarda uma cotação vencedora por ticker (ver ultimas_cotacoes). Um ticker em
    duas moedas faria uma sobrescrever a outra em rel.variacoes e, na próxima rodada, compararia
    preço numa moeda contra base na outra — falsa anomalia de centenas de %. checar_dados já
    barra isso como ERRO; barrar aqui também evita que a rodada chegue a gravar o resultado."""
    moedas_do_ticker = {}
    for p in posicoes:
        moedas_do_ticker.setdefault(p["ticker"], set()).add(p["moeda"])
    ambiguos = sorted(t for t, m in moedas_do_ticker.items() if len(m) > 1)
    if ambiguos:
        raise ValueError(f"fills.csv: {', '.join(ambiguos)} em mais de uma moeda — cotacoes.csv guarda "
                         "uma cotação vencedora por ticker; corrija antes (rode o validador)")


def atualizar(raiz: str | Path, *, manual: dict[str, float] | None = None, dry_run: bool = False,
              agora: datetime.datetime | None = None, buscar=None, provider=None, cambio=None) -> Relatorio:
    """provider/cambio: instâncias prontas (injeção em teste); default vem da config via criar_provider."""
    raiz = Path(raiz)
    agora = agora or datetime.datetime.now()
    hoje, hora_agora = agora.strftime("%Y-%m-%d"), agora.strftime("%H:%M")
    cfg = carregar_config(raiz)
    eventos = _ler_limpo("eventos", raiz)
    # O universo a cotar é a carteira DERIVADA (fills + eventos + classe de ativos.csv), a mesma
    # que carteira.valorar lê. Ticker que entrou só por fill é cotável pelo comando que o próprio
    # gerar_estado manda rodar; antes a fonte era posicoes.csv e o laço fechava em beco.
    classes, erros_ativos, _ = ler_ativos(raiz)
    if erros_ativos:
        raise ValueError(f"a declaração de classes tem erro — corrija antes (rode o validador): "
                         f"{erros_ativos[0]}")
    posicoes, erros_pos = posicoes_de_fills(_ler_limpo("fills", raiz), eventos, classes)
    if erros_pos:
        raise ValueError(erros_pos[0])
    _checar_moeda_unica(posicoes)
    cotacoes_atuais = _ler_limpo("cotacoes", raiz)
    rel = Relatorio(dry_run=dry_run, hoje=hoje)
    pedidos = pedidos_de_ativos(posicoes)
    rel.pedidos = len(pedidos)
    # Sem retorno antecipado quando não há pedido: --manual para ticker sem fill tem que virar
    # FALHA nomeada, não descarte silencioso com exit 0.
    ultimas = ultimas_cotacoes(cotacoes_atuais)

    manual = manual or {}
    if manual:
        prov_manual = ManualProvider(manual, hoje, hora_agora)
        obtidas, _ = prov_manual.cotar([p for p in pedidos if p.ticker in manual])
        rel.obtidas.extend(obtidas)
        sobras = sorted(set(manual) - {p.ticker for p in pedidos})
        if sobras:
            rel.falhas.append(f"--manual para ticker sem posição no ledger (nenhum fill em fills.csv): "
                              f"{', '.join(sobras)} (ignorado)")
    restantes = [p for p in pedidos if p.ticker not in manual]

    # Saldo em conta: 1,00 na própria moeda por definição da unidade (não é cotação de mercado).
    # Fonte "definicao": distingue do que o usuário colou (--manual) mesmo quando o número é o mesmo.
    saldos = [p for p in restantes if p.classe == "caixa" and sem_cotacao_de_mercado(p)]
    for p in saldos:
        existente = ultimas.get(p.ticker)
        ja_sintetizado_hoje = (existente and existente["data"] == hoje
                               and existente["fonte"] == "definicao" and existente["preco"] == 1.0)
        if ja_sintetizado_hoje:
            rel.ja_atualizadas.append(p.ticker)   # nada a buscar, mas não é silêncio
            continue   # append-only: não empilha uma linha idêntica por rodada
        rel.obtidas.append(Cotacao(hoje, "00:00", p.ticker, 1.0, p.moeda, "definicao"))
        rel.sinteticas.append(p.ticker)
    # Seguro comparar Pedido por igualdade aqui: pedidos_de_ativos dedupa por (ticker, moeda),
    # então dois Pedidos nunca são iguais por valor a menos que sejam o mesmo pedido.
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

    abertas = {e["ticker"] for e in eventos if e["tipo"] == "variacao-anomala" and e["confirmado"] == "nao"}
    for c in rel.obtidas:
        ant = ultimas.get(c.ticker)
        # `preco == 0` é inalcançável pelo arquivo desde que validar_linha passou a recusá-lo;
        # fica como defesa: divisão por zero aqui viraria variação de +infinito e falsa anomalia.
        if not ant or ant["preco"] == 0:
            rel.variacoes[c.ticker] = None
            continue
        pct = c.preco / ant["preco"] - 1
        rel.variacoes[c.ticker] = pct
        if abs(pct) > LIMIAR_ANOMALIA:
            pct_txt = f"{formatar_brl(pct * 100)}%"
            ant_txt, novo_txt = formatar_canonico(ant["preco"]), formatar_canonico(c.preco)
            ja_aberta = c.ticker in abertas
            sufixo = " (já existe proposta aberta em eventos.csv)" if ja_aberta else ""
            rel.anomalias.append(f"{c.ticker}: {ant_txt} ({ant['data']}) -> {novo_txt} ({pct_txt}) "
                                 f"— split, grupamento ou ticker trocado? confirme em eventos.csv{sufixo}")
            if not ja_aberta:
                rel.propostas.append({"data": c.data, "ticker": c.ticker, "tipo": "variacao-anomala",
                                      "razao": f"{pct_txt} vs {ant['data']} ({ant_txt} -> {novo_txt})",
                                      "confirmado": "nao"})
                abertas.add(c.ticker)

    if not dry_run and rel.obtidas:
        # Se ESTA falhar, nada foi escrito e a exceção sobe: o CLI declara e ninguém perde nada.
        rel.gravadas = anexar_csv("cotacoes", raiz / "dados" / "cotacoes.csv", [c.como_linha() for c in rel.obtidas])
        if rel.propostas:
            try:   # o preço já está no disco: perder a proposta em silêncio é pior que gravar nada
                anexar_csv("eventos", raiz / "dados" / "eventos.csv", rel.propostas)
            except (OSError, ValueError) as e:
                rel.propostas_nao_gravadas = (str(e), rel.propostas)
    return rel
