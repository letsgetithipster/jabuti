"""Alvo do harness no disco tem que ser o que a fonte produz. Divergência é erro (bloqueia commit);
motor inacessível é aviso (não dá para regenerar, e a regra é falhar alto sem bloquear quem não
tem como cumprir)."""
from pathlib import Path

from po.config import carregar_config
from po.harness import motor_de, renderizar_harness


def checar_harness(raiz: str | Path) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos). Config inválida é assunto do check_dados: aqui vira silêncio."""
    raiz = Path(raiz)
    try:
        cfg = carregar_config(raiz)
    except (FileNotFoundError, ValueError):
        return [], []
    motor = motor_de(raiz, cfg)
    if not (motor / "rules" / "00-voz.md").exists():
        return [], [f"harness: motor não encontrado em {cfg['caminhos']['motor']} — não dá para conferir "
                    "o harness; rode gerar_harness.py quando o motor estiver acessível"]
    erros = []
    for rel, texto in renderizar_harness(raiz, motor).items():
        alvo = raiz / rel
        if not alvo.exists():
            erros.append(f"harness: {rel} ausente — rode python <motor>/scripts/gerar_harness.py .")
        elif alvo.read_text(encoding="utf-8-sig") != texto:
            erros.append(f"harness: {rel} diverge da fonte (rules/ do motor ou vault.config.yaml mudou) — "
                         "rode gerar_harness.py; nunca edite à mão")
    return erros, []
