"""Compilador do harness: fontes agnósticas (rules/ do motor) + vault.config.yaml → alvo.

Decisão 3 de 08/09: contrato universal em markdown, um gerador por alvo. Hoje compila só
`claude-code`; `codex`, `cursor` e `app-web` são aceitos no config e não recebem nada compilado:
esses agentes leem o `AGENTS.md` do motor, que despacha as skills e manda ler a voz.
Alvo é gerado, nunca editado à mão: check_harness regenera em memória e compara.

Dois modos, decididos pela posição da raiz em relação ao motor. Separado (a pasta da pessoa fica
fora do motor): `CLAUDE.md` na raiz dela. No lugar (a raiz É o motor, a pasta clonada virou a da
pessoa): `CLAUDE.local.md`, que o Claude Code carrega sozinho e o .gitignore do motor ignora,
porque o `CLAUDE.md` dali é o do motor, versionado, que importa o `AGENTS.md`.
"""
import shutil
from pathlib import Path

from po.config import carregar_config, nome

MOTOR = Path(__file__).resolve().parent.parent.parent
COMPILAVEIS = {"claude-code"}
RESERVADOS = {"codex", "cursor", "app-web"}
PLACEHOLDERS = ("__CASA__", "__USUARIO__", "__COORDENADOR__")

# As partes do CLAUDE_MD que mudam entre os dois modos. O modo separado reproduz, byte a byte, o
# CLAUDE.md de antes da instalação no lugar: o exemplo versionado é a prova (test_harness).
VARIANTES = {
    "separado": {
        "arquivo": "CLAUDE.md",
        "cabeca": (
            "> GERADO por scripts/gerar_harness.py a partir de rules/ do motor e de vault.config.yaml. Nunca\n"
            "> editar à mão: o validador (check_harness) acusa divergência e bloqueia o commit. Para mudar o\n"
            "> nome da casa, do usuário ou do coordenador, edite vault.config.yaml e regenere."),
        "quem": (
            "Este workspace é de {usuario}. Quem fala aqui é {coordenador}, coordenador da casa, com a voz\n"
            "e o método em `.claude/rules/00-voz.md`. O contrato que torna tudo isto confiável é o\n"
            "`GUARDRAILS.md` do motor: leia antes de operar."),
        "validador": (
            "- **Validador antes de commit**: `python <motor>/scripts/validar_workspace.py .` com zero erros;\n"
            "  o pre-commit repete e bloqueia. Nunca `--no-verify`."),
        "catalogo": (
            "Catálogo, com quando usar e o que cada uma nunca faz: `skills/README.md` do motor. O caminho\n"
            "do motor está em `vault.config.yaml`, `caminhos.motor`."),
    },
    "no-lugar": {
        "arquivo": "CLAUDE.local.md",
        "cabeca": (
            "> GERADO por scripts/gerar_harness.py a partir de rules/ e de vault.config.yaml. Nunca editar\n"
            "> à mão: o validador (check_harness) acusa divergência. Para mudar o nome da casa, do usuário\n"
            "> ou do coordenador, edite vault.config.yaml e rode python scripts/gerar_harness.py ."),
        "quem": (
            "Esta pasta é a instalação do jabuti de {usuario}: o motor, que só muda por `git pull`, e os\n"
            "dados, que ficam fora do git. Quem fala aqui é {coordenador}, coordenador da casa, com a voz e\n"
            "o método em `.claude/rules/00-voz.md`. O contrato que torna tudo isto confiável é o\n"
            "`GUARDRAILS.md`: leia antes de operar."),
        "validador": (
            "- **Validador ao fim de cada skill**: `python scripts/validar_workspace.py .` com zero erros.\n"
            "  Commit e push ficam bloqueados nesta pasta; nunca `--no-verify`.\n"
            "- **Nunca editar arquivo do motor** (`scripts/`, `skills/`, `rules/`, `metodo/`, `templates/`,\n"
            "  `docs/`, os mapeamentos prontos, os documentos da raiz): ele só muda por `git pull`. O\n"
            "  mapeamento que você escrever é `mapeamentos/meu-<corretora>.yaml`, fora do git."),
        "catalogo": (
            "Catálogo, com quando usar e o que cada uma nunca faz: `skills/README.md`. O motor é esta\n"
            "mesma pasta: onde uma skill diz `<motor>`, leia `.`."),
    },
}

CLAUDE_MD = """# {arquivo} — {casa}

{cabeca}

{quem}

## Ao abrir uma sessão

1. Ler `estado/SETUP.md`. Se o onboarding está aberto (alguma linha `- [ ]`), cumprimentar
   {usuario} com a etapa em que está ("etapa 2 de 5, perfil pronto") e oferecer o próximo
   passo, que é a linha `Próximo:` do próprio SETUP.md, pronta para colar. Não perguntar o que
   a pessoa quer fazer: dizer o que falta.
2. Se o onboarding está fechado, operar normal: `estado/ESTADO.md` é a primeira leitura para
   qualquer pergunta de alocação.

## Regras operacionais

- **Número de mercado entra por script**, nunca digitado: cotação via `/jabuti-mes`;
  posição, fill e provento via `/jabuti-importar`. Sem rede, parar e declarar.
- **Gerado nunca se edita à mão**: `estado/ESTADO.md` (gerar_estado.py), este {arquivo} e
  `.claude/rules/` (gerar_harness.py), o cockpit xlsx (gerar_cockpit.py).
{validador}
- **Frontmatter é fonte de verdade**; corpo divergente é bug.
- **Um fato mora num lugar só**: perfil em `politica/00-perfil.md`, política em
  `politica/01-alocacao-alvo.md`, posição em `dados/`, estado em `estado/ESTADO.md`. Fora da
  casa, o documento aponta, não copia.
- **Postura legal**: {coordenador} apresenta alternativas com racional e executa a política que
  {usuario} declarou. Nunca "recomendo comprar X"; sempre "sua política aponta X".

## Skills instaladas

{skills}

{catalogo}
"""


