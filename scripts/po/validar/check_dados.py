"""Checa a config, os 6 CSVs canônicos e a coerência entre eles.

v2: conta e moeda da linha × conta; ledger cronológico (qty E pm contra
posicoes.csv; venda acima do saldo; abertura única via saldo-inicial); quando
o ledger já aponta erro numa chave (venda sem saldo, duplicata em
posicoes.csv, abertura inválida), a comparação de qty/pm daquela chave fica
suspensa — não soma erro derivado em cima de erro de origem; posição sem
cotação, cotação em moeda diferente da posição, ou o mesmo ticker em mais de
uma moeda entre contas (cotacoes.csv só guarda uma vencedora por ticker, a
ambiguidade já é o defeito), = ERRO; cotação anexada fora de ordem = aviso;
provento sem posição = aviso; eventos confirmados coerentes. Tolerância de PM
combina piso absoluto (BRL), teto relativo ao próprio PM (protege ativo de
fração de centavo) e piso relativo (domina em PM alto, ex. cripto).
Vocabulários e formatos de campo são do ler_csv.
"""
from pathlib import Path

from po.config import carregar_config, moedas_por_conta
from po.csvs import SCHEMAS, ler_csv, ultimas_cotacoes
from po.ledger import TOLERANCIA_QTY, calcular_saldos

TOLERANCIA_PM = 0.01           # piso absoluto em BRL, limitado a 5% do PM (ver abaixo)
TOLERANCIA_PM_RELATIVA = 1e-7  # domina acima de PM 100.000 (o cruzamento é 0,01 / 1e-7)
# Por que estes números: o piso absorve PM de corretora arredondado a 2 casas (erro ≤ 0,005);
# o termo relativo absorve o mesmo erro em PM alto (0,03 em PM de 300 mil) e deixa nove ordens
# de grandeza de folga sobre o ruído de float acumulado; o teto de 5% impede que o piso engula
# o valor inteiro em ativo de fração de centavo (cripto, penny), onde 1 centavo é 100% do PM.


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

    tabelas, leitura_suja = {}, {}
    for nome in SCHEMAS:
        caminho = raiz / "dados" / f"{nome}.csv"
        if not caminho.exists():
            erros.append(f"dados/{nome}.csv ausente")
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
    for nome_csv, linhas in (("posicoes.csv", posicoes), ("fills.csv", fills), ("proventos.csv", proventos)):
        for linha in linhas:
            conta = linha.get("conta")
            if conta is None:
                continue
            if conta not in moedas:
                erros.append(f"{nome_csv}: conta {conta!r} não declarada na config")
            elif linha.get("moeda") and linha["moeda"] != moedas[conta]:
                erros.append(f"{nome_csv}: {linha['ticker']} em {linha['moeda']} mas a conta "
                             f"{conta} é {moedas[conta]}")

    # Ledger: fills → qty e PM por (ticker, conta). Só com leitura limpa (contrato do ler_csv).
    if limpos("posicoes", "fills"):
        qty_posicao, pm_posicao, duplicadas = {}, {}, set()
        for p in posicoes:
            chave = (p["ticker"], p["conta"])
            if chave in qty_posicao:
                erros.append(
                    f"posicoes.csv: linha duplicada para {p['ticker']} na conta {p['conta']} — "
                    "uma linha por (ticker, conta)")
                duplicadas.add(chave)
            else:
                qty_posicao[chave] = p["qty"]
                pm_posicao[chave] = p["pm"]
        saldos, errs, suspeitas = calcular_saldos(fills)
        erros.extend(errs)
        suspensas = suspeitas | duplicadas   # já há erro na origem: não somar erro derivado
        for (ticker, conta), s in sorted(saldos.items()):
            chave = (ticker, conta)
            if chave in suspensas:
                continue
            if s.qty <= TOLERANCIA_QTY:
                if chave in qty_posicao:
                    erros.append(f"posicoes.csv: {ticker} ({conta}) tem qty {qty_posicao[chave]:g} "
                                 "mas o ledger de fills zerou a posição")
                continue
            if chave not in qty_posicao:
                erros.append(
                    f"fills.csv: {ticker} tem fills na conta {conta} mas não existe em posicoes.csv")
            elif abs(s.qty - qty_posicao[chave]) > TOLERANCIA_QTY:
                erros.append(
                    f"posicoes.csv: {ticker} ({conta}) qty {qty_posicao[chave]:g} "
                    f"difere do saldo dos fills ({s.qty:g})")
            else:
                tolerancia = max(min(TOLERANCIA_PM, abs(pm_posicao[chave]) * 0.05),
                                 abs(pm_posicao[chave]) * TOLERANCIA_PM_RELATIVA)
                if abs(s.pm - pm_posicao[chave]) > tolerancia:
                    erros.append(
                        f"posicoes.csv: {ticker} ({conta}) pm {pm_posicao[chave]:g} "
                        f"difere do recalculado {s.pm:g} (ledger de fills)")
        for chave in sorted(qty_posicao):
            if chave not in saldos and chave not in suspensas:
                avisos.append(f"posicoes.csv: {chave[0]} ({chave[1]}) sem fills — PM não verificável "
                              "(importe posições ou registre um saldo-inicial)")

    # Cotações: toda posição precisa de ao menos uma, na mesma moeda; append fora de ordem é aviso.
    if limpos("posicoes", "cotacoes"):
        ultimas = ultimas_cotacoes(cotacoes)
        moedas_do_ticker = {}
        for p in posicoes:
            moedas_do_ticker.setdefault(p["ticker"], set()).add(p["moeda"])
        for ticker in sorted(moedas_do_ticker):
            c = ultimas.get(ticker)
            if len(moedas_do_ticker[ticker]) > 1:
                erros.append(f"posicoes.csv: {ticker} aparece em mais de uma moeda "
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

    if limpos("posicoes", "proventos"):
        tickers_pos = {p["ticker"] for p in posicoes}
        for i, pr in enumerate(proventos, start=2):
            if pr["ticker"] not in tickers_pos:
                avisos.append(f"proventos.csv:{i}: {pr['ticker']} sem posição em posicoes.csv "
                              "(posição vendida ou ainda não importada?)")

    if limpos("eventos"):
        for i, ev in enumerate(eventos, start=2):
            if ev["confirmado"] == "sim" and ev["tipo"] == "variacao-anomala":
                erros.append(f"eventos.csv:{i}: {ev['ticker']} confirmado como 'variacao-anomala' — "
                             "ao confirmar, troque o tipo pelo evento real (split, grupamento, bonificacao…)")
            if ev["confirmado"] == "sim" and ev["tipo"] in ("split", "grupamento", "bonificacao") and not ev["razao"]:
                avisos.append(f"eventos.csv:{i}: {ev['ticker']} {ev['tipo']} confirmado sem razão "
                              "(ex.: 2:1) — o preparar-ir precisa dela")
    return erros, avisos
