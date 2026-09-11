from pathlib import Path

import pytest

from po.config import (
    caminho_planilhas,
    carregar_config,
    moedas_por_conta,
    provider_cambio,
    validar_config,
)

CFG_OK = {
    "versao": 1,
    "idioma": "pt-BR",
    "moeda_base": "BRL",
    "harness": ["claude-code"],
    "cotacoes": {"provider": "manual"},
    "contas": [{"id": "corretora-br", "nome": "Corretora BR", "moeda": "BRL"}],
    "caminhos": {"motor": "C:/Workspace/mesa-propria"},
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


def test_moeda_base_invalida():
    cfg = dict(CFG_OK, moeda_base="USD")
    assert any("moeda_base" in e for e in validar_config(cfg))


def test_harness_invalido():
    cfg = dict(CFG_OK, harness=["gemini-cli"])
    assert any("harness" in e for e in validar_config(cfg))


def test_config_nao_dict():
    assert any("mapeamento" in e for e in validar_config("apenas texto"))


def test_conta_sem_id():
    cfg = dict(CFG_OK, contas=[{"nome": "X"}, "corretora"])
    erros = validar_config(cfg)
    assert sum("sem id" in e for e in erros) == 2


def test_carregar_invalida_levanta_value_error(tmp_path):
    (tmp_path / "vault.config.yaml").write_text("versao: 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="config inválida"):
        carregar_config(tmp_path)


def test_carregar_yaml_malformado(tmp_path):
    (tmp_path / "vault.config.yaml").write_text("versao: [1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="malformado"):
        carregar_config(tmp_path)


def test_carregar_yaml_escalar(tmp_path):
    (tmp_path / "vault.config.yaml").write_text("apenas texto\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapeamento"):
        carregar_config(tmp_path)


def test_harness_com_entrada_nao_string():
    cfg = dict(CFG_OK, harness=[{"claude-code": None}])
    assert any("harness" in e for e in validar_config(cfg))


def test_conta_com_id_nao_string():
    cfg = dict(CFG_OK, contas=[{"id": ["a"]}, {"id": {"x": "y"}}])
    erros = validar_config(cfg)
    assert sum("sem id" in e for e in erros) == 2


def test_carregar_nao_utf8(tmp_path):
    (tmp_path / "vault.config.yaml").write_bytes("versao: 1  # ação\n".encode("latin-1"))
    with pytest.raises(ValueError, match="UTF-8"):
        carregar_config(tmp_path)


def test_carregar_harness_dois_pontos_perdido(tmp_path):
    (tmp_path / "vault.config.yaml").write_text(
        "versao: 1\nmoeda_base: BRL\nharness:\n  - claude-code:\n"
        "cotacoes: {provider: manual}\n"
        "contas:\n  - id: c1\n    nome: C1\n    moeda: BRL\n"
        "caminhos: {motor: /x}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="config inválida"):
        carregar_config(tmp_path)


def test_conta_sem_moeda_e_erro():
    cfg = dict(CFG_OK, contas=[{"id": "c1", "nome": "C1"}])
    assert any("c1" in e and "moeda" in e for e in validar_config(cfg))


def test_conta_com_moeda_invalida_e_erro():
    cfg = dict(CFG_OK, contas=[{"id": "c1", "nome": "C1", "moeda": "reais"}])
    assert any("moeda" in e for e in validar_config(cfg))


def test_brapi_e_provider_valido():
    cfg = dict(CFG_OK, cotacoes={"provider": "brapi"})
    assert validar_config(cfg) == []


def test_cambio_invalido_e_erro():
    cfg = dict(CFG_OK, cotacoes={"provider": "yahoo", "cambio": "chute"})
    assert any("cambio" in e for e in validar_config(cfg))


def test_defaults_de_cambio_e_planilhas(tmp_path):
    assert provider_cambio(CFG_OK) == "bcb-sgs"
    assert caminho_planilhas(tmp_path, CFG_OK) == tmp_path / "planilhas"
    absoluto = tmp_path / "onedrive" / "cockpit"
    cfg = dict(CFG_OK, cotacoes={"provider": "yahoo", "cambio": "yahoo"},
               caminhos={"motor": "x", "planilhas": str(absoluto)})
    assert provider_cambio(cfg) == "yahoo"
    assert caminho_planilhas(tmp_path, cfg) == absoluto
    assert caminho_planilhas(tmp_path, dict(CFG_OK, caminhos={"motor": "x", "planilhas": "~/cockpit"})) == Path.home() / "cockpit"


def test_moedas_por_conta():
    cfg = dict(CFG_OK, contas=[{"id": "br", "moeda": "BRL"}, {"id": "us", "moeda": "USD"}])
    assert moedas_por_conta(cfg) == {"br": "BRL", "us": "USD"}


def test_valores_em_lista_nao_levantam_so_reprovam():
    cfg = dict(CFG_OK, cotacoes={"provider": ["manual"], "cambio": ["bcb-sgs"]},
               contas=[{"id": "a", "moeda": ["BRL"]}, {"id": "b", "moeda": {"x": 1}}], moeda_base=["BRL"])
    erros = validar_config(cfg)
    assert any("provider" in e for e in erros) and any("cambio" in e for e in erros)
    assert any("'a'" in e and "moeda" in e for e in erros) and any("'b'" in e and "moeda" in e for e in erros)
    assert any("moeda_base" in e for e in erros)


VENENOS = [["x"], {"a": 1}, None, True, 7, 3.5, {1: "a", "b": 2}]


def _caminhos(obj, prefixo=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield prefixo + (k,)
            yield from _caminhos(v, prefixo + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield prefixo + (i,)
            yield from _caminhos(v, prefixo + (i,))


def _poe(obj, caminho, valor):
    import copy
    obj = copy.deepcopy(obj)
    alvo = obj
    for passo in caminho[:-1]:
        alvo = alvo[passo]
    alvo[caminho[-1]] = valor
    return obj


def test_validar_config_nunca_levanta_com_shape_nenhum():
    """Mesmo fuzz de tipos de tests/test_ingestao_mapeamento.py (validar_config e
    validar_mapeamento compartilham em_vocabulario e o mesmo contrato de nunca levantar)."""
    for caminho in _caminhos(CFG_OK):
        for veneno in VENENOS:
            try:
                validar_config(_poe(CFG_OK, caminho, veneno))
            except Exception as e:
                raise AssertionError(f"{'.'.join(map(str, caminho))} <- {veneno!r}: {type(e).__name__}: {e}")
