"""A rubrica perfil → bandas é dado do motor. Estes testes cobram os invariantes dela, não os
números: soma 100, ordem mín ≤ alvo ≤ máx, blocos no vocabulário, cobertura do espaço de perfil
sem buraco nem sobreposição, e as três regras de parâmetro (taxa, reserva, risco testado)."""
import copy
import itertools

import pytest

from po.csvs import CLASSES
from po.metodo import (
    ALTERNATIVAS, RESPOSTAS_CENARIO, aplicar_reserva, classificar_risco, degrau_if,
    ler_rubrica, selecionar_faixa, taxa_retirada,
)


@pytest.fixture(scope="module")
def rubrica():
    return ler_rubrica()


def test_rubrica_tem_nove_faixas_com_tres_alternativas(rubrica):
    assert len(rubrica["faixas"]) == 9
    for f in rubrica["faixas"]:
        assert set(f["alternativas"]) == set(ALTERNATIVAS), f["id"]


def test_toda_alternativa_soma_100_e_respeita_a_ordem(rubrica):
    for f in rubrica["faixas"]:
        for nome, alt in f["alternativas"].items():
            bandas = alt["bandas"]
            assert set(bandas) == CLASSES, f"{f['id']}/{nome}: blocos {sorted(bandas)}"
            soma = sum(v[1] for v in bandas.values())
            assert round(abs(soma - 100), 6) <= 0.05, f"{f['id']}/{nome} soma {soma}"
            for bloco, (mn, alvo, mx) in bandas.items():
                assert 0 <= mn <= alvo <= mx <= 100, f"{f['id']}/{nome}/{bloco}: {mn}/{alvo}/{mx}"
            assert set(alt["caps"]) == {"ativo", "setor"}


def test_faixas_cobrem_horizonte_x_risco_sem_buraco_nem_sobreposicao(rubrica):
    """Todo perfil válido cai em exatamente uma faixa. Horizonte de 0 a 60 anos, os três riscos."""
    for anos, risco in itertools.product(range(0, 61), ("baixo", "medio", "alto")):
        # conta as faixas que CASAM, não a que selecionar_faixa devolve: ela devolve a primeira,
        # e uma sobreposição passaria em silêncio se o teste olhasse só o resultado dela
        candidatas = [f["id"] for f in rubrica["faixas"]
                      if f["risco-testado"] == risco
                      and f["horizonte-anos"].get("min", 0) <= anos <= f["horizonte-anos"].get("max", 10**6)]
        assert len(candidatas) == 1, f"horizonte {anos}, risco {risco}: faixas {candidatas}"
        assert selecionar_faixa(rubrica, anos, risco)["id"] == candidatas[0]


def test_selecionar_faixa_recusa_risco_fora_do_vocabulario(rubrica):
    with pytest.raises(ValueError, match="risco-testado"):
        selecionar_faixa(rubrica, 30, "altissimo")


def test_classificar_risco_fecha_o_dominio_e_acerta_os_casos_nomeados(rubrica):
    """Duas coisas distintas. O laço das 64 combinações só prende o domínio: nenhuma levanta
    exceção e nenhuma devolve algo fora das três classes. Quem confere a classificação em si são
    as quatro asserções nomeadas abaixo, uma por regra da tabela."""
    for base in itertools.product(sorted(RESPOSTAS_CENARIO), repeat=3):
        assert classificar_risco(list(base), rubrica) in {"baixo", "medio", "alto"}, base
    assert classificar_risco(["vende-tudo", "vende-tudo", "mantem"], rubrica) == "baixo"
    assert classificar_risco(["aporta-mais", "aporta-mais", "mantem"], rubrica) == "alto"
    assert classificar_risco(["aporta-mais", "aporta-mais", "vende-tudo"], rubrica) == "medio"
    assert classificar_risco(["mantem", "mantem", "mantem"], rubrica) == "medio"


def test_classificar_risco_recusa_resposta_fora_do_vocabulario(rubrica):
    with pytest.raises(ValueError, match="cenário"):
        classificar_risco(["mantem", "chuta", "mantem"], rubrica)


def test_degrau_if_e_a_conta_do_metodo(rubrica):
    assert taxa_retirada(rubrica) == 0.0325
    assert degrau_if(7000, taxa_retirada(rubrica)) == 2584615     # 84.000 / 0,0325 = 2.584.615,38
    # um custo cuja divisão cai acima do meio: arredonda para cima, não trunca
    assert degrau_if(1000, taxa_retirada(rubrica)) == 369231      # 12.000 / 0,0325 = 369.230,77


