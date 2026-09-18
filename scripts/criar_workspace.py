"""Instala o jabuti: na própria pasta clonada (`.`), ou numa pasta separada do motor.

Uso: python scripts/criar_workspace.py . [--harness claude-code|codex|cursor|app-web]
        [--usuario NOME] [--casa NOME] [--data AAAA-MM-DD] [--sem-git] [--so-skills]
     python scripts/criar_workspace.py C:\\caminho\\meu-vault [--sem-git] [--data AAAA-MM-DD]
        [--motor CAMINHO] [--harness ...] [--casa NOME] [--usuario NOME] [--so-skills]

`.` na raiz do motor é a instalação no lugar: a pasta clonada vira a da pessoa, os arquivos
pessoais nascem na raiz, fora do git do motor (.gitignore), e os hooks do motor passam a bloquear
commit e push ali. Outra pasta fora do motor é o modo separado, com git próprio.
"""
import argparse
import datetime
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from po.cli import preparar_console  # noqa: E402

preparar_console()


def _checar_ambiente(com_git: bool = True) -> list[str]:
    """Falha na porta, com o comando de correção, em vez de falhar no terceiro passo (spec §2.1).

    Erro (SystemExit): Python < 3.11, pyyaml ausente, git fora do PATH quando o workspace vai
    nascer versionado. Aviso (devolvido): openpyxl ausente, que só tira o .xlsx e o cockpit.
    Chamada também na importação deste módulo, antes de `po.config` importar `yaml`: sem isso a
    falta de pyyaml seria um traceback de import, não uma frase.
    """
    if sys.version_info < (3, 11):
        v = ".".join(str(x) for x in sys.version_info[:2])
        raise SystemExit(f"erro: Python {v} — o jabuti precisa de Python 3.11 ou mais novo: "
                         "https://www.python.org/downloads/")
    if importlib.util.find_spec("yaml") is None:
        raise SystemExit("erro: pyyaml não instalado — rode: python -m pip install -r requirements.txt")
    if com_git and shutil.which("git") is None:
        raise SystemExit("erro: git não encontrado no PATH — instale (https://git-scm.com/downloads) "
                         "ou rode com --sem-git")
    avisos = []
    if importlib.util.find_spec("openpyxl") is None:
        avisos.append("aviso: openpyxl não instalado — extrato .xlsx e cockpit ficam de fora até: "
                      "python -m pip install -r requirements-xlsx.txt")
    return avisos


_checar_ambiente(com_git=False)   # Python e pyyaml, antes do import abaixo puxar `yaml`

from po.config import HARNESSES, NOMES_PADRAO  # noqa: E402
from po.harness import escrever_harness, instalar_skills  # noqa: E402,F401  (reexportado: os testes importam daqui)

MOTOR = Path(__file__).resolve().parent.parent
TEMPLATE = MOTOR / "templates" / "workspace"
SKILLS = MOTOR / "skills"
# O que a instalação no lugar copia do template para a raiz do motor. O resto do template
# (.githooks/, .gitattributes, gitignore.template, mapeamentos/) o motor já tem, na versão dele.
COPIADOS_NO_LUGAR = ("dados", "estado", "inbox", "logs", "planilhas", "politica", "vault.config.yaml")
# Variável de ambiente que denuncia o agente que rodou o instalador. Sem detecção, claude-code,
# como sempre foi; o /jabuti-init passa --harness explícito, então isto é só o default do terminal.
DETECCAO_DE_HARNESS = (("CLAUDECODE", "1", "claude-code"),)
ISSUES = "https://github.com/letsgetithipster/jabuti/issues"


def detectar_harness(env=None) -> str:
    """Id do harness pelo ambiente; claude-code quando nada denuncia o agente."""
    env = os.environ if env is None else env
    for variavel, valor, harness in DETECCAO_DE_HARNESS:
        if env.get(variavel) == valor:
            return harness
    return "claude-code"


def _yaml_str(valor: str) -> str:
    """String YAML entre aspas simples, com a aspa interna dobrada."""
    return "'" + valor.replace("'", "''") + "'"


