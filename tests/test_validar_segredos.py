"""Segredo em arquivo versionado é o defeito mais caro de desfazer: uma vez commitado, ele
está no histórico de todo mundo que clonou. O check roda no validador e no pre-commit."""
import subprocess

from po.validar.check_segredos import checar_segredos, parece_credencial
from test_validar_dados import copia_exemplo


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
