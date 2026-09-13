"""Rubrica do método, lida de metodo/bandas.yaml do motor.

Dado, não código: a skill jabuti-estrategia lê daqui as três alternativas para o perfil da pessoa,
e o validador (check_perfil) recalcula por aqui os dois derivados do perfil — o degrau da função
objetivo e a classificação de risco testado — para a LLM nunca aplicar taxa nem regra de memória.
Formato e invariantes: tests/test_metodo.py.
"""
from pathlib import Path

import yaml

from po.csvs import em_vocabulario

MOTOR = Path(__file__).resolve().parent.parent.parent
ARQUIVO = MOTOR / "metodo" / "bandas.yaml"
ALTERNATIVAS = ("conservadora", "equilibrada", "agressiva")
RISCOS = {"baixo", "medio", "alto"}
RESPOSTAS_CENARIO = {"vende-tudo", "para-de-aportar", "mantem", "aporta-mais"}


def ler_rubrica(caminho: str | Path = ARQUIVO) -> dict:
    """Carrega a rubrica. ValueError com frase acionável se o arquivo faltar ou estiver malformado."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise ValueError(f"rubrica {caminho} ausente — instalação do motor incompleta, clone novamente")
    try:
        doc = yaml.safe_load(caminho.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as e:
        raise ValueError(f"rubrica {caminho.name} malformada: {e}") from e
    if not isinstance(doc, dict) or not isinstance(doc.get("faixas"), list) or "parametros" not in doc:
        raise ValueError(f"rubrica {caminho.name} sem 'parametros' e 'faixas' no topo")
    return doc


def taxa_retirada(rubrica: dict) -> float:
    return float(rubrica["parametros"]["taxa-retirada-real"])


def degrau_if(custo_vida_mensal: float, taxa: float) -> int:
    """Degrau de independência: custo anual ÷ taxa de retirada real, em unidades inteiras da moeda."""
    return int(round(custo_vida_mensal * 12 / taxa))


def classificar_risco(base: list[str], rubrica: dict) -> str:
    """Classe de risco testado a partir das respostas de cenário, pela tabela parametros.risco-testado.

    Ordem fixa: 'baixo' vence 'alto' (quem vende em pânico numa vez e aporta noutra é baixo), e o
    que não casa nenhuma regra é 'medio'. Resposta fora do vocabulário é ValueError, não 'medio'."""
    for r in base:
        if not em_vocabulario(r, RESPOSTAS_CENARIO):
            raise ValueError(f"resposta de cenário {r!r} fora do vocabulário {sorted(RESPOSTAS_CENARIO)}")
    tabela = rubrica["parametros"]["risco-testado"]
    for classe in ("baixo", "alto"):
        regra = tabela[classe]
        if base.count(regra["resposta"]) >= int(regra["minimo"]) and regra.get("sem") not in base:
            return classe
    return "medio"


def selecionar_faixa(rubrica: dict, horizonte_anos: int, risco_testado: str) -> dict | None:
    """A única faixa cujo intervalo de horizonte contém `horizonte_anos` e cujo risco é o dado."""
    if not em_vocabulario(risco_testado, RISCOS):
        raise ValueError(f"risco-testado {risco_testado!r} fora do vocabulário {sorted(RISCOS)}")
    for f in rubrica["faixas"]:
        h = f["horizonte-anos"]
        if f["risco-testado"] == risco_testado and h.get("min", 0) <= horizonte_anos <= h.get("max", 10**6):
            return f
    return None


def aplicar_reserva(alternativa: dict, reserva_meses: int, rubrica: dict) -> dict:
    """Regra de "montar caixa": com reserva abaixo do mínimo, `caixa` sobe até o piso e a diferença
    sai de `rf-br`, deslocando as três colunas da banda.

    Devolve sempre uma cópia, inclusive quando não há o que ajustar: a rubrica é carregada uma vez
    por processo, e quem mutasse o resultado corromperia a faixa para toda consulta seguinte.
    ValueError quando o piso não cabe no alvo de `rf-br`, porque o deslocamento silencioso deixaria
    os alvos somando mais de 100."""
    p = rubrica["parametros"]["reserva"]
    piso, minimo = int(p["caixa-minimo-sem-reserva"]), int(p["minimo-meses"])
    bandas = {b: list(v) for b, v in alternativa["bandas"].items()}
    caixa = alternativa["bandas"]["caixa"]
    delta = piso - caixa[1]
    if reserva_meses >= minimo or delta <= 0:
        return {**alternativa, "bandas": bandas}
    rf_alvo = alternativa["bandas"]["rf-br"][1]
    if delta > rf_alvo:
        raise ValueError(
            f"regra de reserva não cabe nesta alternativa: caixa precisa subir {delta} pontos e "
            f"rf-br só tem {rf_alvo} de alvo, então os alvos deixariam de somar 100 — baixe "
            f"caixa-minimo-sem-reserva em metodo/bandas.yaml ou suba o alvo de rf-br da faixa")
    bandas["caixa"] = [min(100, x + delta) for x in bandas["caixa"]]
    bandas["rf-br"] = [max(0, x - delta) for x in bandas["rf-br"]]
    return {**alternativa, "bandas": bandas}
