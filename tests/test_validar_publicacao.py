"""O oitavo check: publicar o workspace é ato declarado, nunca default.

O erro catastrófico do usuário não é número errado, é `git push` do workspace para repositório
público — e o histórico do git não se apaga. Este check não impede o push (git não é do motor);
ele cobra que o remoto esteja DECLARADO no vault.config.yaml, para que publicar exija um gesto
consciente e datado.

O teste que mais importa aqui é `test_o_exemplo_nao_herda_o_remoto_do_motor`: sem o gate de
`git rev-parse --show-toplevel`, o check acusaria `exemplos/workspace-exemplo` de estar publicado
no remoto público do jabuti (medido: `git remote -v` de dentro dele devolve o remoto do motor), e
o validador do exemplo roda no pre-commit — ou seja, todo commit do repo ficaria bloqueado.
"""
import subprocess
from pathlib import Path

import pytest

from po.config import validar_config
from po.validar.check_publicacao import checar_publicacao, raiz_do_repo, remotos_de

from test_validar_dados import copia_exemplo

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "workspace-exemplo"
REMOTO = "https://github.com/estranho/meu-vault.git"


def _ws(tmp_path, *, com_git=True, remoto=None, declarado=None):
    ws = copia_exemplo(tmp_path)
    if declarado is not None:
        cfg = ws / "vault.config.yaml"
        texto = cfg.read_text(encoding="utf-8")
        alvo = "remoto-declarado: null"
        assert texto.count(alvo) == 1, texto.count(alvo)
        cfg.write_text(texto.replace(alvo, f"remoto-declarado: '{declarado}'"),
                       encoding="utf-8", newline="\n")
    if com_git:
        subprocess.run(["git", "init", "-q"], cwd=ws, check=True, capture_output=True)
        if remoto:
            subprocess.run(["git", "remote", "add", "origin", remoto],
                           cwd=ws, check=True, capture_output=True)
    return ws


def test_workspace_sem_git_e_silencio(tmp_path):
    """`--sem-git` é caminho suportado: sem repositório não há push a interceptar."""
    assert checar_publicacao(_ws(tmp_path, com_git=False)) == ([], [])


def test_workspace_com_git_e_sem_remoto_e_silencio(tmp_path):
    """Versionar localmente é o caminho recomendado e não expõe nada."""
    assert checar_publicacao(_ws(tmp_path)) == ([], [])


def test_remoto_nao_declarado_e_erro(tmp_path):
    erros, avisos = checar_publicacao(_ws(tmp_path, remoto=REMOTO))
    assert avisos == []
    assert len(erros) == 1
    assert REMOTO in erros[0]
    assert "privacidade.remoto-declarado" in erros[0]
    assert "PRIVACIDADE.md" in erros[0]


def test_remoto_declarado_confere_e_passa(tmp_path):
    assert checar_publicacao(_ws(tmp_path, remoto=REMOTO, declarado=REMOTO)) == ([], [])


def test_remoto_declarado_diferente_do_real_e_erro(tmp_path):
    """Declarar QUALQUER coisa não basta: o que vale é declarar a URL que está lá. Um workspace
    que trocou de remoto sem trocar a declaração é exatamente o caso que este check existe para
    pegar, e é o mais provável de todos (clone, fork, `git remote set-url`)."""
    erros, _ = checar_publicacao(
        _ws(tmp_path, remoto=REMOTO, declarado="https://github.com/estranho/outro.git"))
    assert len(erros) == 1 and REMOTO in erros[0]


def test_o_exemplo_nao_herda_o_remoto_do_motor():
    """Ver docstring do módulo. O `skip` existe para o verde valer alguma coisa: num clone sem
    remoto configurado este teste passaria por vacuidade, provando nada."""
    if not remotos_de(EXEMPLO):
        pytest.skip("este clone não tem remoto configurado: o teste não teria o que provar")
    assert raiz_do_repo(EXEMPLO) != EXEMPLO.resolve()
    assert checar_publicacao(EXEMPLO) == ([], [])


def test_config_ilegivel_e_silencio(tmp_path):
    """Config quebrada é assunto do check de dados, que nomeia a causa de origem. Aqui, dizer a
    mesma coisa de novo é ruído; e levantar seria traceback no validador."""
    ws = _ws(tmp_path, remoto=REMOTO)
    (ws / "vault.config.yaml").write_text("versao: [1\n", encoding="utf-8", newline="\n")
    assert checar_publicacao(ws) == ([], [])


