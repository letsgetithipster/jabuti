"""Procura credencial em arquivo que o git versiona, ou versionaria. Erro, nunca aviso: segredo
commitado está no histórico de todo mundo que clonou, e o custo de desfazer é reescrever
história pública.

O conjunto varrido vem do próprio git (`git ls-files --cached --others --exclude-standard`), que
é exatamente "rastreado, ou não rastreado e não ignorado". Nada de lista de pastas mantida à mão:
espelho de `.gitignore` diverge em silêncio, e este divergiu antes mesmo do código existir — o
`.gitignore` do workspace ignora `inbox/*`, que é justo onde export bruto de corretora cai.

Workspace criado com `--sem-git` não tem `.gitignore` a honrar nem commit a bloquear: ali a
varredura cobre tudo. O que ela nunca cobre é `.env*`, que existe para guardar segredo.

Instalação no lugar (a raiz é o próprio motor): os arquivos que o motor versiona não são da
pessoa, e os testes do motor têm credencial falsa de propósito. Ali a varredura cobre só o que é
dela e o git levaria: caminho pessoal rastreado (o `git add -f` que o check_publicacao também
acusa) e arquivo não rastreado e não ignorado. Sem git, cobre os caminhos pessoais inteiros.
"""
import os
import re
import subprocess
from pathlib import Path

from po.config import CAMINHOS_PESSOAIS, e_pessoal, raiz_e_motor

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
# Sem \b: `.search()` puro. Vetor conhecido e aceito — um segredo que contenha "fake", "todo",
# "sample" ou "example" como SUBSTRING acidental escaparia da detecção (ex.: um token que por
# acaso contém a sequência "todo"). Não é consertável com \b: `_` conta como caractere de
# palavra, então \b nunca dispara dentro de `COLE_AQUI_SUA_CHAVE`, e é exatamente essa forma de
# placeholder (maiúsculas com underscore) que a escotilha existe para reconhecer — \b quebraria
# a detecção de placeholder, que é o ponto todo. Em chave HEXADECIMAL o vetor é impossível: "k",
# "t", "o", "s" não são dígitos hex, então nenhuma dessas palavras cabe dentro de um valor
# hex. Sobra token alfanumérico ou base64 com uma dessas sequências embutida por acaso,
# probabilidade na casa de 1 em 10 mil (4 letras fixas numa distribuição de ~62-70 símbolos por
# posição). Não "consertar" isso com \b sem reler este comentário primeiro.
PREENCHIMENTO = re.compile(
    r"aqui|here|your|seu|sua|exemplo|example|sample|cole|troque|change|placeholder|"
    r"todo|fixme|dummy|fake|xxx|\.\.\.", re.I)
SUFIXOS_BINARIOS = {".xlsx", ".png", ".jpg", ".pdf", ".zip", ".ico"}
# Só diretório de ferramenta (git interno, cache de bytecode, cache de teste, venv), nunca
# regra do usuário — isso NÃO é espelho de .gitignore, que é justo o que este módulo evita
# manter à mão (ver docstring do arquivo). Sem isso, o fallback sem-git varria 1038 arquivos
# de .git/ e 80 de __pycache__/ à toa: nem incorreto, nem barato.
DIRETORIOS_IGNORADOS_NO_FALLBACK = {".git", "__pycache__", ".pytest_cache", ".venv"}


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


def _rglob_sem_diretorios_de_ferramenta(raiz: Path):
    """rglob("*") plano, mas podando DIRETORIOS_IGNORADOS_NO_FALLBACK na travessia."""
    for dirpath, dirnames, filenames in os.walk(raiz):
        dirnames[:] = [d for d in dirnames if d not in DIRETORIOS_IGNORADOS_NO_FALLBACK]
        for nome in filenames:
            yield Path(dirpath) / nome


def _ls_files(raiz: Path, *args: str) -> list[str] | None:
    saida = subprocess.run(["git", "ls-files", *args, "-z"], cwd=raiz, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    return [p for p in saida.stdout.split("\0") if p] if saida.returncode == 0 else None


def _pessoais_no_disco(raiz: Path):
    """Os arquivos dos CAMINHOS_PESSOAIS na raiz, sem git para dizer o que ele levaria."""
    for padrao in CAMINHOS_PESSOAIS:
        if padrao.endswith("/"):
            if (raiz / padrao).is_dir():
                yield from _rglob_sem_diretorios_de_ferramenta(raiz / padrao)
        else:
            yield from raiz.glob(padrao)


def _versionaveis(raiz: Path):
    """Arquivos que o git versiona ou versionaria. `.env*` fica de fora sempre."""
    no_lugar = raiz_e_motor(raiz)
    todos = _ls_files(raiz, "--cached", "--others", "--exclude-standard")
    if todos is not None and no_lugar:
        soltos = set(_ls_files(raiz, "--others", "--exclude-standard") or [])
        candidatos = (raiz / p for p in todos if e_pessoal(p) or p in soltos)
    elif todos is not None:
        candidatos = (raiz / p for p in todos)
    elif no_lugar:
        candidatos = _pessoais_no_disco(raiz)
    else:
        candidatos = _rglob_sem_diretorios_de_ferramenta(raiz)   # --sem-git: não há gitignore a honrar
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