def _resolver_config(cfg: Path, valor_motor: str, harness: str, casa: str | None,
                     usuario: str | None) -> None:
    texto_cfg = (cfg.read_text(encoding="utf-8")
                 .replace("__MOTOR__", _yaml_str(valor_motor))
                 .replace("harness: [claude-code]", f"harness: [{harness}]")
                 .replace("__CASA__", _yaml_str(casa or NOMES_PADRAO["casa"]))
                 .replace("__USUARIO__", _yaml_str(usuario or NOMES_PADRAO["usuario"])))
    cfg.write_text(texto_cfg, encoding="utf-8", newline="\n")


def _trocar_data(pastas: list[Path], data: str) -> None:
    for pasta in pastas:
        for md in pasta.rglob("*.md"):
            texto = md.read_text(encoding="utf-8")
            if "__DATA__" in texto:
                md.write_text(texto.replace("__DATA__", data), encoding="utf-8", newline="\n")


def _apagar(caminho: Path) -> None:
    if caminho.is_dir():
        shutil.rmtree(caminho, ignore_errors=True)
    elif caminho.exists():
        caminho.unlink()


def e_repo_git(raiz: Path) -> bool:
    """A raiz é a raiz de um repositório git (o clone). Download em zip não é."""
    return (raiz / ".git").exists()


def instalar_no_lugar(harness: str = "claude-code", data: str | None = None,
                      casa: str | None = None, usuario: str | None = None,
                      com_git: bool = True) -> Path:
    """A pasta clonada vira a da pessoa: copia os arquivos pessoais do template para a raiz do
    motor, resolve os placeholders com `caminhos.motor: '.'`, compila o harness para o alvo
    escolhido e liga os hooks do motor (que, com vault.config.yaml na raiz, bloqueiam commit e
    push). Nunca roda `git init` e nunca toca arquivo do motor. Em falha, apaga só o que criou."""
    raiz = MOTOR
    if (raiz / "vault.config.yaml").exists():
        raise SystemExit(
            "erro: o jabuti já está instalado aqui (vault.config.yaml existe na raiz) e o instalador "
            "não sobrescreve os seus arquivos. Para reinstalar só as skills e o harness: "
            "python scripts/gerar_harness.py .")
    if harness not in HARNESSES:
        raise SystemExit(f"erro: harness {harness!r} desconhecido — use um de {sorted(HARNESSES)}")
    ocupados = [n for n in COPIADOS_NO_LUGAR if (raiz / n).exists()]
    if harness == "claude-code" and (raiz / "CLAUDE.local.md").exists():
        ocupados.append("CLAUDE.local.md")
    if ocupados:
        raise SystemExit(
            f"erro: já existe {', '.join(ocupados)} na raiz do jabuti, sem vault.config.yaml ao lado, "
            "e o instalador não sobrescreve arquivo que não criou. Mova para fora desta pasta e rode "
            "de novo.")
    repo = com_git and e_repo_git(raiz)
    for aviso in _checar_ambiente(com_git=repo):   # antes de qualquer cópia
        print(aviso)
    if not TEMPLATE.is_dir():
        raise SystemExit(
            "erro: templates/workspace ausente — instalação do motor incompleta, clone novamente")
    data = data or datetime.date.today().isoformat()
    # O que existia antes não é apagado no rollback: .claude/ pode ter settings.local.json da
    # sessão do agente.
    geraveis = [raiz / "CLAUDE.local.md", raiz / ".claude" / "rules", raiz / ".claude" / "skills",
                raiz / ".claude"]
    ja_existiam = {p for p in geraveis if p.exists()}
    criados = []
    try:
        for n in COPIADOS_NO_LUGAR:
            origem, alvo = TEMPLATE / n, raiz / n
            criados.append(alvo)
            if origem.is_dir():
                shutil.copytree(origem, alvo)
            else:
                shutil.copyfile(origem, alvo)
        _resolver_config(raiz / "vault.config.yaml", ".", harness, casa, usuario)
        _trocar_data([raiz / n for n in COPIADOS_NO_LUGAR if (raiz / n).is_dir()], data)
        escrever_harness(raiz, motor=raiz)
        if repo:
            try:
                subprocess.run(["git", "config", "core.hooksPath", ".githooks"],
                               cwd=raiz, check=True, capture_output=True)
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                stderr = (getattr(e, "stderr", b"") or b"").decode(errors="replace").strip()
                raise SystemExit(
                    f"erro: git falhou ao ligar os hooks: {stderr or e} (nada ficou instalado; "
                    "rode de novo após corrigir)")
    except BaseException:
        for p in criados:
            _apagar(p)
        for p in geraveis:
            if p not in ja_existiam:
                _apagar(p)
        raise
    return raiz


