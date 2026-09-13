"""Leitura do perfil declarado, politica/00-perfil.md. Frontmatter é a fonte de verdade; as seções
em prosa existem para o humano. Quem escreve é a LLM no jabuti-init; quem confere é check_perfil."""
from pathlib import Path

from po.frontmatter import extrair_frontmatter

ARQUIVO = "politica/00-perfil.md"
OBRIGATORIOS = {
    "idade", "dependentes", "horizonte-anos", "custo-vida-mensal", "funcao-objetivo-provisoria",
    "capacidade-aporte-mensal", "reserva-meses", "risco-declarado", "risco-testado",
    "risco-testado-base", "metas", "classes-vetadas", "liquidez-minima-meses", "degrau-if",
}
RISCO_DECLARADO = {"conservador", "moderado", "arrojado"}
TIPOS_META = {"independencia", "imovel", "renda-passiva", "outra"}


def ler_perfil(raiz: str | Path) -> tuple[dict | None, list[str]]:
    """Retorna (meta, erros). meta é None quando o arquivo falta ou não se lê (o erro diz qual);
    meta sem nenhum campo de OBRIGATORIOS é perfil ainda não preenchido, e não é erro."""
    caminho = Path(raiz) / ARQUIVO
    if not caminho.exists():
        return None, [f"{ARQUIVO} ausente — rode o /jabuti-init para criar o perfil"]
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return None, [f"{ARQUIVO}: não é UTF-8 válido — salve o arquivo como UTF-8"]
    meta, _ = extrair_frontmatter(texto)
    if not meta:
        return None, [f"{ARQUIVO}: sem frontmatter válido"]
    return meta, []


def preenchido(meta: dict) -> bool:
    return bool(OBRIGATORIOS & set(meta))
