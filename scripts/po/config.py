"""Leitura e validação do vault.config.yaml de um workspace."""
from pathlib import Path

import yaml

MOEDAS_BASE = {"BRL"}
HARNESSES = {"claude-code", "codex", "cursor", "app-web"}
PROVIDERS_COTACOES = {"yahoo", "manual"}  # Fase 2 adiciona brapi, bcb-sgs


def validar_config(cfg: dict) -> list[str]:
    """Retorna lista de erros (vazia = config válida)."""
    erros = []
    if cfg.get("versao") != 1:
        erros.append("versao deve ser 1")
    if cfg.get("moeda_base") not in MOEDAS_BASE:
        erros.append(f"moeda_base deve ser uma de {sorted(MOEDAS_BASE)}")
    harness = cfg.get("harness") or []
    if not harness or not set(harness) <= HARNESSES:
        erros.append(f"harness deve ser subconjunto não-vazio de {sorted(HARNESSES)}")
    provider = (cfg.get("cotacoes") or {}).get("provider")
    if provider not in PROVIDERS_COTACOES:
        erros.append(f"cotacoes.provider deve ser um de {sorted(PROVIDERS_COTACOES)}")
    contas = cfg.get("contas") or []
    if not contas:
        erros.append("declare ao menos uma conta em contas:")
    ids = [c.get("id") for c in contas]
    if len(ids) != len(set(ids)):
        erros.append("ids de conta duplicados")
    if not (cfg.get("caminhos") or {}).get("motor"):
        erros.append("caminhos.motor ausente (preenchido pelo criar_workspace)")
    return erros


def carregar_config(raiz) -> dict:
    """Carrega e valida o vault.config.yaml na raiz do workspace. Levanta em erro."""
    caminho = Path(raiz) / "vault.config.yaml"
    if not caminho.exists():
        raise FileNotFoundError(f"vault.config.yaml não encontrado em {raiz}")
    cfg = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    erros = validar_config(cfg)
    if erros:
        raise ValueError("config inválida: " + "; ".join(erros))
    return cfg
