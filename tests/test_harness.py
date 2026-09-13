"""O harness é compilado: fonte em rules/ do motor + vault.config.yaml → alvo. Nunca editado à mão.
Estes testes cobram a compilação; o check que bloqueia deriva está em test_validar_harness.py."""
import shutil
from pathlib import Path

from po.harness import escrever_harness, renderizar_harness
from test_validar_dados import copia_exemplo

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"
MOTOR = EXEMPLO.parent.parent
ALVOS = {"CLAUDE.md", ".claude/rules/00-voz.md"}


def test_render_produz_os_dois_arquivos_com_os_nomes_da_config(tmp_path):
    ws = copia_exemplo(tmp_path)
    arquivos = renderizar_harness(ws)
    assert set(arquivos) == ALVOS
    assert "Casa Exemplo" in arquivos["CLAUDE.md"] and "Ana" in arquivos["CLAUDE.md"]
    assert "Otávio" in arquivos[".claude/rules/00-voz.md"]
    for texto in arquivos.values():
        assert "__CASA__" not in texto and "__USUARIO__" not in texto and "__COORDENADOR__" not in texto


def test_claude_md_lista_as_skills_instaladas_e_a_regra_de_sessao(tmp_path):
    ws = copia_exemplo(tmp_path)
    claude = renderizar_harness(ws)["CLAUDE.md"]
    esperadas = sorted(p.parent.name for p in (MOTOR / "skills").glob("*/SKILL.md"))
    for nome in esperadas:
        assert f"/{nome}" in claude, nome
    assert "estado/SETUP.md" in claude and "GUARDRAILS.md" in claude


def test_escrever_e_idempotente_e_instala_skills(tmp_path):
    """A arvore de skills e apagada antes de chamar: `copia_exemplo` copia o exemplo inteiro, e o
    exemplo ja tem `.claude/skills/` no disco (gitignorado, nao inexistente). Sem apagar, a
    assercao final e satisfeita pelo fixture e nao pelo codigo, e desligar instalar_skills passa
    verde. Cobra o conjunto inteiro das skills do motor, nao um arquivo so."""
    ws = copia_exemplo(tmp_path)
    shutil.rmtree(ws / ".claude" / "skills", ignore_errors=True)
    assert not (ws / ".claude" / "skills").exists()
    escritos = escrever_harness(ws)
    primeira = {p: p.read_bytes() for p in escritos}
    escrever_harness(ws)
    assert {p: p.read_bytes() for p in escritos} == primeira
    instaladas = {p.parent.name for p in (ws / ".claude" / "skills").glob("*/SKILL.md")}
    assert instaladas == {p.parent.name for p in (MOTOR / "skills").glob("*/SKILL.md")}


def test_exemplo_esta_regenerado_pelo_gerador():
    """O harness do exemplo é exatamente o que o gerador produz (drift = teste vermelho), como o
    ESTADO.md do exemplo já é."""
    esperado = renderizar_harness(EXEMPLO)
    for rel, texto in esperado.items():
        assert (EXEMPLO / rel).read_text(encoding="utf-8") == texto, rel


def test_alvo_reservado_nao_gera_arquivo(tmp_path):
    ws = copia_exemplo(tmp_path)
    cfg = ws / "vault.config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("harness: [claude-code]", "harness: [codex]"),
                   encoding="utf-8")
    assert renderizar_harness(ws) == {}
