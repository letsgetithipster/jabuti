"""Compilador do harness: fontes agnósticas (rules/ do motor) + vault.config.yaml → alvo.

Decisão 3 de 08/09: contrato universal em markdown, um gerador por alvo. Hoje compila só
`claude-code`; `codex`, `cursor` e `app-web` são aceitos no config e ignorados com uma frase.
Alvo é gerado, nunca editado à mão: check_harness regenera em memória e compara.
"""
import shutil
from pathlib import Path

from po.config import carregar_config, nome

MOTOR = Path(__file__).resolve().parent.parent.parent
COMPILAVEIS = {"claude-code"}
RESERVADOS = {"codex", "cursor", "app-web"}
PLACEHOLDERS = ("__CASA__", "__USUARIO__", "__COORDENADOR__")

CLAUDE_MD = """# CLAUDE.md — {casa}

> GERADO por scripts/gerar_harness.py a partir de rules/ do motor e de vault.config.yaml. Nunca
> editar à mão: o validador (check_harness) acusa divergência e bloqueia o commit. Para mudar o
> nome da casa, do usuário ou do coordenador, edite vault.config.yaml e regenere.

Este workspace é de {usuario}. Quem fala aqui é {coordenador}, coordenador da casa, com a voz
e o método em `.claude/rules/00-voz.md`. O contrato que torna tudo isto confiável é o
`GUARDRAILS.md` do motor: leia antes de operar.

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
- **Gerado nunca se edita à mão**: `estado/ESTADO.md` (gerar_estado.py), este CLAUDE.md e
  `.claude/rules/` (gerar_harness.py), o cockpit xlsx (gerar_cockpit.py).
- **Validador antes de commit**: `python <motor>/scripts/validar_workspace.py .` com zero erros;
  o pre-commit repete e bloqueia. Nunca `--no-verify`.
- **Frontmatter é fonte de verdade**; corpo divergente é bug.
- **Um fato mora num lugar só**: perfil em `politica/00-perfil.md`, política em
  `politica/01-alocacao-alvo.md`, posição em `dados/`, estado em `estado/ESTADO.md`. Fora da
  casa, o documento aponta, não copia.
- **Postura legal**: {coordenador} apresenta alternativas com racional e executa a política que
  {usuario} declarou. Nunca "recomendo comprar X"; sempre "sua política aponta X".

## Skills instaladas

{skills}

Catálogo, com quando usar e o que cada uma nunca faz: `skills/README.md` do motor. O caminho
do motor está em `vault.config.yaml`, `caminhos.motor`.
"""


def motor_de(raiz: str | Path, cfg: dict) -> Path:
    """Caminho do motor declarado no config, resolvido contra a raiz quando relativo."""
    valor = Path(str(cfg["caminhos"]["motor"])).expanduser()
    return (valor if valor.is_absolute() else Path(raiz) / valor).resolve()


def _skills_instalaveis(motor: Path) -> list[str]:
    return sorted(p.parent.name for p in (motor / "skills").glob("*/SKILL.md"))


def renderizar_harness(raiz: str | Path, motor: str | Path | None = None) -> dict[str, str]:
    """{caminho relativo à raiz: texto} para cada alvo compilável do config. Não escreve nada.

    ValueError se a fonte rules/00-voz.md não existir no motor: o chamador decide se é erro
    (gerador) ou aviso (check)."""
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
    return {
        "CLAUDE.md": CLAUDE_MD.format(skills=skills, **nomes),
        ".claude/rules/00-voz.md": voz,
    }


def instalar_skills(destino: str | Path, motor: str | Path = MOTOR) -> int:
    """Copia skills/<nome>/SKILL.md do motor para <destino>/.claude/skills/<nome>/SKILL.md.
    Cópia literal, fora do check_harness: `criar_workspace.py --so-skills` reinstala. Retorna quantas."""
    destino, motor = Path(destino).resolve(), Path(motor)
    if not (destino / "vault.config.yaml").exists():
        raise SystemExit(f"erro: {destino} não é um workspace (vault.config.yaml ausente)")
    n = 0
    for skill in sorted((motor / "skills").glob("*/SKILL.md")):
        alvo = destino / ".claude" / "skills" / skill.parent.name / "SKILL.md"
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