def criar(destino: str | Path, com_git: bool = True, data: str | None = None,
          motor: str | None = None, harness: str = "claude-code",
          casa: str | None = None, usuario: str | None = None) -> Path:
    """Copia o template, resolve placeholders, compila o harness e (opcional) inicializa git com hooks.

    destino == motor é a instalação no lugar (`instalar_no_lugar`). Fora dele, o modo separado:
    motor é o valor gravado em caminhos.motor (default: caminho absoluto deste motor; fixtures
    versionadas passam relativo, ex. '../..'). harness: alvo gravado em `harness:` (um dos
    HARNESSES; só claude-code é compilado hoje). Em falha após a cópia, o destino desta execução
    é limpo — nunca sobra workspace pela metade.
    """
    destino = Path(destino).resolve()
    if destino == MOTOR:
        if motor is not None:
            raise SystemExit("erro: --motor não vale na instalação no lugar: aqui caminhos.motor é "
                             "sempre '.'")
        return instalar_no_lugar(harness=harness, data=data, casa=casa, usuario=usuario,
                                 com_git=com_git)
    # Uma pasta DENTRO do motor, sem ser ele, teria dado pessoal no git do método (o .gitignore do
    # motor só cobre os caminhos pessoais da raiz) e num push.
    if MOTOR in destino.parents:
        raise SystemExit(
            f"erro: {destino} fica dentro do motor ({MOTOR}). Duas saídas: instalar na própria pasta "
            f"do jabuti, com python scripts/criar_workspace.py . (os seus dados ficam na raiz, fora "
            f"do git); ou uma pasta fora do motor, o modo separado, por exemplo "
            f"{MOTOR.parent / 'meu-jabuti'}")
    for aviso in _checar_ambiente(com_git=com_git):   # antes de qualquer cópia
        print(aviso)
    if harness not in HARNESSES:
        raise SystemExit(f"erro: harness {harness!r} desconhecido — use um de {sorted(HARNESSES)}")
    if destino.exists() and not destino.is_dir():
        raise SystemExit(f"erro: destino {destino} existe e não é uma pasta")
    if destino.exists() and any(destino.iterdir()):
        raise SystemExit(
            f"erro: destino {destino} não está vazio — escolha uma pasta nova ou vazia")
    if not TEMPLATE.is_dir():
        raise SystemExit(
            "erro: templates/workspace ausente — instalação do motor incompleta, clone novamente")
    data = data or datetime.date.today().isoformat()
    valor_motor = motor if motor is not None else MOTOR.as_posix()
    shutil.copytree(TEMPLATE, destino, dirs_exist_ok=True)
    try:
        (destino / "gitignore.template").rename(destino / ".gitignore")
        _resolver_config(destino / "vault.config.yaml", valor_motor, harness, casa, usuario)
        _trocar_data([destino], data)
        escrever_harness(destino, motor=MOTOR)   # CLAUDE.md, .claude/rules/, .claude/skills/
        os.chmod(destino / ".githooks" / "pre-commit", 0o755)
        if com_git:
            try:
                subprocess.run(["git", "init"], cwd=destino, check=True, capture_output=True)
                subprocess.run(["git", "config", "core.hooksPath", ".githooks"],
                               cwd=destino, check=True, capture_output=True)
            except FileNotFoundError:
                raise SystemExit(
                    "erro: git não encontrado no PATH — instale o git ou rode com --sem-git "
                    "(o destino foi limpo; rode de novo após corrigir)")
            except subprocess.CalledProcessError as e:
                stderr = (e.stderr or b"").decode(errors="replace").strip()
                raise SystemExit(
                    f"erro: git falhou: {stderr} (o destino foi limpo; rode de novo após corrigir)")
    except BaseException:
        shutil.rmtree(destino, ignore_errors=True)
        raise
    return destino


