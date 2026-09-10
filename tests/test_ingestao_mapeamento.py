from pathlib import Path

import pytest
import yaml

from po.ingestao.mapeamento import (carregar_mapeamento, detectar_mapeamento, listar_mapeamentos,
                                    resolver_mapeamento, validar_mapeamento)

MOTOR = Path(__file__).resolve().parent.parent

MAPA_OK = {
    "nome": "teste", "versao": 1, "descricao": "x",
    "arquivo": {"formato": "csv"},
    "datas": {"formatos": ["%d/%m/%Y"]},
    "conta": "corretora-br", "moeda": "BRL",
    "colunas": {"data": "Data", "descricao": "Histórico", "valor": "Valor", "saldo": "Saldo"},
    "linhas": [
        {"quando": {"descricao": r"^RENDIMENTO (?P<ticker>[A-Z0-9]{4,6})$"}, "destino": "proventos",
         "campos": {"tipo": "rendimento", "valor_bruto": "{valor}", "valor_liquido": "{valor}"}},
        {"quando": {"descricao": "^TED"}, "destino": "ignorar", "motivo": "caixa"},
    ],
    "conciliacao": {"tipo": "saldo-corrente", "valor": "valor", "saldo": "saldo", "ordem": "decrescente"},
}


def test_mapa_ok():
    assert validar_mapeamento(MAPA_OK) == []


def test_sem_conciliacao_e_recusado():
    m = dict(MAPA_OK)
    del m["conciliacao"]
    assert any("conciliação" in e for e in validar_mapeamento(m))


def test_destino_desconhecido():
    m = dict(MAPA_OK, linhas=[{"quando": {"descricao": "x"}, "destino": "contas"}])
    assert any("destino" in e for e in validar_mapeamento(m))


def test_campo_fora_do_schema():
    m = dict(MAPA_OK, linhas=[{"quando": {"descricao": "x"}, "destino": "proventos", "campos": {"yield": "1"}}])
    assert any("'yield'" in e for e in validar_mapeamento(m))


def test_template_com_apelido_inexistente():
    m = dict(MAPA_OK, linhas=[{"quando": {"descricao": "x"}, "destino": "proventos",
                               "campos": {"valor_bruto": "{montante}"}}])
    assert any("{montante}" in e for e in validar_mapeamento(m))


def test_grupo_nomeado_de_regex_vale_como_apelido():
    m = dict(MAPA_OK, linhas=[{"quando": {"descricao": r"^X (?P<montante>\d+)$"}, "destino": "proventos",
                               "campos": {"valor_bruto": "{montante}"}}])
    assert validar_mapeamento(m) == []


def test_regex_invalida():
    m = dict(MAPA_OK, linhas=[{"quando": {"descricao": "("}, "destino": "ignorar", "motivo": "x"}])
    assert any("regex inválida" in e for e in validar_mapeamento(m))


def test_ignorar_exige_motivo_e_ajuste_exige_chave():
    m = dict(MAPA_OK, linhas=[{"quando": {"descricao": "x"}, "destino": "ignorar"},
                              {"quando": {"descricao": "y"}, "destino": "ajuste", "aplica-em": "proventos", "valor": "{valor}"}])
    erros = validar_mapeamento(m)
    assert any("motivo" in e for e in erros) and any("chave" in e for e in erros)


def test_saldo_corrente_exige_apelidos():
    m = dict(MAPA_OK, conciliacao={"tipo": "saldo-corrente", "valor": "valor", "saldo": "balanco"})
    assert any("conciliacao.saldo" in e for e in validar_mapeamento(m))


def test_total_declarado_exige_origem():
    m = dict(MAPA_OK, conciliacao={"tipo": "total-declarado", "soma": "qty*pm"})
    assert any("origem" in e for e in validar_mapeamento(m))


def test_datas_extrair_exige_um_grupo():
    m = dict(MAPA_OK, datas={"formatos": ["%m/%d/%Y"], "extrair": r"^\S+"})
    assert any("datas.extrair" in e and "um grupo" in e for e in validar_mapeamento(m))
    m = dict(MAPA_OK, datas={"formatos": ["%m/%d/%Y"], "extrair": "("})
    assert any("datas.extrair" in e and "inválida" in e for e in validar_mapeamento(m))
    m = dict(MAPA_OK, datas={"formatos": ["%m/%d/%Y"], "extrair": r"^(\S+)"})
    assert validar_mapeamento(m) == []


