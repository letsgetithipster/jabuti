"""Checa a config, os 6 CSVs canônicos e a coerência entre eles."""
from collections import defaultdict
from pathlib import Path

from po.config import carregar_config
from po.csvs import SCHEMAS, ler_csv

TOLERANCIA_QTY = 1e-6


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

    contas_validas = {c["id"] for c in cfg["contas"]}

    # leitura_suja/tabelas cobrem as 6; só posicoes/fills têm checks hoje (cotações/proventos: check_dados v2)
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

    posicoes = tabelas.get("posicoes", [])
    fills = tabelas.get("fills", [])

    # Conta é campo texto: seguro ler mesmo com erro de formato em outro campo.
    # Linha capenga (conta None) já foi apontada pelo ler_csv — pula sem duplicar ruído.
    for nome_csv, linhas in (("posicoes.csv", posicoes), ("fills.csv", fills)):
        for linha in linhas:
            conta = linha["conta"]
            if conta is not None and conta not in contas_validas:
                erros.append(f"{nome_csv}: conta {conta!r} não declarada na config")

    # Cross-check fills → posições por (ticker, conta) — pin emendado em review:
    # posição sem fills = importada, permitida; duplicata de (ticker, conta) = erro.
    # Roda apenas com leitura limpa (contrato do ler_csv).
    if not leitura_suja.get("posicoes") and not leitura_suja.get("fills"):
        qty_posicao = {}
        for p in posicoes:
            chave = (p["ticker"], p["conta"])
            if chave in qty_posicao:
                erros.append(
                    f"posicoes.csv: linha duplicada para {p['ticker']} na conta {p['conta']} — "
                    "uma linha por (ticker, conta)")
            else:
                qty_posicao[chave] = p["qty"]
        saldo_fills = defaultdict(float)
        for f in fills:
            delta = f["qty"] if f["tipo"] == "compra" else -f["qty"]
            saldo_fills[(f["ticker"], f["conta"])] += delta
        for (ticker, conta), saldo in sorted(saldo_fills.items()):
            if (ticker, conta) not in qty_posicao:
                erros.append(
                    f"fills.csv: {ticker} tem fills na conta {conta} mas não existe em posicoes.csv")
            elif abs(saldo - qty_posicao[(ticker, conta)]) > TOLERANCIA_QTY:
                erros.append(
                    f"posicoes.csv: {ticker} ({conta}) qty {qty_posicao[(ticker, conta)]} "
                    f"difere do saldo dos fills ({saldo})")
    return erros, avisos
