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
    m = dict(MAPA_OK, linhas=[{"quando": {"descricao": r"^X (?P<ticker>[A-Z0-9]+) (?P<montante>\d+)$"},
                               "destino": "proventos",
                               "campos": {"tipo": "rendimento", "valor_bruto": "{montante}",
                                          "valor_liquido": "{montante}"}}])
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


def test_detectar_escalar_e_erro_nao_traceback():
    assert any("detectar deve ser" in e for e in validar_mapeamento(dict(MAPA_OK, detectar="banco")))


def test_detectar_cabecalho_contem_precisa_ser_lista():
    m = dict(MAPA_OK, detectar={"cabecalho-contem": "Saldo"})
    assert any("lista não-vazia" in e for e in validar_mapeamento(m))


def test_mapa_quebrado_na_pasta_nao_derruba_a_deteccao(tmp_path):
    """Um YAML ruim em mapeamentos/ não pode impedir a detecção de todos os outros."""
    import yaml
    (tmp_path / "mapeamentos").mkdir()
    (tmp_path / "mapeamentos" / "quebrado.yaml").write_text("nome: q\nversao: 1\ndetectar: banco\n", encoding="utf-8")
    bom = dict(MAPA_OK, detectar={"cabecalho-contem": ["Histórico", "Saldo"]})
    (tmp_path / "mapeamentos" / "bom.yaml").write_text(yaml.safe_dump(bom, allow_unicode=True), encoding="utf-8")
    doc = tmp_path / "extrato.csv"
    doc.write_text("Data,Histórico,Valor,Saldo\n20/08/2026,TED,1,1\n", encoding="utf-8")
    assert detectar_mapeamento(doc, tmp_path / "nada", tmp_path).stem == "bom"


@pytest.mark.parametrize("mapa,trecho", [
    (dict(MAPA_OK, colunass={"x": "y"}), "chave desconhecida 'colunass'"),
    (dict(MAPA_OK, arquivo={"formato": "csv", "cabecalho_contem": ["A"]}), "chave desconhecida 'cabecalho_contem'"),
])
def test_chave_desconhecida_e_erro(mapa, trecho):
    assert any(trecho in e for e in validar_mapeamento(mapa))


def test_apelido_nao_vaza_entre_regras():
    m = dict(MAPA_OK, linhas=[
        {"quando": {"descricao": r"^A (?P<ticker>\w+)$"}, "destino": "proventos",
         "campos": {"tipo": "rendimento", "valor_bruto": "{valor}", "valor_liquido": "{valor}"}},
        {"quando": {"descricao": "^B"}, "destino": "proventos",
         "campos": {"tipo": "rendimento", "ticker": "{ticker}", "valor_bruto": "{valor}", "valor_liquido": "{valor}"}}])
    assert any("{ticker}" in e for e in validar_mapeamento(m))


def test_regra_que_nao_preenche_o_destino_e_erro():
    m = dict(MAPA_OK, linhas=[{"quando": {"descricao": "x"}, "destino": "fills"}])
    assert any("não consegue preencher" in e for e in validar_mapeamento(m))


def test_ajuste_chave_fora_do_schema():
    m = dict(MAPA_OK, linhas=[{"quando": {"descricao": "x"}, "destino": "ajuste", "aplica-em": "proventos",
                               "chave": ["nao_existe"], "valor": "{valor}"}])
    assert any("ajuste.chave" in e and "fora do schema" in e for e in validar_mapeamento(m))


def test_soma_com_campo_que_nao_existe_no_destino():
    m = dict(MAPA_OK, linhas=[{"quando": {"ticker": "^[A-Z]"}, "destino": "posicoes"}],
             colunas={"ticker": "A", "classe": "B", "qty": "C", "pm": "D"},
             conciliacao={"tipo": "total-declarado", "soma": "quantidade*preco_medio", "origem": "flag"})
    assert any("conciliacao.soma cita" in e for e in validar_mapeamento(m))


