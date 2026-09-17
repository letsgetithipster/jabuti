"""Escrita em dados/ após conciliação: dedupe por multiconjunto contra dados/, abertura de livro
(fill `saldo-inicial`) e linha em ativos.csv para cada posição do documento, log de importação
em logs/importacoes/. Nada aqui roda sem a conciliação ter passado: `gravar` recusa Resultado
com erro.

Posição não é tabela: é o que o ledger deriva de fills + eventos + a classe declarada em
ativos.csv (po.ledger.posicoes_de_fills). O documento de posição da corretora vira, por linha,
UM fill `saldo-inicial` (só para ticker/conta sem NENHUM fill) e UMA linha `ticker,classe` em
ativos.csv (só para ticker ainda não declarado). Reimportar o mesmo documento não grava nada.

Posição do documento para ticker que JÁ tem fill é conferida contra o ledger cortado na data do
documento (po.ingestao.reconciliacao). Se diverge em quantidade, o documento contradiz o livro:
nada é gravado (nem o resto do documento) e `Divergencia` carrega a aritmética e o comando de
cada saída — o mesmo texto que `conferir` imprime. Diferença só de custo com a mesma quantidade
(taxa que a corretora soma ao PM, arredondamento) é nota, não barreira: o livro tem a
procedência, e a foto precisa continuar passando todo mês."""
import datetime
from collections import Counter
from pathlib import Path

from po.ativos import ler_ativos
from po.csvs import anexar_csv, ler_csv
from po.ingestao.artefatos import caminho_datado_livre
from po.ingestao.engine import Resultado
from po.ingestao.reconciliacao import CAVEAT_ACEITAR, Diferenca, explicar, fill_implicito
from po.ledger import Saldo, calcular_saldos, posicoes_de_fills
from po.numeros import formatar_brl, formatar_decimal_brl

REGISTRAR = "python <motor>/scripts/registrar.py ."


class Divergencia(ValueError):
    """O documento contradiz o livro: nada gravado. A mensagem é a explicação inteira, posição a
    posição, com o comando de cada saída. ValueError de propósito: quem já tratava "nada gravado"
    continua tratando; quem quer o código de saída próprio (3, não é erro de execução) distingue."""

class GravacaoParcial(Exception):
    """A gravação morreu no meio do laço de tabelas. Carrega o que chegou a entrar em `dados/` e o
    caminho do log, para que o CLI possa dizer isso em vez de repetir "nada gravado" — que seria
    falso. Não herda de OSError nem de ValueError de propósito: quem trata precisa distinguir
    "nada entrou" de "entrou parte", e herdar faria a guarda genérica engolir o caso."""

    def __init__(self, causa: Exception, gravadas: dict[str, int], log):
        super().__init__(str(causa))
        self.causa, self.gravadas, self.log = causa, gravadas, log


# As tabelas de evento que o documento alimenta. `ativos` não está aqui de propósito: não é
# evento, é a declaração de classe, e entra pela posição do documento (ver `gravar`).
TABELAS = ("fills", "proventos", "eventos")
CHAVES = {
    "proventos": lambda r: (r["data"], r["ticker"], r["tipo"], r["conta"], round(float(r["valor_bruto"]), 2)),
    "fills": lambda r: (r["data"], r["ticker"], r["tipo"], r["conta"], round(float(r["qty"]), 6), round(float(r["preco"]), 4)),
    "eventos": lambda r: (r["data"], r["ticker"], r["tipo"]),
}


def _existentes(raiz: Path) -> dict[str, list[dict]]:
    tabelas = {}
    for nome in TABELAS:
        linhas, erros = ler_csv(nome, raiz / "dados" / f"{nome}.csv")
        if erros:
            raise ValueError(f"dados/{nome}.csv com erros — corrija antes de importar (rode o validador): {erros[0]}")
        tabelas[nome] = linhas
    return tabelas


def _classes(raiz: Path) -> dict[str, str]:
    classes, erros, _ = ler_ativos(raiz)
    if erros:
        raise ValueError(f"dados/ativos.csv com erros — corrija antes de importar (rode o validador): {erros[0]}")
    return classes


