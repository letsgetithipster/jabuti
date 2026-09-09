"""Checa a config, os 6 CSVs canônicos e a coerência entre eles.

v2: conta e moeda da linha × conta; ledger cronológico (qty E pm contra
posicoes.csv; venda acima do saldo); posição sem cotação = ERRO; cotação
anexada fora de ordem = aviso; provento sem posição = aviso; eventos
confirmados coerentes. Vocabulários e formatos de campo são do ler_csv.
"""
from pathlib import Path

from po.config import carregar_config, moedas_por_conta
from po.csvs import SCHEMAS, ler_csv, ultimas_cotacoes
from po.ledger import TOLERANCIA_QTY, calcular_saldos

TOLERANCIA_PM = 0.01


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
        qty_posicao, pm_posicao = {}, {}
        for p in posicoes:
            chave = (p["ticker"], p["conta"])
            if chave in qty_posicao:
                erros.append(
                    f"posicoes.csv: linha duplicada para {p['ticker']} na conta {p['conta']} — "
                    "uma linha por (ticker, conta)")
            else:
                qty_posicao[chave] = p["qty"]
                pm_posicao[chave] = p["pm"]
        saldos, errs = calcular_saldos(fills)
        erros.extend(errs)
        for (ticker, conta), s in sorted(saldos.items()):
            chave = (ticker, conta)
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
            elif abs(s.pm - pm_posicao[chave]) > TOLERANCIA_PM:
                erros.append(
                    f"posicoes.csv: {ticker} ({conta}) pm {pm_posicao[chave]:.2f} "
                    f"difere do recalculado {s.pm:.2f} (ledger de fills)")
        for (ticker, conta) in sorted(qty_posicao):
            if (ticker, conta) not in saldos:
                avisos.append(f"posicoes.csv: {ticker} ({conta}) sem fills — PM não verificável "
                              "(importe posições ou registre um saldo-inicial)")

    # Cotações: toda posição precisa de ao menos uma; append fora de ordem é aviso.
    if limpos("posicoes", "cotacoes"):
        ultimas = ultimas_cotacoes(cotacoes)
        for ticker in sorted({p["ticker"] for p in posicoes}):
            if ticker not in ultimas:
                erros.append(f"cotacoes.csv: {ticker} sem nenhuma cotação — rode "
                             f"scripts/atualizar_cotacoes.py (ou passe --manual {ticker}=PRECO)")
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
