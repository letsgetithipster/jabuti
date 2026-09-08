import pytest

from po.config import carregar_config, validar_config

CFG_OK = {
    "versao": 1,
    "idioma": "pt-BR",
    "moeda_base": "BRL",
    "harness": ["claude-code"],
    "cotacoes": {"provider": "manual"},
    "contas": [{"id": "corretora-br", "nome": "Corretora BR", "moeda": "BRL"}],
    "caminhos": {"motor": "C:/Workspace/patrimonio-os"},
}


def test_config_valida_sem_erros():
    assert validar_config(CFG_OK) == []


def test_versao_errada():
    cfg = dict(CFG_OK, versao=2)
    assert any("versao" in e for e in validar_config(cfg))


def test_conta_duplicada():
    cfg = dict(CFG_OK, contas=[{"id": "a"}, {"id": "a"}])
    assert any("duplicad" in e for e in validar_config(cfg))


def test_sem_contas():
    cfg = dict(CFG_OK, contas=[])
    assert any("conta" in e for e in validar_config(cfg))


def test_provider_desconhecido():
    cfg = dict(CFG_OK, cotacoes={"provider": "inventado"})
    assert any("provider" in e for e in validar_config(cfg))


def test_sem_caminho_motor():
    cfg = dict(CFG_OK, caminhos={})
    assert any("motor" in e for e in validar_config(cfg))


def test_carregar_de_arquivo(tmp_path):
    (tmp_path / "vault.config.yaml").write_text(
        "versao: 1\nidioma: pt-BR\nmoeda_base: BRL\n"
        "harness: [claude-code]\ncotacoes: {provider: manual}\n"
        "contas:\n  - id: c1\n    nome: C1\n    moeda: BRL\n"
        "caminhos: {motor: /x}\n",
        encoding="utf-8",
    )
    cfg = carregar_config(tmp_path)
    assert cfg["moeda_base"] == "BRL"


def test_carregar_sem_arquivo(tmp_path):
    with pytest.raises(FileNotFoundError):
        carregar_config(tmp_path)
