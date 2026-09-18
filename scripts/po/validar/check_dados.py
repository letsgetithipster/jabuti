"""Checa a config, os CSVs canônicos e a coerência entre eles.

Exige a existência das tabelas de TABELAS_DADOS; lê toda tabela de SCHEMAS que estiver no disco.
`dados/ativos.csv` ausente com `dados/posicoes.csv` presente é AVISO, não erro: é workspace criado
antes desta versão, e a classe de cada ticker continua saindo da tabela antiga (po.ativos).

A posição é DERIVADA do ledger (fills + eventos + classe de ativos.csv), a mesma que o ESTADO
publica: não há tabela de posição para cruzar, e o que se confere é o próprio livro. Erros:
conta e moeda da linha × conta; venda acima do saldo; evento confirmado que o ledger não aplica;
fill de ticker sem classe declarada; posição sem cotação, cotação em moeda diferente da posição,
ou o mesmo ticker em mais de uma moeda entre contas (cotacoes.csv só guarda uma vencedora por
ticker, a ambiguidade já é o defeito); `posicoes.csv` antiga declarando ticker sem fill (o
ESTADO publicaria zero). Avisos: cotação anexada fora de ordem; provento sem posição; evento
confirmado sem razão. Vocabulários e formatos de campo são do ler_csv.
"""
from pathlib import Path

from po.ativos import ler_ativos
from po.config import carregar_config, moedas_por_conta
from po.csvs import SCHEMAS, TABELAS_DADOS, ler_csv, ultimas_cotacoes
from po.ledger import posicoes_de_fills
from po.numeros import formatar_canonico

# Derivado do schema, não literal: toda tabela com `conta` E `ticker` (a mensagem do laço usa
# os dois). `posicoes` entra enquanto o arquivo antigo existir no workspace.
TABELAS_COM_CONTA_E_TICKER = [n for n in SCHEMAS if "conta" in SCHEMAS[n] and "ticker" in SCHEMAS[n]]


