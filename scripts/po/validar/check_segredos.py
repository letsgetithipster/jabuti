"""Procura credencial em arquivo que o git versiona, ou versionaria. Erro, nunca aviso: segredo
commitado está no histórico de todo mundo que clonou, e o custo de desfazer é reescrever
história pública.

O conjunto varrido vem do próprio git (`git ls-files --cached --others --exclude-standard`), que
é exatamente "rastreado, ou não rastreado e não ignorado". Nada de lista de pastas mantida à mão:
espelho de `.gitignore` diverge em silêncio, e este divergiu antes mesmo do código existir — o
`.gitignore` do workspace ignora `inbox/*`, que é justo onde export bruto de corretora cai.

Workspace criado com `--sem-git` não tem `.gitignore` a honrar nem commit a bloquear: ali a
varredura cobre tudo. O que ela nunca cobre é `.env*`, que existe para guardar segredo.
"""
import re
import subprocess
from pathlib import Path

# Formas que só aparecem em credencial de verdade. NÃO passam por escotilha de placeholder: a
# forma já é a prova, e `AKIAIOSFODNN7EXAMPLE` ser o exemplo da AWS não torna um AKIA real menos
# secreto.
PADROES_DE_FORMA = [
    (re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.]{20,}"), "token bearer"),
    (re.compile(r"\bsk_(live|test)_[A-Za-z0-9]{8,}"), "chave secreta de API"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"), "token do GitHub"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "chave de acesso AWS"),
]
# Padrão fraco, por nome de chave. É o que pega segredo sem prefixo reconhecível (senha de
# corretora, token proprietário), e é o único que precisa de escotilha — porque a linha que
# ENSINA o usuário a configurar tem exatamente esta forma.
CREDENCIAL_POR_NOME = re.compile(
    r"""(client[_-]?secret|api[_-]?key|apikey|senha|password)\s*[:=]\s*["']([^"'\s]{8,})["']""",
    re.I)
PREENCHIMENTO = re.compile(
    r"aqui|here|your|seu|sua|exemplo|example|sample|cole|troque|change|placeholder|"
    r"todo|fixme|dummy|fake|xxx|\.\.\.", re.I)
SUFIXOS_BINARIOS = {".xlsx", ".png", ".jpg", ".pdf", ".zip", ".ico"}


def parece_credencial(valor: str) -> bool:
    """True se o valor tem cara de segredo, e não de texto que ensina o usuário a configurar.

    Pergunta invertida de propósito. Lista de placeholders conhecidos é deny-list, e uma de seis
    strings deixou passar 9 de 12 linhas de documentação plausíveis na medição do pré-voo.
    """
    v = valor.strip()
    if len(v) < 8:
        return False
    if any(c in v for c in "<>{} "):       # <sua-chave>, {{TOKEN}}, texto com espaço
        return False
    if PREENCHIMENTO.search(v):            # your-key-here, COLE_AQUI_SUA_CHAVE, exemplo1234
        return False
    if len(set(v)) <= 2:                   # xxxxxxxxxxxx, ------------
        return False
    if v.isupper() and "_" in v:           # MINHA_CHAVE_AQUI
        return False
    return True


def _rotulo(linha: str) -> str:
    """O que a linha revela, ou "" se nada. Forma conhecida vence e não pede escotilha."""
    for padrao, rotulo in PADROES_DE_FORMA:
        if padrao.search(linha):
            return rotulo
    m = CREDENCIAL_POR_NOME.search(linha)
    if m and parece_credencial(m.group(2)):
        return "credencial em texto claro"
    return ""


def _versionaveis(raiz: Path):
    """Arquivos que o git versiona ou versionaria. `.env*` fica de fora sempre."""
    saida = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                           cwd=raiz, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    if saida.returncode == 0:
        candidatos = (raiz / p for p in saida.stdout.split("\0") if p)
    else:
        candidatos = raiz.rglob("*")     # --sem-git: não há gitignore a honrar
    for caminho in candidatos:
        if not caminho.is_file() or caminho.suffix.lower() in SUFIXOS_BINARIOS:
            continue
        if caminho.name == ".env" or caminho.name.startswith(".env."):
            continue
        yield caminho


def checar_segredos(raiz: str | Path) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos). Avisos sempre vazio: aqui não existe meio-termo."""
    raiz = Path(raiz)
    erros = []
    for caminho in _versionaveis(raiz):
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        onde = caminho.relative_to(raiz).as_posix()
        for n, linha in enumerate(texto.splitlines(), start=1):
            rotulo = _rotulo(linha)
            if rotulo:
                erros.append(f"{onde}:{n}: {rotulo} em arquivo versionado — mova para .env "
                             "(ou para o keychain do sistema) e nunca passe segredo como "
                             "argumento de tool MCP, porque argumento entra no transcript do modelo")
    return erros, []