def motor_de(raiz: str | Path, cfg: dict) -> Path:
    """Caminho do motor declarado no config, resolvido contra a raiz quando relativo."""
    valor = Path(str(cfg["caminhos"]["motor"])).expanduser()
    return (valor if valor.is_absolute() else Path(raiz) / valor).resolve()


def no_lugar(raiz: str | Path, motor: str | Path) -> bool:
    """A raiz é o próprio motor: a pasta clonada virou a da pessoa (`caminhos.motor: '.'`)."""
    return Path(raiz).resolve() == Path(motor).resolve()


def _skills_instalaveis(motor: Path) -> list[str]:
    return sorted(p.parent.name for p in (motor / "skills").glob("*/SKILL.md"))


def renderizar_harness(raiz: str | Path, motor: str | Path | None = None) -> dict[str, str]:
    """{caminho relativo à raiz: texto} para cada alvo compilável do config. Não escreve nada.

    O alvo principal é `CLAUDE.md` no modo separado e `CLAUDE.local.md` no lugar (a raiz é o
    motor, cujo `CLAUDE.md` é versionado). ValueError se a fonte rules/00-voz.md não existir no
    motor: o chamador decide se é erro (gerador) ou aviso (check)."""
    raiz = Path(raiz)
    cfg = carregar_config(raiz)
    motor = Path(motor).resolve() if motor else motor_de(raiz, cfg)
    fonte = motor / "rules" / "00-voz.md"
    if not fonte.exists():
        raise ValueError(f"fonte do harness ausente em {fonte} — confira caminhos.motor no vault.config.yaml")
    if "claude-code" not in cfg["harness"]:
        return {}
    nomes = {"casa": nome(cfg, "casa"), "usuario": nome(cfg, "usuario"), "coordenador": nome(cfg, "coordenador")}
    voz = fonte.read_text(encoding="utf-8-sig")
    for marca, chave in zip(PLACEHOLDERS, ("casa", "usuario", "coordenador")):
        voz = voz.replace(marca, nomes[chave])
    skills = "\n".join(f"- `/{s}`" for s in _skills_instalaveis(motor)) or "(nenhuma skill no motor)"
    partes = {k: v.format(**nomes) for k, v in VARIANTES["no-lugar" if no_lugar(raiz, motor) else "separado"].items()}
    return {
        partes["arquivo"]: CLAUDE_MD.format(skills=skills, **nomes, **partes),
        ".claude/rules/00-voz.md": voz,
    }


def instalar_skills(destino: str | Path, motor: str | Path = MOTOR) -> int:
    """Copia skills/<nome>/SKILL.md do motor para <destino>/.claude/skills/<nome>/SKILL.md.
    Cópia literal, fora do check_harness: `criar_workspace.py --so-skills` reinstala. Retorna quantas.

    No lugar (destino == motor), as cópias existem só para os comandos nativos do Claude Code:
    sem `claude-code` no `harness:` do config, nada é copiado (o agente lê `skills/` pelo
    AGENTS.md), e cópia `jabuti-*` de skill que saiu do motor é apagada, para o `git pull` não
    deixar comando morto no menu. O modo separado copia sempre, como antes."""
    destino, motor = Path(destino).resolve(), Path(motor)
    if not (destino / "vault.config.yaml").exists():
        raise SystemExit(f"erro: {destino} não é um workspace (vault.config.yaml ausente)")
    fontes = sorted((motor / "skills").glob("*/SKILL.md"))
    base = destino / ".claude" / "skills"
    if no_lugar(destino, motor):
        try:
            cfg = carregar_config(destino)
        except (FileNotFoundError, ValueError) as e:
            raise SystemExit(f"erro: {e}")
        if "claude-code" not in cfg["harness"]:
            return 0
        vivas = {s.parent.name for s in fontes}
        for velha in sorted(base.glob("jabuti-*")) if base.is_dir() else []:
            if velha.is_dir() and velha.name not in vivas:
                shutil.rmtree(velha)
    n = 0
    for skill in fontes:
        alvo = base / skill.parent.name / "SKILL.md"
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(skill, alvo)
        n += 1
    return n


def escrever_harness(raiz: str | Path, motor: str | Path | None = None, com_skills: bool = True) -> list[Path]:
    """Escreve os alvos compilados e (opcional) instala as skills. Idempotente. Devolve os caminhos escritos."""
    raiz = Path(raiz)
    escritos = []
    for rel, texto in renderizar_harness(raiz, motor).items():
        alvo = raiz / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(texto, encoding="utf-8", newline="\n")
        escritos.append(alvo)
    if com_skills:
        cfg = carregar_config(raiz)
        instalar_skills(raiz, motor=Path(motor).resolve() if motor else motor_de(raiz, cfg))
    return escritos