def separar(existentes: dict[str, list[dict]], res: Resultado) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """(novos por tabela, duplicadas por tabela).

    MULTICONJUNTO contra o que já está em `dados/`, nunca do documento contra ele mesmo. Duas
    execuções parciais da mesma ordem no mesmo dia, pelo mesmo preço, são dois eventos reais e
    rotineiros em B3 e Schwab; deduplicar o documento contra si mesmo perderia a segunda em
    silêncio, e a conciliação já tinha abençoado as duas."""
    novos, duplicadas = {}, {}
    for nome in TABELAS:
        chave = CHAVES[nome]
        restantes = Counter(chave(e) for e in existentes[nome])
        novos[nome], duplicadas[nome] = [], 0
        for r in res.registros.get(nome, []):
            k = chave(r)
            if restantes[k] > 0:
                restantes[k] -= 1
                duplicadas[nome] += 1
                continue
            novos[nome].append(r)
    return novos, duplicadas


def _consolidadas(res: Resultado) -> list[dict]:
    """Posições do documento com UMA linha por (ticker, conta): qty somada, PM ponderado, data da
    primeira linha. Corretora que quebra a posição por lote não pode virar duas divergências
    contra um ledger que tem uma posição só."""
    lotes: dict[tuple, list[dict]] = {}
    for p in res.registros.get("posicoes", []):
        lotes.setdefault((p["ticker"], p["conta"]), []).append(p)
    saida = []
    for (ticker, conta), ps in lotes.items():
        qty = sum(p["qty"] for p in ps)
        pm = sum(p["qty"] * p["pm"] for p in ps) / qty if len(ps) > 1 else ps[0]["pm"]
        saida.append({"ticker": ticker, "conta": conta, "qty": qty, "pm": pm,
                      "moeda": ps[0]["moeda"], "_data": ps[0]["_data"]})
    return saida


def _com_fills(existentes: dict[str, list[dict]]) -> set[tuple[str, str]]:
    return {(f["ticker"], f["conta"]) for f in existentes["fills"]}


def diferencas(existentes: dict[str, list[dict]], res: Resultado) -> list[tuple[dict, Saldo, Diferenca]]:
    """(posição do documento, saldo do ledger na data dela, diferença), só para ticker/conta que
    já tem fill em dados/ e cuja leitura não é `igual`. Ticker sem fill nenhum é abertura de
    livro, não divergência. Ticker COM fill e saldo zero na data (vendido inteiro antes da foto,
    ou comprado só depois dela) é divergência a partir do zero: a foto afirma uma posição que o
    livro não tem nessa data, e `_aberturas` nunca vai abrir o que já tem fill — sem isto, a
    prévia prometia "abre o livro" e a gravação passava em silêncio com "nada novo".

    A posição do livro é DERIVADA (fills + eventos, cortados na data do documento), nunca lida de
    uma tabela de estado: é o que permite conferir uma foto de 01/08 contra o livro como ele era
    em 01/08, e não como ele está hoje. `calcular_saldos` roda uma vez por posição; com milhares
    de fills e dezenas de posições é irrelevante, e agrupar por data seria otimizar antes de medir.

    ValueError se o ledger já tem erro nomeado: empilhar divergência derivada sobre erro de origem
    esconderia a causa, e a frase certa é a do ledger."""
    saida = []
    com_fills = _com_fills(existentes)
    for p in _consolidadas(res):
        saldos, erros, _suspeitas = calcular_saldos(existentes["fills"], existentes["eventos"],
                                                    ate=p["_data"])
        if erros:
            raise ValueError("dados/ com erro no ledger — nada a conferir (rode o validador): " + erros[0])
        k = (p["ticker"], p["conta"])
        s = saldos.get(k)
        if s is None or s.qty <= 0:
            if k not in com_fills:
                continue
            s = Saldo()
        dif = fill_implicito(s.qty, s.pm, p["qty"], p["pm"])
        if dif.leitura != "igual":
            saida.append((p, s, dif))
    return saida


def _explicar(p: dict, s: Saldo, dif: Diferenca, registrar: str, importar: str | None = None) -> list[str]:
    return explicar(dif, ticker=p["ticker"], conta=p["conta"], data=p["_data"], qty_ledger=s.qty,
                    pm_ledger=s.pm, qty_doc=p["qty"], pm_doc=p["pm"], registrar=registrar,
                    importar=importar)