def test_aplicar_reserva_sobe_caixa_tira_de_rf_br_e_mantem_soma(rubrica):
    faixa = selecionar_faixa(rubrica, 30, "alto")
    agressiva = faixa["alternativas"]["agressiva"]
    ajustada = aplicar_reserva(agressiva, reserva_meses=3, rubrica=rubrica)
    assert ajustada["bandas"]["caixa"] == [5, 10, 20]        # era [0, 5, 15], subiu 5
    assert ajustada["bandas"]["rf-br"] == [0, 5, 15]         # era [0, 10, 20], desceu 5
    assert sum(v[1] for v in ajustada["bandas"].values()) == 100
    assert agressiva["bandas"]["caixa"] == [0, 5, 15]        # a original não muda
    # Segunda faixa, porque em longo-alto/agressiva a conta errada coincide com a certa: ler de
    # `caixa` já somada e subtrair delta devolve o mesmo [0, 5, 15] que ler de `rf-br`. Dos sete
    # casos em que a regra dispara, esse é o único cego. longo-medio/agressiva distingue.
    outra = selecionar_faixa(rubrica, 30, "medio")["alternativas"]["agressiva"]
    ajustada2 = aplicar_reserva(outra, reserva_meses=3, rubrica=rubrica)
    assert ajustada2["bandas"]["caixa"] == [5, 10, 20]       # era [0, 5, 15]
    assert ajustada2["bandas"]["rf-br"] == [5, 15, 25]       # era [10, 20, 30]
    assert sum(v[1] for v in ajustada2["bandas"].values()) == 100


def test_aplicar_reserva_sem_efeito_com_reserva_suficiente_ou_caixa_ja_no_piso(rubrica):
    faixa = selecionar_faixa(rubrica, 30, "alto")
    agressiva = faixa["alternativas"]["agressiva"]
    assert aplicar_reserva(agressiva, reserva_meses=6, rubrica=rubrica) == agressiva
    conservadora = faixa["alternativas"]["conservadora"]     # caixa já em 10
    assert aplicar_reserva(conservadora, reserva_meses=0, rubrica=rubrica) == conservadora


def test_classificar_risco_resolve_empate_pela_ordem_baixo_vence_alto():
    """Com a rubrica do motor as duas regras são mutuamente exclusivas (3 respostas não cabem
    2 vende-tudo e 2 aporta-mais), então a ordem do laço só é observável numa rubrica de limiar
    1. Sem este teste, inverter a ordem em classificar_risco passa verde."""
    empate = {"parametros": {"risco-testado": {"baixo": {"resposta": "vende-tudo", "minimo": 1},
                                               "alto": {"resposta": "aporta-mais", "minimo": 1}}}}
    assert classificar_risco(["vende-tudo", "aporta-mais", "mantem"], empate) == "baixo"


def test_aplicar_reserva_devolve_copia_tambem_quando_nao_ha_o_que_ajustar(rubrica):
    """Os dois caminhos de saída antecipada devolviam o próprio objeto da rubrica. Como a rubrica
    é carregada uma vez por processo, quem mutasse o resultado corromperia a faixa para toda
    consulta seguinte, e nenhum teste via, porque os outros comparam por igualdade."""
    faixa = selecionar_faixa(rubrica, 30, "alto")
    for alt, meses in ((faixa["alternativas"]["agressiva"], 6),      # reserva suficiente
                       (faixa["alternativas"]["conservadora"], 0)):  # caixa já no piso
        devolvida = aplicar_reserva(alt, reserva_meses=meses, rubrica=rubrica)
        assert devolvida == alt and devolvida is not alt
        devolvida["bandas"]["caixa"][1] = 999
        assert alt["bandas"]["caixa"][1] != 999


def test_aplicar_reserva_recusa_piso_que_nao_cabe_no_alvo_de_rf_br(rubrica):
    """O `max(0, ...)` do deslocamento é um clamp silencioso: com piso alto demais o alvo de
    `rf-br` vai a zero, a perda não é compensada, e a alternativa sugerida deixa de somar 100. O
    usuário só descobriria depois, no check_politica do workspace dele, longe da causa."""
    esticada = copy.deepcopy(rubrica)
    esticada["parametros"]["reserva"]["caixa-minimo-sem-reserva"] = 18
    agressiva = selecionar_faixa(esticada, 30, "alto")["alternativas"]["agressiva"]
    with pytest.raises(ValueError, match="deixariam de somar 100"):
        aplicar_reserva(agressiva, reserva_meses=0, rubrica=esticada)


def test_aplicar_reserva_preserva_a_soma_em_toda_alternativa_da_rubrica(rubrica):
    """Contracheque da guarda acima contra o dado real: com o piso de hoje nenhuma das 27
    alternativas estoura. Se a guarda tiver o predicado errado, é aqui que aparece."""
    for faixa in rubrica["faixas"]:
        for nome, alt in faixa["alternativas"].items():
            ajustada = aplicar_reserva(alt, reserva_meses=0, rubrica=rubrica)
            soma = sum(v[1] for v in ajustada["bandas"].values())
            assert soma == 100, f"{faixa['id']}/{nome}: reserva aplicada soma {soma}"
            for bloco, (mn, alvo, mx) in ajustada["bandas"].items():
                assert 0 <= mn <= alvo <= mx <= 100, f"{faixa['id']}/{nome}/{bloco}: {mn}/{alvo}/{mx}"
