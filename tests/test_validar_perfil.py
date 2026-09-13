"""O perfil é declaração da pessoa, escrita pela LLM. O que o validador cobra: campo presente e
tipado, vocabulário via em_vocabulario, e os dois derivados (degrau-if e risco-testado)
recalculados pela rubrica — a LLM nunca aplica taxa nem regra de memória."""
from pathlib import Path

from po.validar.check_perfil import checar_perfil

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"

FRONTMATTER_OK = """tipo: perfil
data-criacao: 2026-09-08
data-revisao: 2026-09-08
idade: 35
dependentes: 0
horizonte-anos: 30
custo-vida-mensal: 7000
funcao-objetivo-provisoria: false
capacidade-aporte-mensal: 2000
reserva-meses: 6
risco-declarado: moderado
risco-testado: medio
risco-testado-base: [mantem, mantem, mantem]
metas:
  - {tipo: independencia, valor: 2584615, prazo: 2056}
classes-vetadas: []
liquidez-minima-meses: 6
degrau-if: 2584615
"""


def _perfil(tmp_path, frontmatter: str):
    (tmp_path / "politica").mkdir(exist_ok=True)
    (tmp_path / "politica" / "00-perfil.md").write_text(
        f"---\n{frontmatter}---\n\n# Perfil\n\ncorpo\n", encoding="utf-8")
    return tmp_path


def _troca(linha_de: str, linha_para: str) -> str:
    assert FRONTMATTER_OK.count(linha_de) == 1, linha_de
    return FRONTMATTER_OK.replace(linha_de, linha_para)


def test_exemplo_sem_erros_nem_avisos():
    assert checar_perfil(EXEMPLO) == ([], [])


def test_perfil_valido_passa(tmp_path):
    assert checar_perfil(_perfil(tmp_path, FRONTMATTER_OK)) == ([], [])


def test_nao_preenchido_e_aviso_nao_erro(tmp_path):
    ws = _perfil(tmp_path, "tipo: perfil\ndata-criacao: 2026-09-08\ndata-revisao: 2026-09-08\n")
    erros, avisos = checar_perfil(ws)
    assert erros == [] and avisos == ["perfil: ainda não preenchido (o /jabuti-init preenche)"]


def test_arquivo_ausente_e_erro(tmp_path):
    erros, _ = checar_perfil(tmp_path)
    assert any("00-perfil.md" in e and "ausente" in e for e in erros)


def test_campo_ausente_e_erro(tmp_path):
    erros, _ = checar_perfil(_perfil(tmp_path, _troca("reserva-meses: 6\n", "")))
    assert any("reserva-meses" in e and "ausente" in e for e in erros)


def test_degrau_divergente_da_conta_e_erro(tmp_path):
    erros, _ = checar_perfil(_perfil(tmp_path, _troca("degrau-if: 2584615\n", "degrau-if: 2100000\n")))
    assert any("degrau-if" in e and "2584615" in e for e in erros)


def test_risco_testado_divergente_da_base_e_erro(tmp_path):
    fm = _troca("risco-testado-base: [mantem, mantem, mantem]\n",
                "risco-testado-base: [vende-tudo, vende-tudo, mantem]\n")
    erros, _ = checar_perfil(_perfil(tmp_path, fm))
    assert any("risco-testado" in e and "baixo" in e for e in erros)


def test_custo_desconhecido_exige_provisoria_e_degrau_nulo(tmp_path):
    fm = _troca("custo-vida-mensal: 7000\n", "custo-vida-mensal: null\n")
    fm = fm.replace("funcao-objetivo-provisoria: false", "funcao-objetivo-provisoria: true")
    fm = fm.replace("degrau-if: 2584615", "degrau-if: null")
    assert checar_perfil(_perfil(tmp_path, fm)) == ([], [])
    fm2 = _troca("custo-vida-mensal: 7000\n", "custo-vida-mensal: null\n")   # provisoria false, degrau preenchido
    erros, _ = checar_perfil(_perfil(tmp_path, fm2))
    assert any("funcao-objetivo-provisoria" in e for e in erros)
    assert any("degrau-if" in e and "null" in e for e in erros)


def test_valor_nao_string_em_vocabulario_vira_frase_nao_excecao(tmp_path):
    """YAML resolve lista, dict, bool e int sem aspas. Nada disso pode derrubar o validador."""
    fm = _troca("risco-declarado: moderado\n", "risco-declarado: [moderado]\n")
    fm = fm.replace("classes-vetadas: []", "classes-vetadas: cripto")          # string, não lista
    fm = fm.replace("metas:\n  - {tipo: independencia, valor: 2584615, prazo: 2056}\n", "metas: {}\n")
    fm = fm.replace("idade: 35", "idade: on")                                   # bool, não int
    erros, _ = checar_perfil(_perfil(tmp_path, fm))
    assert any("risco-declarado" in e for e in erros)
    assert any("classes-vetadas" in e for e in erros)
    assert any("metas" in e for e in erros)
    assert any("idade" in e for e in erros)


def test_valor_coagido_para_bool_explica_a_coacao(tmp_path):
    """Quem digita `idade: on` ve `lido: True` no erro, um valor que nunca escreveu: o YAML 1.1
    coage on/off/yes/no/true/false antes de o validador ver. A frase tem que explicar isso, senao
    reporta algo que a pessoa nao reconhece. Medido: `sim` e `nao` NAO coagem, entao ficam de fora
    da dica e o erro deles mostra a string mesmo."""
    erros, _ = checar_perfil(_perfil(tmp_path, _troca("idade: 35", "idade: on")))
    idade = [e for e in erros if "idade" in e]
    assert len(idade) == 1 and "verdadeiro/falso" in idade[0], erros

    ws = tmp_path / "outro"
    ws.mkdir()
    erros2, _ = checar_perfil(_perfil(ws, _troca("custo-vida-mensal: 7000", "custo-vida-mensal: sim")))
    custo = [e for e in erros2 if "custo-vida-mensal" in e]
    assert len(custo) == 1 and "verdadeiro/falso" not in custo[0], erros2


def test_todo_campo_obrigatorio_tem_checagem_propria_no_check_perfil():
    """OBRIGATORIOS e a lista de campos cobrados, e checar_perfil e uma sequencia plana de `if`,
    um por campo. Nada obriga quem acrescentar o campo 15 a escrever a checagem de tipo dele: o
    campo entraria cobrado so na presenca, e todos os testes continuariam verdes. Este meta-teste
    prende as duas pontas pelo fonte."""
    from po.perfil import OBRIGATORIOS

    fonte = (Path(__file__).resolve().parent.parent / "scripts" / "po" / "validar"
             / "check_perfil.py").read_text(encoding="utf-8")
    sem_checagem = sorted(c for c in OBRIGATORIOS if c not in fonte)
    assert sem_checagem == [], (
        f"campos em OBRIGATORIOS sem checagem propria em check_perfil.py: {sem_checagem}")