def divergencias(existentes: dict[str, list[dict]], res: Resultado, registrar: str = REGISTRAR,
                 importar: str | None = None, aceitar_como: str | None = None
                 ) -> tuple[list[str], list[str], list[dict]]:
    """(linhas que BARRAM a gravação, notas que não barram, fills implícitos aceitos). Vazio nas
    três = o documento não contradiz o livro. Barra quem muda a quantidade (compra ou venda que
    o livro não tem); `ajuste-de-custo` é nota.

    `aceitar_como="compra"` (decisão 14 da spec) transforma a leitura `compra` COM preço
    implícito num fill: delta de qty, preço implícito, taxa 0, DATADO NA FOTO. Nunca é default.
    Venda continua barrando (a foto tem PM, não preço de venda), compra com custo que cai também
    (não há preço), e ajuste-de-custo continua nota: a flag não fabrica número."""
    if aceitar_como not in (None, "compra"):
        raise ValueError(f"aceitar_como só aceita 'compra' (recebi {aceitar_como!r}): a foto tem "
                         "preço médio, não preço de venda")
    barram, notas, implicitos = [], [], []
    for p, s, dif in diferencas(existentes, res):
        texto = _explicar(p, s, dif, registrar, importar)
        if dif.leitura == "ajuste-de-custo":
            notas.extend(texto)
        elif aceitar_como == "compra" and dif.leitura == "compra" and dif.preco_implicito is not None:
            implicitos.append({"data": p["_data"], "ticker": p["ticker"], "tipo": "compra",
                               "qty": dif.delta_qty, "preco": dif.preco_implicito, "taxa": 0.0,
                               "conta": p["conta"], "moeda": p["moeda"]})
        elif aceitar_como == "compra" and dif.leitura == "venda":
            barram.extend(texto + ["    --aceitar-como compra não cobre venda: a foto tem preço médio, "
                                   "não preço de venda. Registre a venda com o comando acima."])
        else:
            barram.extend(texto)
    if implicitos:
        # O fill aceito pela foto entra no livro como qualquer outro, e o livro pode recusá-lo:
        # foto anterior ao saldo-inicial do ticker, por exemplo, poria uma compra antes da
        # abertura. Gravar e deixar o validador descobrir seria a gravação que passa e o
        # workspace que quebra. A frase é a do ledger, que é quem sabe o motivo.
        _s, erros, _x = calcular_saldos(existentes["fills"] + implicitos, existentes["eventos"])
        if erros:
            barram.append("  --aceitar-como compra deixaria o livro com erro, então nada foi gravado: "
                          + erros[0] + ". Registre a operação com a data certa (registrar.py compra) "
                          "ou corrija a data do documento.")
    return barram, notas, implicitos


def _aberturas(existentes: dict[str, list[dict]], res: Resultado) -> tuple[list[dict], list[str]]:
    """(aberturas, notas). Decisão 6, spec §2.1: posição do documento para ticker/conta sem NENHUM
    fill vira UM fill `saldo-inicial` na data do documento. A condição é "sem fill", não "posição
    nova": se uma gravação anterior morreu no meio, a rodada seguinte completa a abertura que
    faltou. Ticker que já tem fill de verdade (em dados/ ou no próprio documento) nunca ganha
    abertura sintética.

    O ledger abre cada (ticker, conta) uma vez só. Documento que traz a mesma posição em mais de
    uma linha (quebra por lote ou por agente de custódia, como B3 e Schwab exportam) vira uma
    abertura consolidada: qty somada, preço = PM ponderado, data da primeira linha. A soma é
    aritmética sobre as linhas que a conciliação do documento já provou, e a consolidação fica
    nomeada em `notas` para o log — nunca acontece em silêncio."""
    com_fills = {(f["ticker"], f["conta"]) for f in existentes["fills"]}
    com_fills |= {(f["ticker"], f["conta"]) for f in res.registros.get("fills", [])}
    lotes: dict[tuple, list[dict]] = {}
    for p in res.registros.get("posicoes", []):
        if (p["ticker"], p["conta"]) not in com_fills:
            lotes.setdefault((p["ticker"], p["conta"]), []).append(p)
    aberturas, notas = [], []
    for (ticker, conta), ps in lotes.items():
        qty = sum(p["qty"] for p in ps)
        preco = sum(p["qty"] * p["pm"] for p in ps) / qty if len(ps) > 1 else ps[0]["pm"]
        if len(ps) > 1:
            notas.append(f"{ticker} ({conta}): {len(ps)} lotes consolidados numa abertura")
        aberturas.append({"data": ps[0]["_data"], "ticker": ticker, "tipo": "saldo-inicial", "qty": qty,
                          "preco": preco, "taxa": 0.0, "conta": conta, "moeda": ps[0]["moeda"]})
    return aberturas, notas