def test_privacidade_com_shape_errado_e_erro_de_config():
    """YAML resolve lista e dict sem aspas. Nada disso pode derrubar o validador nem passar mudo."""
    base = {"versao": 1, "moeda_base": "BRL", "harness": ["claude-code"],
            "cotacoes": {"provider": "yahoo"},
            "contas": [{"id": "c", "moeda": "BRL"}],
            "caminhos": {"motor": ".."}}
    assert validar_config({**base, "privacidade": {"remoto-declarado": None}}) == []
    assert validar_config({**base, "privacidade": {"remoto-declarado": "https://x/y.git"}}) == []
    for ruim in (["https://x/y.git"], "https://x/y.git", {"remoto-declarado": [1]}):
        erros = validar_config({**base, "privacidade": ruim})
        assert any("privacidade" in e for e in erros), ruim


def test_privacidade_md_nomeia_as_tres_saidas():
    """O documento vale pelo que enumera. Guarda por SENTINELA em comentário HTML, como as duas
    que o repo já tem: ninguém parafraseia um comentário HTML, e ele não aparece no markdown
    renderizado. Prosa sobre o assunto satisfaria um `in` sobre a palavra e não prova nada."""
    texto = (Path(__file__).resolve().parent.parent / "PRIVACIDADE.md").read_text(encoding="utf-8")
    for saida in ("cotacoes", "llm", "git"):
        assert f"<!-- saida: {saida} -->" in texto, (
            f"PRIVACIDADE.md não enumera a saída {saida!r}. As três são o conteúdo do documento: "
            "o ticker que vai ao provider de cotação, o que você mostra à LLM, e o que você mesmo "
            "empurra para um remoto git. Omitir uma delas é a única forma de o documento mentir.")


# --- instalação no lugar: a pasta clonada é a da pessoa, e o remoto dela é o motor público ---

MOTOR_PUBLICO = "https://github.com/letsgetithipster/jabuti.git"
RAIZ = Path(__file__).resolve().parent.parent


def _no_lugar(tmp_path, *, gitignore=None, hooks=True):
    """Motor mínimo com instalação na raiz: o marcador do motor, o .gitignore dele (ou outro), o
    remoto público e os caminhos pessoais."""
    raiz = tmp_path / "jabuti"
    (raiz / "scripts").mkdir(parents=True)
    (raiz / "scripts" / "criar_workspace.py").write_text("", encoding="utf-8", newline="\n")
    texto = (RAIZ / ".gitignore").read_text(encoding="utf-8") if gitignore is None else gitignore
    (raiz / ".gitignore").write_text(texto, encoding="utf-8", newline="\n")
    subprocess.run(["git", "init", "-q"], cwd=raiz, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", MOTOR_PUBLICO], cwd=raiz, check=True)
    if hooks:
        subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=raiz, check=True)
    (raiz / "vault.config.yaml").write_text("versao: 1\n", encoding="utf-8", newline="\n")
    (raiz / "dados").mkdir()
    (raiz / "dados" / "fills.csv").write_text("x\n", encoding="utf-8", newline="\n")
    return raiz


def test_no_lugar_o_remoto_do_motor_nao_e_erro(tmp_path):
    """No lugar, o remoto é o jabuti público por construção. Cobrar declaração dele seria cobrar
    de todo usuário, e a proteção ali é outra: nada pessoal rastreado, tudo ignorado."""
    assert checar_publicacao(_no_lugar(tmp_path)) == ([], [])


def test_no_lugar_caminho_pessoal_rastreado_e_erro_com_o_comando(tmp_path):
    raiz = _no_lugar(tmp_path)
    subprocess.run(["git", "add", "-f", "dados/fills.csv", "vault.config.yaml"], cwd=raiz, check=True)
    erros, _ = checar_publicacao(raiz)
    assert len(erros) == 1, erros
    assert "dados/fills.csv" in erros[0] and "vault.config.yaml" in erros[0]
    assert 'git rm --cached -- "dados/fills.csv" "vault.config.yaml"' in erros[0]


def test_no_lugar_caminho_pessoal_fora_do_gitignore_e_erro(tmp_path):
    texto = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    assert texto.count("/dados/\n") == 1
    erros, _ = checar_publicacao(_no_lugar(tmp_path, gitignore=texto.replace("/dados/\n", "")))
    assert len(erros) == 1 and "dados/" in erros[0] and "git checkout -- .gitignore" in erros[0], erros


def test_no_lugar_sem_hooks_e_aviso_com_o_comando(tmp_path):
    erros, avisos = checar_publicacao(_no_lugar(tmp_path, hooks=False))
    assert erros == []
    assert len(avisos) == 1 and "git config core.hooksPath .githooks" in avisos[0], avisos
