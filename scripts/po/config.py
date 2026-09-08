"""Leitura e validação do vault.config.yaml de um workspace."""
from pathlib import Path

import yaml

MOEDAS_BASE = {"BRL"}
HARNESSES = {"claude-code", "codex", "cursor", "app-web"}
PROVIDERS_COTACOES = {"yahoo", "manual"}  # Fase 2 adiciona brapi, bcb-sgs


def validar_config(cfg: object) -> list[str]:
    """Retorna lista de erros (vazia = config válida). Nunca levanta: shape ruim vira erro."""
    if not isinstance(cfg, dict):
        return ["vault.config.yaml deve ser um mapeamento YAML (chave: valor)"]
    erros = []
    if cfg.get("versao") != 1:
        erros.append("versao deve ser 1")
    if cfg.get("moeda_base") not in MOEDAS_BASE:
        erros.append(f"moeda_base deve ser uma de {sorted(MOEDAS_BASE)}")
    harness = cfg.get("harness")
    if (not isinstance(harness, list) or not harness
            or not all(isinstance(h, str) for h in harness)
            or not set(harness) <= HARNESSES):
        erros.append(f"harness deve ser subconjunto não-vazio de {sorted(HARNESSES)}")
    cotacoes = cfg.get("cotacoes")
    provider = cotacoes.get("provider") if isinstance(cotacoes, dict) else None
    if provider not in PROVIDERS_COTACOES:
        erros.append(f"cotacoes.provider deve ser um de {sorted(PROVIDERS_COTACOES)}")
    contas = cfg.get("contas")
    if not isinstance(contas, list) or not contas:
        erros.append("declare ao menos uma conta em contas")
    else:
        ids = []
        for i, conta in enumerate(contas, start=1):
            if not isinstance(conta, dict) or not isinstance(conta.get("id"), str) or not conta["id"]:
                erros.append(f"conta #{i} sem id (cada conta é um mapeamento com id)")
            else:
                ids.append(conta["id"])
        if len(ids) != len(set(ids)):
            erros.append("ids de conta duplicados")
    caminhos = cfg.get("caminhos")
    motor = caminhos.get("motor") if isinstance(caminhos, dict) else None
    if not motor:
        erros.append("caminhos.motor ausente (preenchido pelo criar_workspace)")
    return erros


def carregar_config(raiz: str | Path) -> dict:
    """Carrega e valida o vault.config.yaml na raiz do workspace.

    Contrato de erro: FileNotFoundError (arquivo ausente) ou ValueError
    (YAML malformado, shape errado ou validação) — nunca outra exceção.
    """
    caminho = Path(raiz) / "vault.config.yaml"
    if not caminho.exists():
        raise FileNotFoundError(f"vault.config.yaml não encontrado em {raiz}")
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        raise ValueError(
            "vault.config.yaml não é UTF-8 válido — salve o arquivo como UTF-8") from e
    try:
        cfg = yaml.safe_load(texto)
    except yaml.YAMLError as e:
        raise ValueError(f"vault.config.yaml malformado: {e}") from e
    if cfg is None:
        cfg = {}
    erros = validar_config(cfg)
    if erros:
        raise ValueError("config inválida: " + "; ".join(erros))
    return cfg