def _relatar_no_lugar(raiz: Path, harness: str, com_git: bool) -> None:
    pessoais = ", ".join(f"{n}/" if (raiz / n).is_dir() else n for n in COPIADOS_NO_LUGAR)
    print(f"jabuti instalado aqui mesmo, em {raiz}")
    print(f"  seus arquivos: {pessoais}, todos fora do git do jabuti (.gitignore)")
    if harness == "claude-code":
        n = len(list((raiz / ".claude" / "skills").glob("*/SKILL.md")))
        print(f"  harness claude-code: CLAUDE.local.md, .claude/rules/00-voz.md e {n} skill(s) "
              "em .claude/skills/ (os comandos do menu)")
    else:
        print(f"  harness {harness}: nada a compilar; o seu agente lê AGENTS.md e as skills em skills/")
    if com_git and e_repo_git(raiz):
        print("  git: hooks ligados (core.hooksPath = .githooks). Commit e push ficam bloqueados "
              "nesta pasta; para atualizar o jabuti, git pull")
        print(f"  para propor mudança no jabuti, abra uma issue: {ISSUES}")
    else:
        print("  sem repositório git nesta pasta: para atualizar o jabuti, baixe a versão nova")
    print("Próximo passo: seguir com o perfil, nesta mesma conversa (/jabuti-init, passo 1).")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("destino",
                    help=". na raiz do jabuti instala aqui mesmo; outra pasta, nova ou vazia, fora "
                         "do jabuti, é o modo separado")
    ap.add_argument("--sem-git", action="store_true",
                    help="não inicializa repositório git (no lugar: não liga os hooks)")
    ap.add_argument("--data", help="data AAAA-MM-DD gravada nos documentos (default: hoje)")
    ap.add_argument("--motor",
                    help="valor de caminhos.motor no modo separado (default: este motor; fixture "
                         "usa relativo)")
    ap.add_argument("--harness", choices=sorted(HARNESSES),
                    help="o agente que você usa (default: detectado pelo ambiente, senão "
                         "claude-code); só claude-code recebe arquivos compilados, os outros "
                         "leem AGENTS.md")
    ap.add_argument("--casa", help="nome da sua casa de gestão (default: %(default)s)",
                    default=NOMES_PADRAO["casa"])
    ap.add_argument("--usuario", help="como o coordenador se dirige a você (default: %(default)s)",
                    default=NOMES_PADRAO["usuario"])
    ap.add_argument("--so-skills", action="store_true",
                    help="só (re)instala as skills em .claude/skills/ de uma instalação existente")
    args = ap.parse_args()
    harness = args.harness or detectar_harness()
    destino = Path(args.destino).resolve()
    if args.so_skills:
        n = instalar_skills(destino)
        if destino == MOTOR and n == 0:
            print("nenhuma skill copiada: o harness desta instalação não é claude-code, e o seu "
                  "agente lê as skills direto de skills/ pelo AGENTS.md")
        else:
            print(f"{n} skill(s) instalada(s) em {destino / '.claude' / 'skills'}")
        return
    criado = criar(destino, com_git=not args.sem_git, data=args.data, motor=args.motor,
                   harness=harness, casa=args.casa, usuario=args.usuario)
    if criado == MOTOR:
        _relatar_no_lugar(criado, harness, com_git=not args.sem_git)
        return
    print(f"Workspace criado em {criado}")
    print("Próximo passo: abra o seu agente na pasta nova e cole /jabuti-init.")
    print(f'  No terminal: cd "{criado}" e abra o agente ali (claude, codex ou o que você usa).')
    print("Este workspace é PRIVADO por desenho: não publique este repositório.")


if __name__ == "__main__":
    main()
