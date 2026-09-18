"""A clonagem é a instalação: `/jabuti-init` na pasta clonada roda
`criar_workspace.py . --harness <id> --usuario <nome>`, e a pasta clonada vira a da pessoa.

Teste real do dono (18/09/2026): quem clona e abre o agente ali não entende "onde eu crio a sua
pasta do jabuti?". Agora os arquivos pessoais nascem na raiz do clone, ignorados pelo git do
motor, e os hooks do motor bloqueiam commit e push, porque o remoto desse clone é o jabuti
público. O jabuti ali só muda por `git pull`, e o post-merge regenera o que foi gerado dele.

Tudo roda numa CÓPIA do motor (os arquivos que o git dele conhece, sem `.git`), com git próprio
e um remoto falso: instalar no repositório de verdade apagaria a fronteira que estes testes
existem para provar. O comando instalado é o do passo 0 da skill, lido do SKILL.md.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
BLOQUEIO_COMMIT = "Esta pasta e a sua instalacao do jabuti: commit bloqueado"
BLOQUEIO_PUSH = "Esta pasta e a sua instalacao do jabuti: push bloqueado"
ISSUES = "https://github.com/letsgetithipster/jabuti/issues"
# Sem as variáveis GIT_* do ambiente: dentro do pre-commit do motor, o git exporta
# GIT_INDEX_FILE, e um `git add` na cópia não pode escrever no índice do commit em andamento.
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
ENV["PYTHONIOENCODING"] = "utf-8"
ENV.pop("CLAUDECODE", None)       # o default do harness não pode depender de onde a suíte roda
# Rede de segurança contra recursão: se o bloqueio do pre-commit sumir, o commit da cópia roda a
# suíte da cópia, que instala outra cópia e commita de novo. Só coletar mantém a falha rápida.
ENV["PYTEST_ADDOPTS"] = "--collect-only -q"
GIT_ID = ["-c", "user.name=jabuti-teste", "-c", "user.email=teste@exemplo.invalid",
          "-c", "commit.gpgsign=false"]
SEM_HOOKS = ["-c", "core.hooksPath=.git/hooks"]     # só para montar a fixture, antes de instalar


def _git(cwd, *args, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=ENV)
    if check:
        assert r.returncode == 0, f"git {' '.join(args)} falhou: {r.stdout}{r.stderr}"
    return r


def _py(cwd, *args):
    return subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=ENV)


def _comando_do_passo_0() -> list[str]:
    """Os argumentos que o passo 0 do /jabuti-init manda rodar, com os marcadores trocados."""
    skill = (RAIZ / "skills" / "jabuti-init" / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"`python (scripts/criar_workspace\.py \. --harness <id> --usuario \"<nome>\")`",
                  skill)
    assert m, "o passo 0 do /jabuti-init não manda rodar criar_workspace.py . --harness --usuario"
    return m.group(1).split()


def _copia_do_motor(base: Path) -> tuple[Path, Path]:
    """Cópia do motor com git próprio, um commit e um remoto falso (bare). Devolve (motor, remoto)."""
    r = _git(RAIZ, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    motor = base / "jabuti"
    for rel in (p for p in r.stdout.split("\0") if p):
        origem = RAIZ / rel
        if origem.is_file():
            alvo = motor / rel
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origem, alvo)
    remoto = base / "remoto.git"
    _git(base, "init", "-q", "--bare", "-b", "main", str(remoto))
    _git(motor, "init", "-q", "-b", "main")
    _git(motor, "add", "-A")
    _git(motor, *GIT_ID, *SEM_HOOKS, "commit", "-q", "-m", "motor")
    _git(motor, "remote", "add", "origin", str(remoto))
    _git(motor, *SEM_HOOKS, "push", "-q", "origin", "main")
    _git(motor, "branch", "-q", "--set-upstream-to", "origin/main")
    for chave, valor in (("user.name", "jabuti-teste"), ("user.email", "teste@exemplo.invalid"),
                         ("commit.gpgsign", "false")):
        _git(motor, "config", chave, valor)
    return motor, remoto


def _instalar(motor: Path, harness: str):
    args = _comando_do_passo_0()
    args[args.index("<id>")] = harness
    args[args.index('"<nome>"')] = "Maria"
    return _py(motor, *args, "--data", "2026-09-18")


def _sh() -> str:
    """O sh que o git usa para rodar hook. No Windows ele vem com o git, fora do PATH do Python."""
    achado = shutil.which("sh")
    if achado:
        return achado
    exec_path = Path(_git(RAIZ, "--exec-path").stdout.strip())
    for candidato in (exec_path.parents[2] / "usr" / "bin" / "sh.exe",
                      exec_path.parents[2] / "bin" / "sh.exe"):
        if candidato.exists():
            return str(candidato)
    pytest.fail("sh não encontrado: nem no PATH, nem ao lado do git")


@pytest.fixture(scope="module")
def instalado(tmp_path_factory):
    motor, remoto = _copia_do_motor(tmp_path_factory.mktemp("claude-code"))
    r = _instalar(motor, "claude-code")
    return motor, remoto, r


@pytest.mark.slow
def test_instala_na_raiz_do_clone_sem_sujar_o_git_do_motor(instalado):
    motor, _, r = instalado
    assert r.returncode == 0, r.stdout + r.stderr
    assert _git(motor, "status", "--porcelain").stdout == "", (
        "a instalação sujou o git do motor: algum caminho pessoal não está no .gitignore, ou o "
        "instalador escreveu num arquivo versionado")
    cfg = yaml.safe_load((motor / "vault.config.yaml").read_text(encoding="utf-8"))
    assert cfg["caminhos"]["motor"] == "."
    assert cfg["harness"] == ["claude-code"] and cfg["usuario"]["nome"] == "Maria"
    for pasta in ("dados", "estado", "inbox", "logs", "planilhas", "politica"):
        assert (motor / pasta).is_dir(), pasta
    assert not (motor / "gitignore.template").exists()
    assert "CLAUDE.local.md" in r.stdout and "Próximo passo" in r.stdout
    assert "/cd" not in r.stdout, "o /cd é do fluxo antigo, de pasta separada"
    assert _git(motor, "config", "core.hooksPath").stdout.strip() == ".githooks"


@pytest.mark.slow
def test_harness_claude_code_no_lugar_vai_para_alvos_ignorados(instalado):
    motor, _, _ = instalado
    assert (motor / "CLAUDE.local.md").is_file()
    assert "Maria" in (motor / "CLAUDE.local.md").read_text(encoding="utf-8")
    assert (motor / ".claude" / "rules" / "00-voz.md").is_file()
    assert (motor / "CLAUDE.md").read_text(encoding="utf-8") == (RAIZ / "CLAUDE.md").read_text(
        encoding="utf-8"), "o CLAUDE.md do motor é versionado e não pode ser reescrito no lugar"
    fontes = sorted((motor / "skills").glob("*/SKILL.md"))
    assert fontes
    for fonte in fontes:
        copia = motor / ".claude" / "skills" / fonte.parent.name / "SKILL.md"
        assert copia.is_file() and copia.read_bytes() == fonte.read_bytes(), fonte.parent.name


@pytest.mark.slow
def test_o_validador_da_instalacao_no_lugar_fecha_em_zero_erros(instalado):
    motor, _, _ = instalado
    r = _py(motor, "scripts/validar_workspace.py", ".")
    assert r.returncode == 0 and "0 erro(s)" in r.stdout, r.stdout + r.stderr
    assert "instalação no lugar" not in r.stdout, r.stdout


@pytest.mark.slow
def test_segunda_instalacao_recusa(instalado):
    motor, _, _ = instalado
    r = _instalar(motor, "claude-code")
    assert r.returncode != 0 and "já está instalado aqui" in (r.stdout + r.stderr)
    assert "gerar_harness.py" in (r.stdout + r.stderr)
    assert _git(motor, "status", "--porcelain").stdout == ""


@pytest.mark.slow
def test_commit_bloqueado_na_instalacao(instalado):
    motor, _, _ = instalado
    antes = _git(motor, "rev-parse", "HEAD").stdout
    r = _git(motor, "commit", "--allow-empty", "-m", "x", check=False)
    assert r.returncode != 0, "o commit passou numa instalação de uso"
    assert BLOQUEIO_COMMIT in r.stdout + r.stderr and ISSUES in r.stdout + r.stderr
    assert _git(motor, "rev-parse", "HEAD").stdout == antes


@pytest.mark.slow
def test_push_bloqueado_na_instalacao(instalado):
    motor, _, _ = instalado
    hook = motor / ".githooks" / "pre-push"
    assert hook.is_file(), "o motor não tem hook pre-push"
    r = subprocess.run([_sh(), ".githooks/pre-push", "origin", "x"], cwd=motor, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=ENV)
    assert r.returncode != 0 and BLOQUEIO_PUSH in r.stderr, r.stdout + r.stderr
    # E pelo git, como a pessoa faria: ref nova no remoto, para o git chegar a chamar o hook.
    r = _git(motor, "push", "origin", "HEAD:refs/heads/tentativa", check=False)
    assert r.returncode != 0 and BLOQUEIO_PUSH in r.stderr, r.stdout + r.stderr
    assert "tentativa" not in _git(motor, "ls-remote", "origin").stdout


@pytest.mark.slow
def test_caminho_pessoal_rastreado_e_erro_de_publicacao(instalado):
    motor, _, _ = instalado
    _git(motor, "add", "-f", "dados/fills.csv")
    try:
        r = _py(motor, "scripts/validar_workspace.py", ".")
        assert r.returncode == 1, r.stdout
        assert "dados/fills.csv" in r.stdout and "git rm --cached" in r.stdout, r.stdout
    finally:
        _git(motor, "reset", "-q", "--", "dados/fills.csv")
    assert _git(motor, "status", "--porcelain").stdout == ""


@pytest.mark.slow
def test_so_skills_no_lugar_reinstala_e_apaga_skill_que_saiu(instalado):
    motor, _, _ = instalado
    viva = motor / ".claude" / "skills" / "jabuti-mes"
    morta = motor / ".claude" / "skills" / "jabuti-que-saiu"
    shutil.rmtree(viva)
    morta.mkdir(parents=True)
    (morta / "SKILL.md").write_text("velha", encoding="utf-8", newline="\n")
    r = _py(motor, "scripts/criar_workspace.py", ".", "--so-skills")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (viva / "SKILL.md").is_file() and not morta.exists()
    assert _git(motor, "status", "--porcelain").stdout == ""


@pytest.mark.slow
def test_pasta_dentro_do_motor_continua_recusada(instalado):
    motor, _, _ = instalado
    r = _py(motor, "scripts/criar_workspace.py", "./sub", "--sem-git")
    assert r.returncode != 0 and "dentro do motor" in r.stdout + r.stderr
    assert "criar_workspace.py ." in r.stdout + r.stderr, "a recusa não cita a instalação no lugar"
    assert not (motor / "sub").exists()


@pytest.mark.slow
def test_harness_codex_nao_cria_nada_do_claude(tmp_path):
    motor, _ = _copia_do_motor(tmp_path)
    r = _instalar(motor, "codex")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (motor / "CLAUDE.local.md").exists()
    assert not (motor / ".claude").exists()
    assert "AGENTS.md" in r.stdout
    cfg = yaml.safe_load((motor / "vault.config.yaml").read_text(encoding="utf-8"))
    assert cfg["harness"] == ["codex"]
    assert _git(motor, "status", "--porcelain").stdout == ""
    v = _py(motor, "scripts/validar_workspace.py", ".")
    assert v.returncode == 0 and "0 erro(s)" in v.stdout, v.stdout + v.stderr
    s = _py(motor, "scripts/criar_workspace.py", ".", "--so-skills")
    assert s.returncode == 0 and not (motor / ".claude").exists(), s.stdout + s.stderr


@pytest.mark.slow
def test_git_pull_regenera_o_harness_pelo_post_merge(tmp_path):
    """Depois de um pull, CLAUDE.local.md e as cópias das skills viriam do motor velho. O hook
    post-merge regenera: o adulterado volta a ser o gerado, e a mudança do motor chega à cópia."""
    motor, remoto = _copia_do_motor(tmp_path)
    assert _instalar(motor, "claude-code").returncode == 0
    local = motor / "CLAUDE.local.md"
    gerado = local.read_text(encoding="utf-8")
    local.write_text(gerado + "\nlinha adulterada\n", encoding="utf-8", newline="\n")

    outro = tmp_path / "outro"
    _git(tmp_path, "clone", "-q", str(remoto), str(outro))
    nova = "\nLinha nova do motor, chegada por git pull.\n"
    skill = outro / "skills" / "jabuti-mes" / "SKILL.md"
    with skill.open("a", encoding="utf-8", newline="\n") as f:
        f.write(nova)
    _git(outro, "add", "-A")
    _git(outro, *GIT_ID, *SEM_HOOKS, "commit", "-q", "-m", "motor novo")
    _git(outro, *SEM_HOOKS, "push", "-q", "origin", "main")

    r = _git(motor, "pull", "--no-rebase", "--ff-only", check=False)
    assert r.returncode == 0, r.stdout + r.stderr
    assert local.read_text(encoding="utf-8") == gerado, "o post-merge não regenerou o CLAUDE.local.md"
    copia = motor / ".claude" / "skills" / "jabuti-mes" / "SKILL.md"
    assert nova.strip() in copia.read_text(encoding="utf-8"), "a cópia da skill ficou velha"
    assert _git(motor, "status", "--porcelain").stdout == ""


@pytest.mark.slow
def test_post_merge_sem_instalacao_nao_faz_nada(tmp_path):
    motor, _ = _copia_do_motor(tmp_path)
    r = subprocess.run([_sh(), ".githooks/post-merge", "0"], cwd=motor,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV)
    assert r.returncode == 0 and r.stdout == "" and r.stderr == "", r.stdout + r.stderr
    assert not (motor / "CLAUDE.local.md").exists() and not (motor / ".claude").exists()


def test_o_passo_0_so_usa_harness_que_o_instalador_aceita():
    """O passo 0 escolhe o id pelo agente em que a conversa roda. Id que o instalador não aceita
    é a instalação morrendo no argparse, na primeira conversa da pessoa."""
    from po.config import HARNESSES
    skill = (RAIZ / "skills" / "jabuti-init" / "SKILL.md").read_text(encoding="utf-8")
    passo = skill.split("## Passo 0", 1)
    assert len(passo) == 2, "o /jabuti-init não tem o passo 0, que instala na pasta clonada"
    secao = passo[1].split("\n## ", 1)[0]
    for id_ in ("claude-code", "codex", "cursor"):
        assert f"`{id_}`" in secao and id_ in HARNESSES, id_
    assert "vault.config.yaml" in secao and "scripts/criar_workspace.py" in secao
    assert _comando_do_passo_0()[:2] == ["scripts/criar_workspace.py", "."]
    assert "passo 1" in secao.lower(), "o passo 0 não segue para o perfil na mesma conversa"


def test_o_que_a_instalacao_copia_e_pessoal_e_existe_no_template():
    from criar_workspace import COPIADOS_NO_LUGAR, TEMPLATE
    from po.config import e_pessoal
    for nome in COPIADOS_NO_LUGAR:
        assert (TEMPLATE / nome).exists(), nome
        assert e_pessoal(nome + ("/x" if (TEMPLATE / nome).is_dir() else "")), (
            f"{nome} é copiado para a raiz do motor e não está em CAMINHOS_PESSOAIS")
    copiados = set(COPIADOS_NO_LUGAR)
    do_motor = {".githooks", ".gitattributes", "gitignore.template", "mapeamentos"}
    assert {p.name for p in TEMPLATE.iterdir()} == copiados | do_motor, (
        "o template ganhou um item: decida se ele é pessoal (COPIADOS_NO_LUGAR e .gitignore) "
        "ou se o motor já tem o seu")


def test_o_gitignore_do_motor_cobre_todo_caminho_pessoal_e_so_na_raiz():
    """A lista canônica é CAMINHOS_PESSOAIS; o .gitignore é a outra ponta. Ancorado na raiz: o
    exemplo versionado não pode ficar ignorado."""
    from po.validar.check_publicacao import SONDAS
    r = _git(RAIZ, "check-ignore", "--no-index", *SONDAS, check=False)
    ignorados = set(r.stdout.splitlines())
    assert [s for s in SONDAS if s not in ignorados] == [], r.stdout
    exemplo = ["exemplos/workspace-exemplo/dados/fills.csv",
               "exemplos/workspace-exemplo/vault.config.yaml",
               "exemplos/workspace-exemplo/politica/00-perfil.md",
               "mapeamentos/clear-extrato.yaml"]
    r = _git(RAIZ, "check-ignore", "--no-index", *exemplo, check=False)
    assert r.stdout.strip() == "", f"o .gitignore do motor alcança o que é versionado: {r.stdout}"


def test_detectar_harness_pelo_ambiente():
    from criar_workspace import detectar_harness
    assert detectar_harness({"CLAUDECODE": "1"}) == "claude-code"
    assert detectar_harness({}) == "claude-code"