def _declaracoes(classes: dict[str, str], res: Resultado) -> list[dict]:
    """Linha `ticker,classe` para cada ticker do documento ainda sem declaração. Ticker já
    declarado fica como está, mesmo que o documento traga outra classe: ativos.csv é a
    declaração da pessoa (decisão 10), e o documento não a sobrescreve."""
    novas, vistos = [], set(classes)
    for p in res.registros.get("posicoes", []):
        if p["ticker"] in vistos:
            continue
        vistos.add(p["ticker"])
        novas.append({"ticker": p["ticker"], "classe": p["classe"]})
    return novas


def gravar(raiz: str | Path, res: Resultado, *, mapeamento: str, arquivo: str, conciliacao: str,
           conta: str, hoje: datetime.date | None = None, registrar: str = REGISTRAR,
           importar: str | None = None, aceitar_como: str | None = None) -> dict:
    """Grava os registros novos e o log. Retorna {'gravadas': {...}, 'duplicadas': {...},
    'aberturas': N, 'implicitos': N, 'log': Path}. `gravadas` cobre as tabelas de evento e
    `ativos`; `aberturas` é quantos dos fills gravados são `saldo-inicial` sintetizados a partir
    de posição; `implicitos` é quantos são fills aceitos pela foto (`aceitar_como="compra"`, ver
    `divergencias`), e o log carrega o caveat deles.

    ValueError em dados/ sujo ou em Resultado com erro, e `Divergencia` (também ValueError) se uma
    posição do documento contradiz o ledger na data dela: nada é gravado nesses casos, e a
    checagem acontece antes de qualquer escrita. `registrar` é o prefixo do comando que a
    explicação da divergência cita. `GravacaoParcial` se o laço de tabelas morrer no meio
    (arquivo travado no Excel, disco cheio): aí parte entrou, e a exceção diz qual parte e onde
    está o log. É a única saída de erro em que dados/ mudou."""
    raiz = Path(raiz)
    hoje = hoje or datetime.date.today()
    if res.erros:   # o contrato do módulo é este; sem a guarda ele valia só por disciplina
        raise ValueError("a ingestão reportou erro — nada gravado: " + res.erros[0])
    existentes = _existentes(raiz)
    classes = _classes(raiz)
    novos, duplicadas = separar(existentes, res)
    barram, _notas, implicitos = divergencias(existentes, res, registrar, importar, aceitar_como)
    if barram:
        raise Divergencia("o documento não bate com o seu livro — nada gravado:\n" + "\n".join(barram))
    aberturas, notas = _aberturas(existentes, res)
    novos["fills"] = novos["fills"] + aberturas + implicitos
    novos["ativos"] = _declaracoes(classes, res)
    duplicadas["ativos"] = 0
    gravadas = {t: 0 for t in (*TABELAS, "ativos")}
    try:
        # ativos antes dos fills: se a rodada morrer no meio, o fill que entrou já tem classe e
        # o gerador de ESTADO não para em "ticker sem classe declarada" enquanto a pessoa recupera
        for nome in ("ativos", *TABELAS):
            if novos[nome]:
                gravadas[nome] = anexar_csv(nome, raiz / "dados" / f"{nome}.csv", novos[nome])
    except (OSError, ValueError) as e:
        # A rodada que mais precisa de registro é justamente a que morreu no meio.
        try:
            entrou = bool(gravadas["fills"])
            log = _escrever_log(raiz, hoje, mapeamento, arquivo, conciliacao, conta, res, gravadas,
                                duplicadas, len(aberturas) if entrou else 0, notas,
                                len(implicitos) if entrou else 0, falha=str(e))
        except OSError:
            log = None   # logs/ também travado: a causa original vale mais que o registro dela
        raise GravacaoParcial(e, gravadas, log) from e
    log = _escrever_log(raiz, hoje, mapeamento, arquivo, conciliacao, conta, res, gravadas, duplicadas,
                        len(aberturas), notas, len(implicitos))
    return {"gravadas": gravadas, "duplicadas": duplicadas, "aberturas": len(aberturas),
            "implicitos": len(implicitos), "log": log}


