"""Leitura e validação do vault.config.yaml de um workspace."""
from fnmatch import fnmatchcase
from pathlib import Path

import yaml

from po.csvs import CLASSES, MOEDAS, em_vocabulario

MOEDAS_BASE = {"BRL"}
HARNESSES = {"claude-code", "codex", "cursor", "app-web"}
NOMES_PADRAO = {"casa": "minha casa de gestão", "usuario": "o investidor", "coordenador": "Otávio"}
PROVIDERS_COTACOES = {"yahoo", "brapi", "manual"}
PROVIDERS_CAMBIO = {"bcb-sgs", "yahoo", "manual"}
CAMBIO_PADRAO = "bcb-sgs"
PLANILHAS_PADRAO = "planilhas"

# Instalação no lugar: a pasta clonada do jabuti é a pasta da pessoa, e o remoto dela é o jabuti
# público. Estes são os caminhos pessoais na raiz, todos no .gitignore do motor; o
# check_publicacao confere que nenhum está rastreado e que todos estão ignorados. Diretório
# termina em "/"; o resto é arquivo ou padrão fnmatch.
CAMINHOS_PESSOAIS = ("vault.config.yaml", "dados/", "politica/", "estado/", "logs/", "inbox/",
                     "planilhas/", "teses/", "watchlist/", "CLAUDE.local.md", ".claude/rules/",
                     ".claude/skills/", "mapeamentos/meu-*.yaml")
# Arquivos do motor que moram dentro de um caminho pessoal. Hoje só o marcador que mantém
# .claude/skills/ no clone: sem a pasta ao abrir a sessão, o Claude Code não vê as skills que o
# /jabuti-init instala no meio dela (primeiro uso real, 18/09/2026).
MARCADORES_DO_MOTOR = (".claude/skills/.gitkeep",)


def e_pessoal(rel: str) -> bool:
    """True se o caminho relativo à raiz (com `/`) é de um dos CAMINHOS_PESSOAIS."""
    rel = rel.replace("\\", "/").lstrip("/")
    if rel in MARCADORES_DO_MOTOR:
        return False
    for padrao in CAMINHOS_PESSOAIS:
        if padrao.endswith("/"):
            if rel.startswith(padrao) or rel == padrao.rstrip("/"):
                return True
        elif fnmatchcase(rel, padrao):
            return True
    return False


def raiz_e_motor(raiz: str | Path) -> bool:
    """True se a raiz é o próprio motor: a instalação no lugar, em que a pasta clonada é a da
    pessoa (ou o repositório do motor sem instalação, que não tem vault.config.yaml)."""
    return (Path(raiz) / "scripts" / "criar_workspace.py").is_file()


