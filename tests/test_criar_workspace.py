import subprocess
from pathlib import Path

import pytest
import yaml

from criar_workspace import MOTOR, TEMPLATE, criar, instalar_skills
from po.csvs import TABELAS_DADOS


def test_cria_workspace_completo(tmp_path):
    destino = tmp_path / "meu-vault"
    criar(destino, com_git=False, data="2026-09-08")
    assert (destino / "vault.config.yaml").exists()
    # G1: dados/ nasce com as CINCO tabelas de TABELAS_DADOS e nenhuma outra. `posicoes`,
    # `indices` e `movimentacoes` saíram do template; se voltarem, este assert cai.
    assert sorted(p.name for p in (destino / "dados").glob("*.csv")) == \
        sorted(f"{t}.csv" for t in TABELAS_DADOS) and len(TABELAS_DADOS) == 5
    # Tabela de TABELAS_DADOS criada vazia pelo template: sem esta linha, nada provaria que
    # o arquivo novo chega a um workspace novo, e o check_dados dele só acusaria depois.
    assert (destino / "dados" / "ativos.csv").read_text(encoding="utf-8").strip() == "ticker,classe"
    assert (destino / "estado" / "SETUP.md").exists()
    assert (destino / ".githooks" / "pre-commit").exists()
    assert (destino / ".gitattributes").exists()
    assert (destino / ".gitignore").exists()          # renomeado de gitignore.template
    assert not (destino / "gitignore.template").exists()
    cfg_texto = (destino / "vault.config.yaml").read_text(encoding="utf-8")
    assert "__MOTOR__" not in cfg_texto
    assert "__CASA__" not in cfg_texto and "__USUARIO__" not in cfg_texto
    cfg = yaml.safe_load(cfg_texto)
    assert cfg["casa"]["nome"] and cfg["usuario"]["nome"] and cfg["coordenador"]["nome"] == "Otávio"
    assert Path(cfg["caminhos"]["motor"]).is_dir()    # aponta pro motor real


def test_substitui_data_nos_md(tmp_path):
    destino = tmp_path / "ws"
    criar(destino, com_git=False, data="2026-09-08")
    estado = (destino / "estado" / "ESTADO.md").read_text(encoding="utf-8")
    assert "__DATA__" not in estado
    assert "data-referencia: 2026-09-08" in estado
    sobras = [p for p in destino.rglob("*.md") if "__DATA__" in p.read_text(encoding="utf-8")]
    assert sobras == []


def test_recusa_destino_nao_vazio(tmp_path):
    destino = tmp_path / "ocupado"
    destino.mkdir()
    (destino / "x.txt").write_text("x")
    with pytest.raises(SystemExit):
        criar(destino, com_git=False)


@pytest.mark.slow
def test_com_git_configura_hookspath(tmp_path):
    destino = tmp_path / "com-git"
    criar(destino, com_git=True)
    assert (destino / ".git").exists()
    out = subprocess.run(["git", "config", "core.hooksPath"], cwd=destino,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == ".githooks"


def test_falha_no_git_limpa_destino(tmp_path, monkeypatch):
    def git_quebrado(*args, **kwargs):
        raise FileNotFoundError("git")
    monkeypatch.setattr("criar_workspace.subprocess.run", git_quebrado)
    destino = tmp_path / "ws-git-quebrado"
    with pytest.raises(SystemExit, match="git"):
        criar(destino, com_git=True)
    assert not destino.exists()


def test_motor_relativo(tmp_path):
    destino = tmp_path / "ws-rel"
    criar(destino, com_git=False, data="2026-09-08", motor="../..")
    cfg = yaml.safe_load((destino / "vault.config.yaml").read_text(encoding="utf-8"))
    assert cfg["caminhos"]["motor"] == "../.."


def test_destino_e_arquivo(tmp_path):
    arq = tmp_path / "arquivo.txt"
    arq.write_text("x")
    with pytest.raises(SystemExit, match="não é uma pasta"):
        criar(arq, com_git=False)


def test_instala_skills_no_workspace(tmp_path):
    destino = tmp_path / "ws"
    criar(destino, com_git=False, data="2026-09-08")
    instaladas = sorted(p.parent.name for p in (destino / ".claude" / "skills").glob("*/SKILL.md"))
    esperadas = sorted(p.parent.name for p in (MOTOR / "skills").glob("*/SKILL.md"))
    assert instaladas == esperadas and "jabuti-mes" in instaladas and "jabuti-importar" in instaladas
    assert "jabuti-cotacoes" not in instaladas, (
        "cotar é passo, não fim: a tradução dos códigos de saída mora nas skills que chamam "
        "o script, e não numa skill própria com um nome a mais para a pessoa memorizar")
    texto = (destino / ".claude" / "skills" / "jabuti-importar" / "SKILL.md").read_text(encoding="utf-8")
    assert texto == (MOTOR / "skills" / "jabuti-importar" / "SKILL.md").read_text(encoding="utf-8")


def test_so_skills_reinstala_em_workspace_existente(tmp_path):
    destino = tmp_path / "ws"
    criar(destino, com_git=False, data="2026-09-08")
    alvo = destino / ".claude" / "skills" / "jabuti-importar" / "SKILL.md"
    alvo.write_text("velho", encoding="utf-8")
    n = instalar_skills(destino)
    assert n >= 2 and alvo.read_text(encoding="utf-8") != "velho"


def test_so_skills_exige_workspace(tmp_path):
    with pytest.raises(SystemExit, match="não é um workspace"):
        instalar_skills(tmp_path)


def test_workspace_novo_valida_sem_erros(tmp_path):
    from po.validar import validar
    destino = tmp_path / "ws"
    criar(destino, com_git=False, data="2026-09-08")
    erros, avisos = validar(destino)
    assert erros == [] and avisos == [
        "perfil: ainda não preenchido (o /jabuti-init preenche)",
        "politica: nenhuma banda declarada ainda (o /jabuti-estrategia preenche a tabela)",
    ]


def test_yaml_str_sobrevive_a_nome_com_dois_pontos_e_a_nome_que_o_yaml_resolveria(tmp_path):
    """O nome da casa vai para dentro do vault.config.yaml como texto. Sem as aspas simples,
    "Casa: a minha" quebra o parse do arquivo inteiro (o workspace nasce ilegivel) e "on" volta
    do YAML como o bool True, que a validacao entao recusa. As duas pontas do mesmo defeito que
    em_vocabulario cobre na leitura, aqui na escrita."""
    from criar_workspace import _yaml_str

    for nome in ("minha casa de gestão", "Casa: a minha", "Casa d'Ana", "on", "sim", "2026"):
        lido = yaml.safe_load(f"casa:\n  nome: {_yaml_str(nome)}\n")["casa"]["nome"]
        assert lido == nome, f"{nome!r} voltou do YAML como {lido!r}"


def test_template_e_exemplo_carregam_exatamente_cinco_csv():
    """G1, a metade perdida da F1: o produto distribuía oito CSVs e o README ia afirmar "de 7
    para 5". Template e exemplo carregam exatamente o que TABELAS_DADOS exige — nem a tabela
    morta (`posicoes`, que a ingestão parou de gravar) nem as órfãs (`indices`, `movimentacoes`,
    sem escritor). O disco é a testemunha; SCHEMAS é forma, não distribuição."""
    esperado = sorted(f"{t}.csv" for t in TABELAS_DADOS)
    assert len(esperado) == 5
    for pasta in (TEMPLATE / "dados", MOTOR / "exemplos" / "workspace-exemplo" / "dados"):
        assert sorted(p.name for p in pasta.glob("*.csv")) == esperado, pasta
