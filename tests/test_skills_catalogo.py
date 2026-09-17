"""Consistência entre as skills que existem, o catálogo que as descreve e o SETUP.md que as
sequencia. O conjunto "skills de onboarding" é DERIVADO das linhas do SETUP.md do template, não
de lista à mão — e só elas têm a seção 'Próximo passo'."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SKILLS = RAIZ / "skills"
CATALOGO = (SKILLS / "README.md").read_text(encoding="utf-8")
SETUP_TEMPLATE = (RAIZ / "templates" / "workspace" / "estado" / "SETUP.md").read_text(encoding="utf-8")
SETUP_EXEMPLO = (RAIZ / "exemplos" / "workspace-exemplo" / "estado" / "SETUP.md").read_text(encoding="utf-8")
# Skills que o SETUP.md já sequencia mas que só nascem no spec 4b. Guarda de duas vias: quando a
# pasta existir, este conjunto tem que esvaziar, senão o teste abaixo acusa.
# Vazio de propósito. Enquanto o SETUP.md podia sequenciar skill "planejada", o onboarding
# terminava mandando colar /jabuti-micro, que não existe — no arquivo que abre toda sessão.
# A regra agora é uma só: nada é sequenciado sem estar instalado, então /jabuti-micro nasce no
# mesmo commit que o cita.
PLANEJADAS: set[str] = set()
LINHA_SKILL = re.compile(r"^- \[[ x]\] `/(jabuti-[a-z]+)", re.MULTILINE)
PROXIMO = re.compile(r"^Próximo: `/(jabuti-[a-z]+)", re.MULTILINE)


def _instaladas() -> set[str]:
    return {p.parent.name for p in SKILLS.glob("*/SKILL.md")}


def _de_onboarding() -> set[str]:
    return set(LINHA_SKILL.findall(SETUP_TEMPLATE))


def test_toda_skill_tem_linha_no_catalogo_e_toda_linha_tem_pasta():
    catalogadas = set(re.findall(r"`/(jabuti-[a-z]+)`", CATALOGO))
    assert catalogadas == _instaladas(), (
        f"catálogo e pastas divergem: só no catálogo {catalogadas - _instaladas()}, "
        f"só em skills/ {_instaladas() - catalogadas}")


def test_skills_de_onboarding_vem_do_setup_e_existem():
    assert _de_onboarding() == {"jabuti-init", "jabuti-estrategia", "jabuti-importar"}
    assert _de_onboarding() <= _instaladas()


def test_secao_proximo_passo_so_nas_skills_de_onboarding():
    for nome in _instaladas():
        texto = (SKILLS / nome / "SKILL.md").read_text(encoding="utf-8")
        tem = "## Próximo passo" in texto
        assert tem == (nome in _de_onboarding()), (
            f"{nome}: 'Próximo passo' {'presente' if tem else 'ausente'}, e a skill "
            f"{'é' if nome in _de_onboarding() else 'não é'} de onboarding")


def test_linha_proximo_aponta_para_skill_existente_ou_planejada():
    assert PLANEJADAS.isdisjoint(_instaladas()), (
        f"{PLANEJADAS & _instaladas()} já existe: esvazie PLANEJADAS")
    for nome_arq, texto in (("template", SETUP_TEMPLATE), ("exemplo", SETUP_EXEMPLO)):
        alvos = PROXIMO.findall(texto)
        assert len(alvos) == 1, f"SETUP.md do {nome_arq}: esperava uma linha 'Próximo:', achei {len(alvos)}"
        assert alvos[0] in _instaladas() | PLANEJADAS, f"SETUP.md do {nome_arq} aponta para {alvos[0]}"


def test_toda_skill_declara_o_que_nao_faz_e_tem_frases_gatilho():
    for nome in _instaladas():
        texto = (SKILLS / nome / "SKILL.md").read_text(encoding="utf-8")
        assert "## O que esta skill NÃO faz" in texto, nome
        assert texto.startswith("---\nname: " + nome + "\n"), f"{nome}: frontmatter sem name igual à pasta"
        assert f"/{nome}" in texto.split("---", 2)[1], f"{nome}: description sem a frase-gatilho /{nome}"


def test_campos_do_perfil_na_skill_batem_com_o_codigo():
    """Os 14 nomes de campo do perfil moram em po.perfil.OBRIGATORIOS e sao repetidos em quatro
    lugares. Tres apodrecem barulhento: mudar OBRIGATORIOS sem mexer no fixture, no exemplo ou no
    check quebra teste na hora. O quarto e esta SKILL, que os lista em prosa para a LLM seguir, e
    prosa nao tem quem a segure. Sem este teste, a skill manda gravar um conjunto de campos que o
    validador nao cobra mais, ou deixa de mandar gravar um que ele cobra."""
    import sys

    sys.path.insert(0, str(RAIZ / "scripts"))
    from po.perfil import OBRIGATORIOS

    texto = (SKILLS / "jabuti-init" / "SKILL.md").read_text(encoding="utf-8")
    citados = {c for c in OBRIGATORIOS if f"`{c}`" in texto}
    assert citados == OBRIGATORIOS, (
        f"campos em OBRIGATORIOS que a SKILL nao cita: {sorted(OBRIGATORIOS - citados)}")


def test_setup_do_template_nasce_com_tudo_aberto_e_aponta_a_primeira_etapa():
    """O template e o SETUP.md que todo workspace novo recebe. Uma linha `- [x]` ali faria a LLM
    tratar uma etapa como cumprida na primeira sessao de cada usuario novo, e o regex de
    LINHA_SKILL casa `[ ]` e `[x]` igual, entao os outros testes nao veem diferenca. O exemplo,
    ao contrario, tem marcacoes fechadas de proposito: e a fotografia de quem ja andou."""
    # ancorada em início de linha: o bloco de navegação do próprio SETUP.md explica os três
    # estados e cita `- [x]` em prosa, então um `in` cru casaria a documentação
    fechada = re.compile(r"^\s*- \[x\]", re.MULTILINE)
    assert not fechada.search(SETUP_TEMPLATE), "SETUP.md do template tem etapa ja marcada"
    assert PROXIMO.findall(SETUP_TEMPLATE) == ["jabuti-init"], (
        "SETUP.md do template deve apontar Próximo para a primeira etapa")
    assert fechada.search(SETUP_EXEMPLO), "SETUP.md do exemplo devia mostrar etapas ja cumpridas"


TETO_ROTINA = 8192


def test_a_skill_da_rotina_existe_e_nao_passa_do_teto():
    """Spec §4: o argumento contra três skills de rotina é que uma pergunta custa menos que dois
    nomes na memória. Se /jabuti-mes engordar, o argumento se vira contra ela, e a resposta certa
    é empurrar caso especial para dentro do CLI — não cortar a tradução de erro da skill."""
    arq = SKILLS / "jabuti-mes" / "SKILL.md"
    assert arq.exists(), "a rotina mensal é uma skill, e ela tem que existir em skills/"
    tamanho = arq.stat().st_size
    assert tamanho <= TETO_ROTINA, (
        f"jabuti-mes tem {tamanho} bytes e o teto declarado é {TETO_ROTINA}. "
        "Empurre caso especial para dentro do CLI em vez de engordar a skill.")


def test_setup_nao_sequencia_skill_que_nao_existe():
    """C2: o onboarding terminava em `Próximo: /jabuti-micro fiis`, e a skill não existe. Vale
    para o template E para o exemplo, que é o workspace que o estranho lê no GitHub sem clonar."""
    for nome_arq, texto in (("template", SETUP_TEMPLATE), ("exemplo", SETUP_EXEMPLO)):
        citadas = set(re.findall(r"`/(jabuti-[a-z]+)", texto))
        fora = sorted(citadas - _instaladas())
        assert fora == [], f"SETUP.md do {nome_arq} sequencia skill não instalada: {fora}"


def test_o_onboarding_do_exemplo_fecha_na_rotina():
    """Spec §2.1: depois do fecho comum a pessoa nunca mais lê o SETUP e nunca mais precisa de
    outro nome. O exemplo mostra isso: onboarding cumprido, `Próximo: /jabuti-mes`."""
    assert PROXIMO.findall(SETUP_EXEMPLO) == ["jabuti-mes"]
    assert not re.search(r"^\s*- \[ \]", SETUP_EXEMPLO, re.MULTILINE), (
        "o exemplo ainda tem etapa de onboarding aberta")
