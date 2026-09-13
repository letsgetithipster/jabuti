"""Alvo gerado diferente do que a fonte produz é erro que bloqueia commit — a lição do vault, onde
uma dessincronização deixou o app web com bandas erradas por seis semanas. Motor inacessível é
aviso: não dá para regenerar, e a regra é falhar alto sem bloquear quem não tem como cumprir."""
from pathlib import Path

from criar_workspace import criar
from po.validar import validar
from po.validar.check_harness import checar_harness
from test_validar_dados import copia_exemplo

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"


def test_exemplo_sem_erros_nem_avisos():
    assert checar_harness(EXEMPLO) == ([], [])


def test_arquivo_gerado_editado_a_mao_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    alvo = ws / "CLAUDE.md"
    alvo.write_text(alvo.read_text(encoding="utf-8") + "\nlinha editada à mão\n", encoding="utf-8")
    erros, _ = checar_harness(ws)
    assert any("CLAUDE.md" in e and "diverge" in e and "gerar_harness" in e for e in erros)


def test_arquivo_gerado_ausente_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / ".claude" / "rules" / "00-voz.md").unlink()
    erros, _ = checar_harness(ws)
    assert any("00-voz.md" in e and "ausente" in e for e in erros)


def test_motor_inacessivel_e_aviso_nao_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    cfg = ws / "vault.config.yaml"
    texto = cfg.read_text(encoding="utf-8")
    inicio = texto.index("motor: '")
    fim = texto.index("'", inicio + len("motor: '")) + 1
    cfg.write_text(texto[:inicio] + "motor: '/caminho/que/nao/existe'" + texto[fim:], encoding="utf-8")
    erros, avisos = checar_harness(ws)
    assert erros == [] and any("motor" in a and "harness" in a for a in avisos)


def test_workspace_novo_nasce_com_harness_valido(tmp_path):
    destino = tmp_path / "ws"
    criar(destino, com_git=False, data="2026-09-08", casa="Casa Nova", usuario="Bia")
    assert "Casa Nova" in (destino / "CLAUDE.md").read_text(encoding="utf-8")
    erros, avisos = validar(destino)
    assert erros == [] and not any("harness" in a for a in avisos)