def _escrever_log(raiz, hoje, mapeamento, arquivo, conciliacao, conta, res, gravadas, duplicadas,
                  aberturas: int, notas: list[str], implicitos: int = 0, falha: str = "") -> Path:
    caminho = caminho_datado_livre(raiz / "logs" / "importacoes",
                                   f"{hoje.isoformat()}-{mapeamento}", ".md")
    motivos = {}
    for _, motivo in res.ignoradas:
        motivos[motivo] = motivos.get(motivo, 0) + 1
    tabela = "\n".join(f"| {t} | {gravadas[t]} | {duplicadas.get(t, 0)} |" for t in gravadas)
    ignoradas = "; ".join(f"{m}: {c}" for m, c in motivos.items()) or "nenhuma"
    # Regra morta neste documento é sintoma fraco (mapa real tem uma regra por tipo de evento e
    # um mês aciona duas ou três), então não vira aviso gritado em toda rodada. Mas some se não
    # ficar em lugar nenhum: o log é o registro durável onde ela pode ser auditada depois.
    acertos = "; ".join(f"regra {i}: {c}" for i, c in sorted(res.acertos.items())) or "nenhuma regra"
    sem_uso = [i for i, c in sorted(res.acertos.items()) if c == 0]
    caminho.write_text(
        "---\n"
        f"tipo: log-importacao\ndata: {hoje.isoformat()}\nconta: {conta}\nmapeamento: {mapeamento}\n"
        f"arquivo: \"{arquivo}\"\nconciliacao: \"{conciliacao}\"\n"
        "---\n\n"
        f"# Importação {hoje.isoformat()} — {mapeamento}\n\n"
        f"Arquivo `{arquivo}` na conta `{conta}`: {res.linhas_lidas} linha(s) lidas, "
        f"{res.classificadas} classificadas, {len(res.ignoradas)} ignoradas.\n\n"
        "| Tabela | Gravadas | Duplicadas (puladas) |\n|---|---|---|\n" + tabela + "\n\n"
        # Abertura de livro declara o custo, não a data real de aquisição: fica registrado
        # quantas entraram, para a apuração fiscal saber que lotes estão mudos sobre a data.
        f"Aberturas (saldo-inicial): {aberturas}" + ("; " + "; ".join(notas) if notas else "") + "\n\n"
        # O fill aceito pela foto tem a data da foto, não da operação: quem apurar IR precisa
        # saber que esses lotes estão mudos sobre o dia. Fica no registro durável, não só no eco.
        f"Fills implícitos aceitos pela foto (--aceitar-como compra): {implicitos}"
        + (f" — {CAVEAT_ACEITAR}" if implicitos else "") + "\n\n"
        f"Ignoradas por motivo: {ignoradas}\n\n"
        f"Linhas ignoradas: {[n for n, _ in res.ignoradas] or 'nenhuma'}\n\n"
        f"Acertos por regra de `linhas`: {acertos}\n\n"
        f"Regras que nunca casaram: {sem_uso or 'nenhuma'}\n\n"
        f"Conciliação: {conciliacao}\n"
        + (f"\n**A gravação falhou no meio**: {falha}\n\nO que está na tabela acima chegou a ser "
           "gravado; o resto não. Rode de novo depois de resolver — a importação é idempotente.\n"
           if falha else ""),
        encoding="utf-8", newline="\n")
    return caminho