def validar_config(cfg: object) -> list[str]:
    """Retorna lista de erros (vazia = config válida). Nunca levanta: shape ruim vira erro."""
    if not isinstance(cfg, dict):
        return ["vault.config.yaml deve ser um mapeamento YAML (chave: valor)"]
    erros = []
    if cfg.get("versao") != 1:
        erros.append("versao deve ser 1")
    if not em_vocabulario(cfg.get("moeda_base"), MOEDAS_BASE):
        erros.append(f"moeda_base deve ser uma de {sorted(MOEDAS_BASE)}")
    harness = cfg.get("harness")
    if (not isinstance(harness, list) or not harness
            or not all(isinstance(h, str) for h in harness)
            or not set(harness) <= HARNESSES):
        erros.append(f"harness deve ser subconjunto não-vazio de {sorted(HARNESSES)}")
    cotacoes = cfg.get("cotacoes")
    provider = cotacoes.get("provider") if isinstance(cotacoes, dict) else None
    if not em_vocabulario(provider, PROVIDERS_COTACOES):
        erros.append(f"cotacoes.provider deve ser um de {sorted(PROVIDERS_COTACOES)}")
    cambio = cotacoes.get("cambio", CAMBIO_PADRAO) if isinstance(cotacoes, dict) else CAMBIO_PADRAO
    if not em_vocabulario(cambio, PROVIDERS_CAMBIO):
        erros.append(f"cotacoes.cambio deve ser um de {sorted(PROVIDERS_CAMBIO)}")
    for chave in NOMES_PADRAO:
        bloco = cfg.get(chave)
        if bloco is not None and (not isinstance(bloco, dict) or not isinstance(bloco.get("nome"), str)
                                  or not bloco["nome"].strip()):
            erros.append(f"{chave} deve ser um mapeamento com nome (string não-vazia), ou ficar ausente")
    contas = cfg.get("contas")
    if not isinstance(contas, list) or not contas:
        erros.append("declare ao menos uma conta em contas")
    else:
        ids = []
        for i, conta in enumerate(contas, start=1):
            if not isinstance(conta, dict) or not isinstance(conta.get("id"), str) or not conta["id"]:
                erros.append(f"conta #{i} sem id (cada conta é um mapeamento com id)")
                continue
            ids.append(conta["id"])
            if not em_vocabulario(conta.get("moeda"), MOEDAS):
                erros.append(f"conta {conta['id']!r} sem moeda válida (uma de {sorted(MOEDAS)})")
            blocos = conta.get("blocos")
            if blocos is not None and (not isinstance(blocos, list)
                                       or not all(em_vocabulario(b, CLASSES) for b in blocos)):
                erros.append(f"conta {conta['id']!r}: blocos deve ser lista de blocos em {sorted(CLASSES)} "
                             "(pode ser vazia; ausente = qualquer bloco)")
        if len(ids) != len(set(ids)):
            erros.append("ids de conta duplicados")
    priv = cfg.get("privacidade")
    if priv is not None:
        remoto = priv.get("remoto-declarado") if isinstance(priv, dict) else object()
        if not isinstance(priv, dict) or not (remoto is None or isinstance(remoto, str)):
            erros.append("privacidade deve ser um mapeamento com remoto-declarado: a URL do SEU "
                         "remoto git (string), ou null se o workspace não tem remoto")
    caminhos = cfg.get("caminhos")
    motor = caminhos.get("motor") if isinstance(caminhos, dict) else None
    if not motor:
        erros.append("caminhos.motor ausente (preenchido pelo criar_workspace)")
    planilhas = caminhos.get("planilhas", PLANILHAS_PADRAO) if isinstance(caminhos, dict) else PLANILHAS_PADRAO
    if not isinstance(planilhas, str) or not planilhas:
        erros.append("caminhos.planilhas deve ser um caminho (string não-vazia)")
    return erros


def provider_cambio(cfg: dict) -> str:
    """Provider usado para câmbio quando há posição fora do BRL (default bcb-sgs)."""
    return (cfg.get("cotacoes") or {}).get("cambio", CAMBIO_PADRAO)


def caminho_planilhas(raiz: str | Path, cfg: dict) -> Path:
    """Pasta onde o cockpit xlsx é gerado: relativa à raiz do workspace, ou absoluta.
    `~` é expandido; caminho relativo a drive do Windows (C:pasta) não é suportado."""
    valor = (cfg.get("caminhos") or {}).get("planilhas", PLANILHAS_PADRAO)
    p = Path(valor).expanduser()
    return p if p.is_absolute() else Path(raiz) / p


def moedas_por_conta(cfg: dict) -> dict[str, str]:
    """{id da conta: moeda}. Config já validada."""
    return {c["id"]: c["moeda"] for c in cfg["contas"]}


def nome(cfg: dict, chave: str) -> str:
    """Nome da casa, do usuário ou do coordenador, com o default do produto quando ausente.
    Config já validada: bloco presente é dict com nome não-vazio."""
    bloco = cfg.get(chave)
    if isinstance(bloco, dict) and isinstance(bloco.get("nome"), str) and bloco["nome"].strip():
        return bloco["nome"].strip()
    return NOMES_PADRAO[chave]


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
