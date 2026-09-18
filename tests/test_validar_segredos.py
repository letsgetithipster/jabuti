"""Segredo em arquivo versionado é o defeito mais caro de desfazer: uma vez commitado, ele
está no histórico de todo mundo que clonou. O check roda no validador e no pre-commit."""
import subprocess
from pathlib import Path

from po.validar.check_segredos import checar_segredos, parece_credencial
from test_validar_dados import copia_exemplo

RAIZ = Path(__file__).resolve().parent.parent


def _repo(tmp_path):
    """Workspace que é repositório git de verdade: só assim dá para testar o que o git ignora."""
    ws = copia_exemplo(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    return ws


def test_workspace_limpo_passa(tmp_path):
    erros, avisos = checar_segredos(copia_exemplo(tmp_path))
    assert erros == [] and avisos == []


def test_client_secret_no_config_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    cfg = ws / "vault.config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8")
                   + '\nopenfinance:\n  client_secret: "9f2b7c1d4e6a8b3f"\n', encoding="utf-8")
    erros, _ = checar_segredos(ws)
    assert any("vault.config.yaml" in e for e in erros)


def test_bearer_em_dados_e_erro(tmp_path):
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "anotacoes.txt").write_text(
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc", encoding="utf-8")
    erros, _ = checar_segredos(ws)
    assert any("anotacoes.txt" in e for e in erros)


def test_arquivo_ignorado_pelo_git_nao_e_conferido(tmp_path):
    """O nome deste teste só virou verdade com a emenda: antes, o check não falava com o git.
    `inbox/` é o caso concreto — é onde export bruto de corretora cai, e o .gitignore o cobre.

    A contraprova no fim não é cerimônia. A primeira versão deste teste usava `api_key,"..."`
    com vírgula, que o regex não casa (ele exige `:` ou `=`), então ela passava verde com o
    `inbox/` varrido ou não — teste decorativo. Afirmar que a linha É pega fora do `inbox/`
    é o que prende a diferença ao git, e não ao conteúdo."""
    ws = _repo(tmp_path)
    segredo = 'api_key: "9f2b7c1d4e6a8b3f"'
    (ws / "inbox" / "extrato.csv").write_text(segredo, encoding="utf-8")
    assert checar_segredos(ws)[0] == []

    (ws / "dados" / "fora-do-inbox.txt").write_text(segredo, encoding="utf-8")
    assert any("fora-do-inbox.txt" in e for e in checar_segredos(ws)[0])


def test_sem_git_o_inbox_volta_a_ser_conferido(tmp_path):
    """O outro lado do teste acima: sem `.git` não há `.gitignore` a honrar, e a varredura cobre
    tudo. Medido no pré-voo: mesmo arquivo, mesmo conteúdo, resultado oposto — e é o git que faz
    a diferença."""
    ws = copia_exemplo(tmp_path)      # sem git init
    (ws / "inbox" / "extrato.csv").write_text('api_key: "9f2b7c1d4e6a8b3f"', encoding="utf-8")
    assert any("extrato.csv" in e for e in checar_segredos(ws)[0])


def test_env_nao_e_conferido(tmp_path):
    """.env existe justamente para guardar segredo. Acusá-lo seria acusar a solução. Vale mesmo
    em workspace sem git, então não usa _repo."""
    ws = copia_exemplo(tmp_path)
    (ws / ".env").write_text('CLIENT_SECRET="9f2b7c1d4e6a8b3f"', encoding="utf-8")
    erros, _ = checar_segredos(ws)
    assert erros == []


def test_workspace_sem_git_ainda_e_conferido(tmp_path):
    """criar_workspace --sem-git é caso suportado. Sem .git não há gitignore a honrar, e a
    varredura cobre tudo — o que não pode é o check virar no-op silencioso."""
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "x.txt").write_text("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.aaaaaaaaaaaa",
                                        encoding="utf-8")
    erros, _ = checar_segredos(ws)
    assert any("x.txt" in e for e in erros)


def test_fallback_sem_git_poda_diretorio_de_ferramenta(tmp_path):
    """Medido num pré-voo: o fallback sem-git (`rglob("*")` plano) varria 1038 arquivos de
    `.git/` e 80 de `__pycache__/` à toa, em 3,81s — não incorreto, só desperdício. A poda por
    diretório não é espelho de `.gitignore` (ver docstring do módulo): só corta ferramenta
    (`.git`, `__pycache__`, `.pytest_cache`, `.venv`), nunca regra do usuário. Este teste prende
    o comportamento: segredo dentro de `__pycache__/` não deve ser achado."""
    ws = copia_exemplo(tmp_path)
    pycache = ws / "dados" / "__pycache__"
    pycache.mkdir()
    (pycache / "x.txt").write_text("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.aaaaaaaaaaaa",
                                   encoding="utf-8")
    erros, _ = checar_segredos(ws)
    assert not any("__pycache__" in e for e in erros)


