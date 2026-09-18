"""As skills que leem o MCP da Finnest, presas ao esquema medido do servidor.

O servidor nao declara `outputSchema` e nao esta nesta suite: o que da para cobrar
mecanicamente e o lado de ca. Que nenhuma skill invente nome de tool, que nenhuma peca
escopo acima do teto declarado, que toda uma cheque atualidade antes de afirmar numero,
que nenhuma escreva na carteira canonica, e que nenhuma engorde alem do teto. Fonte:
tests/fixtures/openfinance/finnest-tools.json, medida em 12/09/2026 contra o servidor real.
"""
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ESQUEMA = json.loads((RAIZ / "tests" / "fixtures" / "openfinance" / "finnest-tools.json")
                     .read_text(encoding="utf-8"))
TOOLS = {t["name"] for t in ESQUEMA["tools"]}
VERBOS = {n.split("_")[0] for n in TOOLS}
TOKEN = re.compile(r"`(?:mcp__finnest__)?([a-z][a-z0-9_]*)`")
TETO_BYTES = 8192
# Fora do teto de escopo: mover dinheiro, mudar configuracao de movimentacao, e gerir
# conexao ou consentimento. DERIVADO do esquema, nunca digitado a mao: lista a mao apodrece
# no dia em que o servidor publicar a tool nova. Medido: 36 das 116.
FORA_DO_TETO = {n for n in TOOLS if "transfer" in n or "automation" in n or "boleto" in n
                or n.startswith(("sync_", "refresh_connection", "refresh_all", "connect_",
                                 "disconnect_", "remove_connection", "revoke_",
                                 "create_data_consent"))}


def _escopo_de_texto():
    return (sorted(RAIZ.glob("skills/*/SKILL.md"))
            + sorted((RAIZ / "templates" / "workspace").rglob("*.md"))
            + sorted(RAIZ.glob("docs/*.md")))


def _tools_citadas(texto):
    """Token entre crases que parece nome de tool: tem `_` e comeca com um verbo do esquema.
    Escopo restrito a .md de propria: `parse_valor` e `posicoes_de_fills` sao funcoes Python
    e cairiam aqui se a varredura pegasse .py."""
    return {t for t in TOKEN.findall(texto) if "_" in t and t.split("_")[0] in VERBOS}


def _skills_finnest():
    return sorted(p for p in RAIZ.glob("skills/*/SKILL.md")
                  if "finnest" in p.read_text(encoding="utf-8").lower())


def test_existe_pelo_menos_uma_skill_finnest():
    """Clamp anti-vacuidade: sem esta linha, as quatro guardas abaixo ficam verdes num repo
    onde nenhuma skill Finnest existe, e ficariam verdes se alguem apagasse todas."""
    assert _skills_finnest(), "nenhuma skill cita a Finnest: as guardas abaixo ficariam vazias"


def test_tool_finnest_citada_existe_no_esquema():
    """Nome de tool e afirmacao sobre um servidor que esta suite nao alcanca. A fixture e o
    unico contrato disponivel. Uma letra a mais e a skill manda a LLM chamar o que nao existe,
    e o erro so aparece na sessao da pessoa. Medido: 52 tokens casados hoje, zero invalidos."""
    faltando = []
    for p in _escopo_de_texto():
        for nome in sorted(_tools_citadas(p.read_text(encoding="utf-8"))):
            if nome not in TOOLS:
                faltando.append(f"{p.relative_to(RAIZ).as_posix()}: {nome}")
    assert faltando == [], "tool citada fora do esquema medido:\n  " + "\n  ".join(faltando)


def test_skill_finnest_nao_pede_escopo_acima_do_teto():
    """O motor usa `read:financial`. execute:transfers, manage:boletos, manage:automations e
    manage:connections ficam fora, e isso e o que torna a integracao segura de divulgar: o pior
    que uma alucinacao pode fazer e ler. Aqui isso deixa de ser postura e vira teste."""
    achados = [f"{p.parent.name}: {n}" for p in _skills_finnest()
               for n in sorted(_tools_citadas(p.read_text(encoding="utf-8")) & FORA_DO_TETO)]
    assert achados == [], "skill citando tool fora do teto read:financial:\n  " + "\n  ".join(achados)


def test_skill_finnest_declara_gate_limite_e_fronteira():
    for p in _skills_finnest():
        texto = p.read_text(encoding="utf-8")
        assert "get_data_freshness_status" in texto, f"{p.parent.name}: sem o gate de atualidade"
        assert "outputSchema" in texto, f"{p.parent.name}: sem o limite de forma da resposta"
        assert "não escreve em `dados/`" in texto, f"{p.parent.name}: sem a fronteira de escrita"


def test_skill_finnest_nao_cita_escritor_da_carteira():
    proibidos = ("importar_extrato.py", "anexar_csv", "dados/fills.csv", "dados/cotacoes.csv")
    achados = [f"{p.parent.name}: {t}" for p in _skills_finnest()
               for t in proibidos if t in p.read_text(encoding="utf-8")]
    assert achados == [], "skill Finnest citando escritor da carteira:\n  " + "\n  ".join(achados)


def test_skill_finnest_cabe_no_teto():
    """Teto declarado. Skill que estoura e caso especial que deveria ter descido para o CLI ou
    para a documentacao."""
    grandes = [f"{p.parent.name}: {p.stat().st_size} bytes" for p in _skills_finnest()
               if p.stat().st_size > TETO_BYTES]
    assert grandes == [], f"skill acima do teto de {TETO_BYTES} bytes:\n  " + "\n  ".join(grandes)