def conferir(raiz: str | Path, res: Resultado, registrar: str = REGISTRAR,
             importar: str | None = None) -> tuple[list[str], bool, int]:
    """Compara o documento com dados/ sem gravar. (linhas, houve divergência, registros novos).

    A posição de dados/ é a DERIVADA do ledger (fills + eventos), cortada na data de cada posição
    do documento: não existe tabela de posição para comparar, e uma foto de 01/08 é conferida
    contra o livro de 01/08. Na divergência, as linhas são a aritmética e o comando de cada saída
    (po.ingestao.reconciliacao.explicar), o MESMO texto com que `gravar` recusa. Usa o MESMO
    `separar`, `_aberturas` e `_declaracoes` da gravação, para que a prévia não possa prometer um
    número que a gravação não vai cumprir. O terceiro valor existe porque "sem divergência" e
    "nada a fazer" são coisas diferentes: um documento pode bater com dados/ em tudo que já
    existe e ainda trazer lançamento novo para gravar."""
    raiz = Path(raiz)
    if res.erros:   # mesmo contrato de `gravar`: prévia sobre resultado que a gravação recusaria mente
        raise ValueError("a ingestão reportou erro — nada a conferir: " + res.erros[0])
    existentes = _existentes(raiz)
    classes = _classes(raiz)
    novos, duplicadas = separar(existentes, res)
    _derivadas, erros = posicoes_de_fills(existentes["fills"], existentes["eventos"], classes)
    if erros:
        raise ValueError("dados/ com erro no ledger — nada a conferir (rode o validador): " + erros[0])
    novos["fills"] = novos["fills"] + _aberturas(existentes, res)[0]
    novos["ativos"] = _declaracoes(classes, res)
    linhas, divergiu = [], False
    explicadas = {(p["ticker"], p["conta"]): (dif, _explicar(p, s, dif, registrar, importar))
                  for p, s, dif in diferencas(existentes, res)}
    contas_do_documento = {p["conta"] for p in res.registros["posicoes"]}
    com_fills = _com_fills(existentes)
    no_documento = set()
    for p in _consolidadas(res):
        k = (p["ticker"], p["conta"])
        no_documento.add(k)
        saldos, _e, _s = calcular_saldos(existentes["fills"], existentes["eventos"], ate=p["_data"])
        s = saldos.get(k)
        if (s is None or s.qty <= 0) and k not in com_fills:
            # o mesmo critério de `_aberturas`: só abre o livro quem não tem fill nenhum
            linhas.append(f"  {p['ticker']} ({p['conta']}): NOVA no documento — "
                          f"{formatar_decimal_brl(p['qty'])} @ {formatar_brl(p['pm'])}, "
                          "abre o livro como saldo-inicial")
            continue
        if k not in explicadas:
            linhas.append(f"  {p['ticker']} ({p['conta']}): OK — "
                          f"{formatar_decimal_brl(p['qty'])} @ {formatar_brl(p['pm'])}")
            continue
        dif, texto = explicadas[k]
        linhas.extend(texto)
        divergiu = divergiu or dif.leitura != "ajuste-de-custo"
    if res.registros["posicoes"]:
        data_doc = max(p["_data"] for p in res.registros["posicoes"])
        saldos, _e, _s = calcular_saldos(existentes["fills"], existentes["eventos"], ate=data_doc)
        for (ticker, conta), s in sorted(saldos.items()):
            # só as contas que ESTE documento cobre: posição de outra corretora não está faltando
            if s.qty > 0 and conta in contas_do_documento and (ticker, conta) not in no_documento:
                linhas.append(f"  {ticker} ({conta}): {formatar_decimal_brl(s.qty)} @ "
                              f"{formatar_brl(s.pm)} no livro e ausente do documento — se você "
                              f"zerou a posição, registre a venda: {registrar} venda {ticker} "
                              f"{formatar_decimal_brl(s.qty)} <preco-de-venda> --data <data-da-venda>")
                divergiu = True
    for nome in TABELAS:
        if res.registros[nome]:
            linhas.append(f"  {nome}: {len(novos[nome])} nova(s), {duplicadas[nome]} já presente(s)")
    if not linhas:
        linhas.append("  nada a comparar: o documento não trouxe posição nem lançamento")
    return linhas, divergiu, sum(len(v) for v in novos.values())