def test_linha_que_ensina_o_usuario_nao_derruba_o_commit():
    """Medido no pré-voo: a deny-list de seis strings deixava passar 9 de 12 destas. O check
    roda no pre-commit, então falso positivo aqui treina o usuário a burlar a guarda."""
    for valor in ["your-key-here", "your-api-key", "COLE_AQUI_SUA_CHAVE", "<sua-chave>",
                  "<sua-senha>", "exemplo1234", "sua-senha-aqui", "seu-token-aqui",
                  "troque-aqui", "xxxxxxxxxxxx", "changeme123", "MINHA_CHAVE_AQUI"]:
        assert not parece_credencial(valor), f"{valor!r} é texto de documentação, não credencial"


def test_credencial_de_verdade_e_reconhecida():
    for valor in ["abc123def456", "9f2b7c1d4e6a8b3f", "Tr0ub4dor&3", "a1b2c3d4e5f6g7h8i9j0"]:
        assert parece_credencial(valor), f"{valor!r} tem cara de credencial e tem que acusar"


def test_forma_conhecida_nao_passa_por_escotilha_de_placeholder(tmp_path):
    """AKIAIOSFODNN7EXAMPLE contém a palavra "EXAMPLE" porque é o exemplo da própria AWS. Um
    AKIA real não é menos secreto por isso: forma conhecida é prova, e não pede escotilha."""
    ws = copia_exemplo(tmp_path)
    (ws / "dados" / "x.txt").write_text('api_key = "AKIAIOSFODNN7EXAMPLE"', encoding="utf-8")
    erros, _ = checar_segredos(ws)
    assert any("x.txt" in e for e in erros)


# --- instalação no lugar: a raiz é o motor, e o que o motor versiona não é da pessoa ---

SEGREDO = 'api_key: "9f2b7c1d4e6a8b3f"'


def _motor_instalado(tmp_path, *, com_git=True):
    """Motor mínimo com instalação na raiz: um teste do motor com credencial falsa de propósito
    (versionado), o .gitignore do motor de verdade e os caminhos pessoais."""
    raiz = tmp_path / "jabuti"
    (raiz / "scripts").mkdir(parents=True)
    (raiz / "scripts" / "criar_workspace.py").write_text("", encoding="utf-8", newline="\n")
    (raiz / "tests").mkdir()
    (raiz / "tests" / "test_x.py").write_text(f"SEGREDO = '{SEGREDO}'\n", encoding="utf-8",
                                              newline="\n")
    (raiz / ".gitignore").write_bytes((RAIZ / ".gitignore").read_bytes())
    if com_git:
        subprocess.run(["git", "init", "-q"], cwd=raiz, check=True)
        subprocess.run(["git", "add", "-A"], cwd=raiz, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-c",
                        "commit.gpgsign=false", "-c", "core.hooksPath=.git/hooks", "commit", "-q",
                        "-m", "motor"], cwd=raiz, check=True)
    (raiz / "vault.config.yaml").write_text("versao: 1\n", encoding="utf-8", newline="\n")
    (raiz / "dados").mkdir()
    return raiz


def test_no_lugar_o_teste_do_motor_nao_e_segredo_da_pessoa(tmp_path):
    """Sem o recorte, o validador da instalação no lugar acusaria a credencial falsa que a suíte do
    motor usa de propósito, e nenhuma instalação fecharia em zero erros."""
    raiz = _motor_instalado(tmp_path)
    (raiz / "dados" / "ignorado.txt").write_text(SEGREDO, encoding="utf-8", newline="\n")
    assert checar_segredos(raiz) == ([], [])


def test_no_lugar_arquivo_solto_ou_pessoal_forcado_e_conferido(tmp_path):
    raiz = _motor_instalado(tmp_path)
    (raiz / "notas.txt").write_text(SEGREDO, encoding="utf-8", newline="\n")   # solto: nem git, nem ignore
    (raiz / "dados" / "forcado.txt").write_text(SEGREDO, encoding="utf-8", newline="\n")
    subprocess.run(["git", "add", "-f", "dados/forcado.txt"], cwd=raiz, check=True)
    erros, _ = checar_segredos(raiz)
    assert any(e.startswith("notas.txt:") for e in erros), erros
    assert any(e.startswith("dados/forcado.txt:") for e in erros), erros
    assert not any("tests/" in e for e in erros), erros


def test_no_lugar_sem_git_confere_so_os_caminhos_pessoais(tmp_path):
    """Download em zip: sem git para dizer o que ele levaria, a varredura cobre o que é da
    pessoa, inteiro, e nunca o motor."""
    raiz = _motor_instalado(tmp_path, com_git=False)
    (raiz / "dados" / "x.txt").write_text(SEGREDO, encoding="utf-8", newline="\n")
    erros, _ = checar_segredos(raiz)
    assert [e.split(":")[0] for e in erros] == ["dados/x.txt"], erros
