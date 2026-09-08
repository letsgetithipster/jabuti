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

    for linha in posicoes:
        if linha["conta"] not in contas_validas:
            erros.append(f"posicoes.csv: conta {linha['conta']!r} não declarada na config")
    for linha in fills:
        if linha["conta"] not in contas_validas:
            erros.append(f"fills.csv: conta {linha['conta']!r} não declarada na config")

    # Cross-check fills → posições, decisão pinada: só tickers presentes em fills
    # (posição sem fills = importada, permitida). Roda apenas com leitura limpa,
    # pelo contrato do ler_csv (erros != [] → não consumir números).
    if not leitura_suja.get("posicoes") and not leitura_suja.get("fills"):
        qty_posicao = {p["ticker"]: p["qty"] for p in posicoes}
        saldo_fills = defaultdict(float)
        for f in fills:
            saldo_fills[f["ticker"]] += f["qty"] if f["tipo"] == "compra" else -f["qty"]
        for ticker, saldo in sorted(saldo_fills.items()):
            if ticker not in qty_posicao:
                erros.append(f"fills.csv: ticker {ticker} tem fills mas não existe em posicoes.csv")
            elif abs(saldo - qty_posicao[ticker]) > TOLERANCIA_QTY:
                erros.append(
                    f"posicoes.csv: {ticker} qty {qty_posicao[ticker]} difere do saldo dos fills ({saldo})")
    return erros, avisos