def test_datas_formatos_com_diretiva_invalida():
    m = dict(MAPA_OK, datas={"formatos": ["%Q"]})
    assert any("datas.formatos" in e and "strptime" in e for e in validar_mapeamento(m))


def test_carregar_arquivo_invalido(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text("nome: x\nversao: 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapeamento inválido"):
        carregar_mapeamento(p)


def test_resolver_por_nome_workspace_sobrepoe_motor(tmp_path):
    ws = tmp_path / "ws"
    (ws / "mapeamentos").mkdir(parents=True)
    motor = tmp_path / "motor"
    (motor / "mapeamentos").mkdir(parents=True)
    (motor / "mapeamentos" / "a.yaml").write_text(yaml.safe_dump(MAPA_OK), encoding="utf-8")
    (motor / "mapeamentos" / "b.yaml").write_text(yaml.safe_dump(MAPA_OK), encoding="utf-8")
    (ws / "mapeamentos" / "a.yaml").write_text(yaml.safe_dump(MAPA_OK), encoding="utf-8")
    assert resolver_mapeamento("a", ws, motor) == ws / "mapeamentos" / "a.yaml"
    assert resolver_mapeamento("b", ws, motor) == motor / "mapeamentos" / "b.yaml"
    assert set(listar_mapeamentos(ws, motor)) == {"a", "b"}
    with pytest.raises(FileNotFoundError, match="disponíveis"):
        resolver_mapeamento("c", ws, motor)
    caminho = ws / "mapeamentos" / "a.yaml"
    assert resolver_mapeamento(str(caminho), ws, motor) == caminho


def test_detectar_por_assinatura_do_cabecalho(tmp_path):
    ws = tmp_path / "ws"
    motor = tmp_path / "motor"
    (motor / "mapeamentos").mkdir(parents=True)
    ws.mkdir()
    m = dict(MAPA_OK, detectar={"cabecalho-contem": ["Histórico", "Saldo"]})
    (motor / "mapeamentos" / "banco.yaml").write_text(yaml.safe_dump(m), encoding="utf-8")
    doc = tmp_path / "extrato.csv"
    doc.write_text("Data,Histórico,Valor,Saldo\n20/08/2026,TED,1,1\n", encoding="utf-8")
    assert detectar_mapeamento(doc, ws, motor) == motor / "mapeamentos" / "banco.yaml"
    outro = tmp_path / "outro.csv"
    outro.write_text("a,b\n1,2\n", encoding="utf-8")
    assert detectar_mapeamento(outro, ws, motor) is None


@pytest.mark.parametrize("campo,valor", [
    ("moeda", ["BRL"]), ("conta", {"id": "x"}), ("nome", ["x"]), ("versao", [1]),
])
def test_valor_em_bloco_yaml_nao_levanta_so_reprova(campo, valor):
    """`moeda:\n  - BRL` é um erro de digitação comum em YAML; tem que virar frase, não TypeError."""
    assert validar_mapeamento(dict(MAPA_OK, **{campo: valor}))


def test_shapes_nao_hashaveis_em_todo_lugar_nao_levantam():
    m = dict(MAPA_OK, arquivo={"formato": ["csv"]}, moeda=["BRL"],
             linhas=[{"quando": {"descricao": "x"}, "destino": ["proventos"]},
                     {"quando": {"descricao": "y"}, "destino": "ajuste", "aplica-em": ["proventos"],
                      "chave": ["data"], "valor": "{valor}"}],
             conciliacao={"tipo": ["saldo-corrente"], "valor": ["valor"], "saldo": "saldo"})
    erros = validar_mapeamento(m)          # não levanta
    assert any("formato" in e for e in erros) and any("moeda" in e for e in erros)
    assert any("destino" in e for e in erros) and any("conciliacao" in e for e in erros)


def test_carregar_mapeamento_com_bloco_yaml_vira_value_error(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text("nome: x\nversao: 1\nmoeda:\n  - BRL\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapeamento inválido"):
        carregar_mapeamento(p)