def test_origem_coluna_e_apelido():
    m = dict(MAPA_OK, linhas=[{"quando": {"descricao": "^[A-Z]"}, "destino": "posicoes"}],
             colunas={"ticker": "A", "classe": "B", "qty": "C", "pm": "D", "investido": "Valor investido"},
             conciliacao={"tipo": "total-declarado", "soma": "qty*pm",
                          "origem": {"linha-contem": "Total", "coluna": "Valor investido"}})
    assert any("origem.coluna deve ser um apelido" in e for e in validar_mapeamento(m))


def test_carregar_mapeamento_de_diretorio(tmp_path):
    (tmp_path / "umdir").mkdir()
    with pytest.raises(FileNotFoundError):
        carregar_mapeamento(tmp_path / "umdir")


def test_origem_linha_contem_nao_hashavel_nao_levanta_so_reprova():
    """Probe adversarial (não veio da lista do coordenador): linha-contem também pode
    chegar como bloco YAML, e o check precisa recusar sem TypeError, como todo o resto da DSL."""
    m = dict(MAPA_OK, linhas=[{"quando": {"descricao": "^[A-Z]"}, "destino": "proventos",
                               "campos": {"tipo": "rendimento", "valor_bruto": "{valor}",
                                          "valor_liquido": "{valor}"}}],
             conciliacao={"tipo": "total-declarado", "soma": "valor_bruto",
                          "origem": {"linha-contem": ["Total"], "coluna": "valor"}})
    erros = validar_mapeamento(m)   # não levanta
    assert any("linha-contem" in e for e in erros)


def test_ajuste_aplica_em_nao_hashavel_nao_levanta_so_reprova():
    """Probe adversarial: aplica-em em bloco YAML não pode derrubar o check de chave que
    vem logo depois (achava alvo in DESTINOS_TABELA sem passar por em_vocabulario)."""
    m = dict(MAPA_OK, linhas=[{"quando": {"descricao": "x"}, "destino": "ajuste",
                               "aplica-em": ["proventos"], "chave": ["data"], "valor": "{valor}"}])
    erros = validar_mapeamento(m)   # não levanta
    assert any("aplica-em" in e for e in erros)


def test_soma_com_destino_de_regra_nao_hashavel_nao_levanta_so_reprova():
    """Probe adversarial: o cruzamento de conciliacao.soma refaz a varredura de regras.linhas
    e não pode quebrar quando uma regra tem destino em bloco YAML (destino já é erro à parte)."""
    m = dict(MAPA_OK, linhas=[{"quando": {"descricao": "x"}, "destino": ["proventos"]}],
             conciliacao={"tipo": "total-declarado", "soma": "valor_bruto", "origem": "flag"})
    erros = validar_mapeamento(m)   # não levanta
    assert any("destino" in e for e in erros)


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


def test_validar_mapeamento_nunca_levanta_com_shape_nenhum():
    """O mesmo defeito (hash/ordenação de valor do usuário) já voltou quatro vezes em lugares
    diferentes, e o grep pelo sintoma não achou o quarto. Este teste procura a CLASSE: troca
    cada caminho do mapa por cada shape venenoso e exige frase, nunca exceção."""
    for caminho in _caminhos(MAPA_OK):
        for veneno in VENENOS:
            try:
                validar_mapeamento(_poe(MAPA_OK, caminho, veneno))
            except Exception as e:
                raise AssertionError(f"{'.'.join(map(str, caminho))} <- {veneno!r}: {type(e).__name__}: {e}")


@pytest.mark.parametrize("bloco", [None, "arquivo", "datas", "colunas", "conciliacao"])
def test_chaves_desconhecidas_de_tipos_mistos_nao_levantam(bloco):
    """YAML resolve `on:` para bool e `2026:` para int; ordenar chaves de tipos mistos levantaria."""
    import copy
    m = copy.deepcopy(MAPA_OK)
    alvo = m if bloco is None else m[bloco]
    alvo.update({1: "a", "zzz": 2, True: 3})
    assert validar_mapeamento(m)      # reprova, não levanta