def test_skill_capacidade_cita_os_campos_do_perfil_que_ela_grava():
    """Mesmo defeito que test_campos_do_perfil_na_skill_batem_com_o_codigo pega no jabuti-init:
    a skill lista campos em prosa, e prosa nao tem quem a segure. Se OBRIGATORIOS renomear um
    destes quatro, a skill passa a mandar gravar campo que o validador nao cobra, ou a deixar de
    gravar um que ele cobra, e o erro so aparece no workspace da pessoa."""
    import sys
    sys.path.insert(0, str(RAIZ / "scripts"))
    from po.perfil import OBRIGATORIOS

    campos = {"custo-vida-mensal", "capacidade-aporte-mensal",
              "funcao-objetivo-provisoria", "degrau-if"}
    assert campos <= OBRIGATORIOS, f"campo fora de OBRIGATORIOS: {sorted(campos - OBRIGATORIOS)}"
    texto = (RAIZ / "skills" / "jabuti-capacidade" / "SKILL.md").read_text(encoding="utf-8")
    faltando = sorted(c for c in campos if f"`{c}`" not in texto)
    assert faltando == [], f"a skill nao cita os campos que grava: {faltando}"


VITRINE = RAIZ / "docs" / "finnest-skills.md"


def test_vitrine_cobre_toda_skill_finnest():
    """Duas vias. Skill sem linha na vitrine e capacidade que ninguem descobre, e o objetivo
    declarado da documentacao e mostrar o que da para fazer. Linha na vitrine sem pasta e
    promessa: o leitor cola um comando que nao existe.

    A linha e a da tabela "Em trinta segundos" (celula inicial `| `/jabuti-x` |`): a prosa da
    vitrine cita /jabuti-init e /jabuti-mes como vizinhos, e contar prosa faria o teste exigir
    que toda skill citada fosse Finnest. A prosa tem a guarda de baixo: skill citada em qualquer
    lugar da vitrine tem que estar instalada."""
    texto = VITRINE.read_text(encoding="utf-8")
    documentadas = set(re.findall(r"^\| `/(jabuti-[a-z]+)` \|", texto, re.MULTILINE))
    instaladas_finnest = {p.parent.name for p in _skills_finnest()}
    assert documentadas == instaladas_finnest, (
        f"so na vitrine: {sorted(documentadas - instaladas_finnest)}; "
        f"so em skills/: {sorted(instaladas_finnest - documentadas)}")
    citadas = set(re.findall(r"`/(jabuti-[a-z]+)`", texto))
    instaladas = {p.parent.name for p in RAIZ.glob("skills/*/SKILL.md")}
    assert citadas <= instaladas, f"a vitrine cita skill nao instalada: {sorted(citadas - instaladas)}"


def test_skill_finnest_aponta_para_a_vitrine():
    """A skill para quando a Finnest nao esta na sessao, e a frase que ela imprime tem que levar
    a algum lugar. Sem este teste, a vitrine e um arquivo que ninguem acha."""
    faltando = [p.parent.name for p in _skills_finnest()
                if "docs/finnest-skills.md" not in p.read_text(encoding="utf-8")]
    assert faltando == [], f"skill Finnest sem ponteiro para a vitrine: {faltando}"


def test_guardrails_declara_o_teto_de_escopo_e_a_fronteira_de_escrita():
    """O teto de escopo e o que torna a integracao segura de divulgar, e uma frase de vitrine nao
    basta: ela tem que estar no documento que o usuario le ANTES do primeiro uso. E a sentinela
    de 'nenhum provider ligado' fica ambigua no dia em que skills Finnest existirem, porque o
    leitor ve a Finnest sendo lida e a ressalva dizendo que nada esta ligado: a fronteira entre
    LER numa skill e ESCREVER em dados/ tem que estar escrita ao lado dela."""
    texto = (RAIZ / "GUARDRAILS.md").read_text(encoding="utf-8")
    assert "read:financial" in texto, "o GUARDRAILS nao declara o escopo que o motor pede"
    for fora in ("execute:transfers", "manage:boletos", "manage:automations", "manage:connections"):
        assert fora in texto, f"o GUARDRAILS nao declara {fora} como fora de escopo"
    paragrafos = [p for p in texto.split("\n\n") if "skill" in p and "dados/" in p and "não escreve" in p]
    assert paragrafos, ("nenhum paragrafo do GUARDRAILS diz que a skill que le um MCP nao escreve "
                        "em dados/ — sem isso a sentinela de provider nao ligado fica ambigua")


# Skills de bônus que medem o mês corrente ou uma intenção: o perfil guarda a média de três meses
# medida pela /jabuti-capacidade, e gravar ali a sobra de um mês ou um corte que ainda não
# aconteceu trocaria medição por desejo. A /jabuti-capacidade fica FORA de propósito: ela grava.
BONUS_QUE_NAO_GRAVAM_PERFIL = ("jabuti-sobra",)


def test_bonus_de_aporte_nao_grava_no_perfil():
    """A fronteira que separa as skills de aporte da /jabuti-capacidade vira cobrança mecânica,
    do mesmo jeito que a de `dados/`: a skill tem de existir e declarar que não grava no perfil."""
    for nome in BONUS_QUE_NAO_GRAVAM_PERFIL:
        arq = RAIZ / "skills" / nome / "SKILL.md"
        assert arq.exists(), f"{nome}: skill ausente"
        texto = arq.read_text(encoding="utf-8")
        assert "não grava no perfil" in texto, f"{nome}: sem a fronteira do perfil"
