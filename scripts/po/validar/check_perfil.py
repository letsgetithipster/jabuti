"""Checa o perfil declarado: campos presentes e tipados, vocabulários, e os dois derivados
recalculados pela rubrica. Perfil ainda não preenchido é aviso (o jabuti-init preenche)."""
from pathlib import Path

from po.csvs import CLASSES, em_vocabulario
from po.metodo import RESPOSTAS_CENARIO, RISCOS, classificar_risco, degrau_if, ler_rubrica, taxa_retirada
from po.perfil import ARQUIVO, OBRIGATORIOS, RISCO_DECLARADO, TIPOS_META, ler_perfil, preenchido

TOLERANCIA_DEGRAU = 1   # unidade inteira da moeda: só o arredondamento final pode divergir


def _dica_bool(valor) -> str:
    """O YAML 1.1 resolve on/off/yes/no/true/false para bool antes de o validador ver (medido:
    `sim` e `não` NÃO coagem, viram string), e o repr mostraria `True` para quem digitou `on`.
    Reportar um valor que a pessoa nunca escreveu é pior que não reportar nada."""
    if isinstance(valor, bool):
        return (" — o YAML leu isso como verdadeiro/falso; escreva só o número, e note que"
                " on, off, yes, no, true e false viram booleano sozinhos")
    return ""


def _inteiro(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0


def checar_perfil(raiz: str | Path) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos)."""
    meta, erros = ler_perfil(raiz)
    if meta is None:
        return erros, []
    if not preenchido(meta):
        return [], ["perfil: ainda não preenchido (o /jabuti-init preenche)"]
    faltam = sorted(OBRIGATORIOS - set(meta))
    for campo in faltam:
        erros.append(f"perfil: campo {campo} ausente do frontmatter — o jabuti-init grava todos")
    for campo in ("idade", "dependentes", "horizonte-anos", "reserva-meses", "liquidez-minima-meses"):
        if campo in meta and not _inteiro(meta[campo]):
            erros.append(f"perfil: {campo} deve ser inteiro não-negativo "
                         f"(lido: {meta[campo]!r}){_dica_bool(meta[campo])}")
    if "capacidade-aporte-mensal" in meta and not _numero(meta["capacidade-aporte-mensal"]):
        erros.append(f"perfil: capacidade-aporte-mensal deve ser número não-negativo "
                     f"(lido: {meta['capacidade-aporte-mensal']!r})"
                     f"{_dica_bool(meta['capacidade-aporte-mensal'])}")
    custo = meta.get("custo-vida-mensal")
    if "custo-vida-mensal" in meta and custo is not None and not _numero(custo):
        erros.append(f"perfil: custo-vida-mensal deve ser número não-negativo ou null "
                     f"(lido: {custo!r}){_dica_bool(custo)}")
    if "funcao-objetivo-provisoria" in meta and not isinstance(meta["funcao-objetivo-provisoria"], bool):
        erros.append("perfil: funcao-objetivo-provisoria deve ser true ou false")
    if "risco-declarado" in meta and not em_vocabulario(meta["risco-declarado"], RISCO_DECLARADO):
        erros.append(f"perfil: risco-declarado deve ser um de {sorted(RISCO_DECLARADO)} (lido: {meta['risco-declarado']!r})")
    if "risco-testado" in meta and not em_vocabulario(meta["risco-testado"], RISCOS):
        erros.append(f"perfil: risco-testado deve ser um de {sorted(RISCOS)} (lido: {meta['risco-testado']!r})")
    base = meta.get("risco-testado-base")
    base_ok = isinstance(base, list) and len(base) == 3 and all(em_vocabulario(r, RESPOSTAS_CENARIO) for r in base)
    if "risco-testado-base" in meta and not base_ok:
        erros.append(f"perfil: risco-testado-base deve ser lista com as 3 respostas de cenário, cada uma em {sorted(RESPOSTAS_CENARIO)}")
    metas = meta.get("metas")
    if "metas" in meta:
        if not isinstance(metas, list) or not metas:
            erros.append("perfil: metas deve ser lista não-vazia de {tipo, valor, prazo}")
        else:
            for i, m in enumerate(metas, start=1):
                if not isinstance(m, dict) or not em_vocabulario(m.get("tipo"), TIPOS_META) \
                        or not _numero(m.get("valor")) or not _inteiro(m.get("prazo")):
                    erros.append(f"perfil: meta #{i} inválida — exige tipo em {sorted(TIPOS_META)}, valor numérico e prazo (ano)")
    vetadas = meta.get("classes-vetadas")
    if "classes-vetadas" in meta:
        if not isinstance(vetadas, list) or not all(em_vocabulario(c, CLASSES) for c in vetadas):
            erros.append(f"perfil: classes-vetadas deve ser lista (pode ser vazia) de blocos em {sorted(CLASSES)}")
    try:
        rubrica = ler_rubrica()
    except ValueError as e:
        return erros + [f"perfil: {e}"], []
    if base_ok and em_vocabulario(meta.get("risco-testado"), RISCOS):
        esperado = classificar_risco(base, rubrica)
        if meta["risco-testado"] != esperado:
            erros.append(f"perfil: risco-testado {meta['risco-testado']!r} diverge da tabela do método — "
                         f"as respostas {base} classificam como {esperado!r}")
    provisoria = meta.get("funcao-objetivo-provisoria")
    degrau = meta.get("degrau-if")
    if "custo-vida-mensal" in meta and custo is None:
        if provisoria is not True:
            erros.append("perfil: custo-vida-mensal null exige funcao-objetivo-provisoria: true")
        if degrau is not None:
            erros.append("perfil: sem custo de vida medido, degrau-if tem que ser null")
    elif _numero(custo):
        esperado = degrau_if(custo, taxa_retirada(rubrica))
        if not _inteiro(degrau) or abs(degrau - esperado) > TOLERANCIA_DEGRAU:
            erros.append(f"perfil: degrau-if {degrau!r} diverge da conta do método — "
                         f"{custo} × 12 ÷ {taxa_retirada(rubrica)} = {esperado}")
        if provisoria is not False:
            erros.append("perfil: com custo de vida medido, funcao-objetivo-provisoria tem que ser false")
    return erros, []