def checar_dados(raiz: str | Path) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos) sobre vault.config.yaml e dados/ do workspace."""
    raiz = Path(raiz)
    erros, avisos = [], []
    try:
        cfg = carregar_config(raiz)
    except (FileNotFoundError, ValueError) as e:
        return [f"vault.config.yaml: {e}"], []

    motor = str(cfg["caminhos"]["motor"])
    if "__MOTOR__" in motor:
        erros.append(
            "vault.config.yaml: caminhos.motor não foi substituído — rode o criar_workspace de novo")
    else:
        motor_path = Path(motor)
        if not motor_path.is_absolute():
            motor_path = (raiz / motor_path).resolve()
        if not (motor_path / "scripts").is_dir():
            erros.append(
                f"vault.config.yaml: caminhos.motor não aponta para um motor válido: {motor!r}")

    moedas = moedas_por_conta(cfg)

    # Exigir e ler são coisas diferentes. TABELAS_DADOS é o que o motor EXIGE em dados/; o laço
    # LÊ toda tabela de SCHEMAS que estiver no disco: `posicoes.csv` de workspace antigo ainda é
    # lida para acusar o zero silencioso (abaixo). Tabela fora de TABELAS_DADOS que não está no
    # disco simplesmente não é checada (nem erro, nem leitura).
    tabelas, leitura_suja = {}, {}
    for nome in SCHEMAS:
        caminho = raiz / "dados" / f"{nome}.csv"
        if not caminho.exists():
            if nome not in TABELAS_DADOS:
                continue
            if nome == "ativos" and (raiz / "dados" / "posicoes.csv").exists():
                # Workspace criado antes desta versão: a classe de cada ticker está na tabela
                # antiga e o motor a lê de lá. Aviso, não erro — a regra "nenhum beco sem saída"
                # vale para quem já tinha workspace, e o aviso traz o arquivo pronto para colar.
                classes, _, _ = ler_ativos(raiz)
                colar = "; ".join(f"{t},{c}" for t, c in sorted(classes.items())) or "(vazio)"
                avisos.append(
                    "dados/ativos.csv ausente — a classe de cada ticker está sendo lida de "
                    "dados/posicoes.csv (workspace criado antes desta versão). Para fixar, crie "
                    "dados/ativos.csv com a linha de cabeçalho `ticker,classe` e estas linhas: "
                    + colar)
                leitura_suja[nome] = True   # redundante com o default de limpos() (ausente = suja);
                continue                    # fica pela simetria com o ramo de erro abaixo
            # Tabela nova numa versão nova do motor: um workspace antigo não a tem, e "ausente"
            # sozinho não diz o que fazer. O cabeçalho é a resposta inteira.
            erros.append(f"dados/{nome}.csv ausente — crie o arquivo com a linha de cabeçalho: "
                         + ",".join(SCHEMAS[nome]))
            leitura_suja[nome] = True
            continue
        linhas, errs = ler_csv(nome, caminho)
        erros.extend(errs)
        leitura_suja[nome] = bool(errs)
        tabelas[nome] = linhas

    def limpos(*nomes):
        return not any(leitura_suja.get(n, True) for n in nomes)

    posicoes = tabelas.get("posicoes", [])
    fills = tabelas.get("fills", [])
    proventos = tabelas.get("proventos", [])
    cotacoes = tabelas.get("cotacoes", [])
    eventos = tabelas.get("eventos", [])

    # Conta é texto: seguro ler mesmo com erro de formato em outro campo da linha.
    for nome in TABELAS_COM_CONTA_E_TICKER:
        nome_csv = f"{nome}.csv"
        for linha in tabelas.get(nome, []):
            conta = linha.get("conta")
            if conta is None:
                continue
            if conta not in moedas:
                erros.append(f"{nome_csv}: conta {conta!r} não declarada na config")
            elif linha.get("moeda") and linha["moeda"] != moedas[conta]:
                erros.append(f"{nome_csv}: {linha['ticker']} em {linha['moeda']} mas a conta "
                             f"{conta} é {moedas[conta]}")

    # Ledger: a posição derivada de fills + eventos + classe. Só com leitura limpa (contrato do
    # ler_csv). A classe vem de po.ativos (ativos.csv por cima da posicoes.csv antiga, se houver).
    # Linha suja de ativos.csv já foi acusada no laço acima e continua declarando o ticker dela
    # (ler_csv devolve a linha junto com o erro), então "sem classe" aqui é sempre ticker que
    # ninguém declarou: erro de origem, não derivado, e não se esconde atrás de outra linha suja.
    classes, _, _ = ler_ativos(raiz)
    derivadas = []
    if limpos("fills", "eventos"):
        derivadas, errs = posicoes_de_fills(fills, eventos, classes)
        erros.extend(errs)

    # Zero silencioso (F1.6): posição declarada na tabela antiga sem NENHUM fill. Com a posição
    # derivada do ledger, o gerador publica R$ 0,00 com exit 0 para esse workspace (nascido de
    # motor anterior, que aceitava posicoes.csv sem fill com um aviso). ERRO, com a linha que abre
    # a posição no ledger. Check próprio: roda só se a tabela antiga ainda estiver no disco.
    if limpos("posicoes", "fills"):
        com_fill = {(f["ticker"], f["conta"]) for f in fills}
        for p in posicoes:
            if (p["ticker"], p["conta"]) not in com_fill:
                erros.append(f"posicoes.csv: {p['ticker']} ({p['conta']}) sem nenhum fill — a posição "
                             "derivada do ledger é zero e o ESTADO não a veria. Registre um "
                             f"saldo-inicial em fills.csv: AAAA-MM-DD,{p['ticker']},saldo-inicial,"
                             f"{formatar_canonico(p['qty'])},{formatar_canonico(p['pm'])},0,"
                             f"{p['conta']},{p['moeda']}")

    # Cotações: toda posição derivada precisa de ao menos uma, na mesma moeda; append fora de
    # ordem é aviso.
    if limpos("fills", "eventos", "cotacoes"):
        ultimas = ultimas_cotacoes(cotacoes)
        moedas_do_ticker = {}
        for p in derivadas:
            moedas_do_ticker.setdefault(p["ticker"], set()).add(p["moeda"])
        for ticker in sorted(moedas_do_ticker):
            c = ultimas.get(ticker)
            if len(moedas_do_ticker[ticker]) > 1:
                erros.append(f"fills.csv: {ticker} aparece em mais de uma moeda "
                             f"({'/'.join(sorted(moedas_do_ticker[ticker]))}) — cotacoes.csv guarda uma "
                             "cotação vencedora por ticker, então a valoração não saberia qual usar")
                continue
            if c is None:
                erros.append(f"cotacoes.csv: {ticker} sem nenhuma cotação — rode "
                             f"scripts/atualizar_cotacoes.py (ou passe --manual {ticker}=PRECO)")
            elif c["moeda"] not in moedas_do_ticker[ticker]:
                erros.append(f"cotacoes.csv: {ticker} cotado em {c['moeda']} mas a posição está em "
                             f"{'/'.join(sorted(moedas_do_ticker[ticker]))} — a valoração multiplicaria "
                             "moedas diferentes")
        mais_recente = {}
        for i, c in enumerate(cotacoes, start=2):
            ultima = mais_recente.get(c["ticker"])
            if ultima and c["data"] < ultima:
                avisos.append(f"cotacoes.csv:{i}: {c['ticker']} {c['data']} anexada depois de {ultima} — "
                              "fora de ordem (a vencedora continua sendo a de data mais recente)")
            mais_recente[c["ticker"]] = max(ultima or c["data"], c["data"])

    if limpos("fills", "eventos", "proventos"):
        tickers_pos = {p["ticker"] for p in derivadas}
        for i, pr in enumerate(proventos, start=2):
            if pr["ticker"] not in tickers_pos:
                avisos.append(f"proventos.csv:{i}: {pr['ticker']} sem posição no ledger (fills.csv) "
                              "(posição vendida ou ainda não importada?)")

    if limpos("eventos"):
        for i, ev in enumerate(eventos, start=2):
            if ev["confirmado"] == "sim" and ev["tipo"] == "variacao-anomala":
                erros.append(f"eventos.csv:{i}: {ev['ticker']} confirmado como 'variacao-anomala' — "
                             "ao confirmar, troque o tipo pelo evento real (split, grupamento, bonificacao…)")
            if ev["confirmado"] == "sim" and ev["tipo"] in ("split", "grupamento", "bonificacao") and not ev["razao"]:
                avisos.append(f"eventos.csv:{i}: {ev['ticker']} {ev['tipo']} confirmado sem razão "
                              "(ex.: 2:1) — sem ela o livro não aplica o evento ao saldo")
    return erros, avisos
