"""Publicar o workspace é ato declarado, nunca default.

O erro catastrófico do usuário deste produto não é um número errado: é um `git push` do workspace
para um repositório público. Patrimônio, corretora, política e histórico de aportes num lugar que
qualquer um lê, e o histórico do git não se apaga. Nada mecânico interceptava isso.

Este check não impede o push — git não é do motor, e um check que tentasse impedir estaria
mentindo sobre o que controla. Ele cobra que o remoto esteja DECLARADO no `vault.config.yaml`:
publicar passa a exigir um gesto consciente, datado no git do usuário, em vez de herdar um remoto
de um `git clone` esquecido ou de um `git remote add` feito por outro motivo.

Gate obrigatório, e é ele que faz este módulo ser correto: o check só fala quando a raiz do
workspace é a raiz do PRÓPRIO repositório git. `git` procura `.git` subindo diretórios, então de
dentro de `exemplos/workspace-exemplo` o comando devolve o remoto público do motor (medido). Sem
o gate, o validador do exemplo ficaria vermelho, e ele roda no pre-commit: todo commit do repo
ficaria bloqueado por um remoto que não é do workspace nenhum.

Instalação no lugar (a raiz é o próprio motor, a pasta clonada virou a da pessoa): ali o remoto
é o jabuti público por construção, e cobrar declaração dele seria cobrar de todo usuário. O que
protege é outra coisa, e é o que o check confere: nenhum caminho pessoal rastreado (erro, com o
`git rm --cached` pronto), todos ignorados pelo .gitignore do motor (erro) e os hooks do motor
ligados, que bloqueiam commit e push ali (aviso, com o `git config` pronto).
"""
import subprocess
from pathlib import Path

from po.config import CAMINHOS_PESSOAIS, carregar_config, e_pessoal, raiz_e_motor

# Um caminho de prova por entrada de CAMINHOS_PESSOAIS: `git check-ignore` responde por caminho,
# e diretório só casa padrão `/dados/` quando o caminho está DENTRO dele.
SONDAS = tuple(p + "sonda" if p.endswith("/") else p.replace("*", "sonda")
               for p in CAMINHOS_PESSOAIS)


def raiz_do_repo(raiz: str | Path) -> Path | None:
    """Raiz do repositório git que contém `raiz`, ou None se não houver git nem repositório."""
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(raiz),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return None                      # git ausente: não é assunto deste check
    if r.returncode != 0 or not r.stdout.strip():
        return None                      # --sem-git, ou pasta fora de qualquer repositório
    return Path(r.stdout.strip()).resolve()


def remotos_de(raiz: str | Path) -> list[str]:
    """URLs de remoto configuradas, sem repetição. Lista vazia = nenhum remoto (ou nenhum git).

    `git config --get-regexp` e não `git remote -v`: aquele devolve fetch e push como duas linhas
    do mesmo remoto, e a deduplicação por URL já é o que interessa aqui.
    """
    try:
        r = subprocess.run(["git", "config", "--get-regexp", r"^remote\..*\.url"], cwd=str(raiz),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return []
    if r.returncode != 0:
        return []                        # returncode 1 = nenhuma chave casou = nenhum remoto
    urls = []
    for linha in r.stdout.splitlines():
        partes = linha.split(None, 1)
        if len(partes) == 2 and partes[1].strip():
            urls.append(partes[1].strip())
    return sorted(dict.fromkeys(urls))


def _git(raiz: Path, *args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", *args], cwd=str(raiz), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return None


def checar_no_lugar(raiz: Path) -> tuple[list[str], list[str]]:
    """Instalação no lugar: o que é da pessoa está fora do git do motor, e os hooks estão ligados."""
    erros, avisos = [], []
    r = _git(raiz, "ls-files", "-z")
    rastreados = [p for p in (r.stdout.split("\0") if r and r.returncode == 0 else []) if p]
    pessoais = sorted(p for p in rastreados if e_pessoal(p))
    if pessoais:
        mostra = ", ".join(pessoais[:5]) + (f" e mais {len(pessoais) - 5}" if len(pessoais) > 5 else "")
        args = " ".join(f'"{p}"' for p in pessoais)
        erros.append(
            f"instalação no lugar: {mostra} está(ão) rastreado(s) pelo git desta pasta, cujo remoto "
            f"é o jabuti público. O que é seu fica fora do git do jabuti. Tire do índice sem apagar "
            f"do disco: git rm --cached -- {args}")
    r = _git(raiz, "check-ignore", "--no-index", *SONDAS)
    ignorados = set(r.stdout.splitlines()) if r is not None and r.returncode in (0, 1) else None
    fora = [p for s, p in zip(SONDAS, CAMINHOS_PESSOAIS) if ignorados is not None and s not in ignorados]
    if fora:
        quais = ", ".join(fora)
        erros.append(
            f"instalação no lugar: {quais} não está(ão) no .gitignore, e um git add levaria o que é "
            f"seu para o git do jabuti. O .gitignore do jabuti cobre todo caminho pessoal; "
            f"restaure-o com: git checkout -- .gitignore")
    r = _git(raiz, "config", "core.hooksPath")
    if r is not None and (r.stdout or "").strip() != ".githooks":
        avisos.append(
            "instalação no lugar: os hooks do jabuti não estão ligados, e sem eles commit e push "
            "desta pasta não ficam bloqueados. Ligue com: git config core.hooksPath .githooks")
    return erros, avisos


def checar_publicacao(raiz: str | Path) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos). No modo separado, avisos sempre vazio: aqui não existe
    meio-termo, como no check_segredos. Ou o remoto está declarado, ou o workspace pode estar
    publicado sem que a pessoa tenha decidido isso. No lugar, ver `checar_no_lugar`."""
    raiz = Path(raiz).resolve()
    if raiz_do_repo(raiz) != raiz:
        return [], []
    if raiz_e_motor(raiz):
        return checar_no_lugar(raiz)
    remotos = remotos_de(raiz)
    if not remotos:
        return [], []
    try:
        cfg = carregar_config(raiz)
    except (FileNotFoundError, ValueError):
        return [], []                    # config quebrada é assunto do check_dados
    bloco = cfg.get("privacidade")
    declarado = bloco.get("remoto-declarado") if isinstance(bloco, dict) else None
    if isinstance(declarado, str) and declarado.strip() in remotos:
        return [], []
    quais = ", ".join(remotos)
    return [(
        f"vault.config.yaml: este workspace tem remoto git ({quais}) e "
        f"privacidade.remoto-declarado não confere. O workspace guarda patrimônio, corretora, "
        f"política e histórico de aportes, e um push para repositório público não se desfaz. Se o "
        f"remoto é SEU e privado, declare-o em vault.config.yaml: privacidade.remoto-declarado: "
        f"'{remotos[0]}' — e leia PRIVACIDADE.md antes, para saber o que fica versionado. Se você "
        f"não queria remoto nenhum: git remote remove <nome>."
    )], []
