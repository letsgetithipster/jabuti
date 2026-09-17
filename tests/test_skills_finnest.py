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
