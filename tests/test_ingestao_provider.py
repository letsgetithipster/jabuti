"""Ingestão a partir de resposta de provider. O que distingue esta camada da ingestão de
documento é procedência: documento baixado é prova de si mesmo, resposta de API não é."""
import datetime
import json

import pytest

from po.ingestao.provider import arquivar_payload, conferir_status
from test_validar_dados import copia_exemplo

HOJE = datetime.date(2026, 9, 11)


def test_payload_cru_vira_artefato(tmp_path):
    """Sem o payload, 'origem rastreável' degenera em 'o provider disse'."""
    ws = copia_exemplo(tmp_path)
    bruto = {"transactions": [{"id": "a1", "amount": -89.9}], "referenceDateTime": "2026-09-11T03:00:00Z"}
    caminho = arquivar_payload(ws, "finnest", bruto, HOJE)
    assert caminho.exists()
    assert caminho.relative_to(ws).as_posix() == "logs/importacoes/2026-09-11-finnest.json"
    assert json.loads(caminho.read_text(encoding="utf-8")) == bruto


def test_duas_rodadas_no_mesmo_dia_nao_sobrescrevem(tmp_path):
    """A segunda sincronização do dia é outro evento e outra prova."""
    ws = copia_exemplo(tmp_path)
    a = arquivar_payload(ws, "finnest", {"n": 1}, HOJE)
    b = arquivar_payload(ws, "finnest", {"n": 2}, HOJE)
    assert a != b
    assert json.loads(a.read_text(encoding="utf-8")) == {"n": 1}
    assert json.loads(b.read_text(encoding="utf-8")) == {"n": 2}


def test_payload_com_caractere_nao_ascii_sobrevive(tmp_path):
    ws = copia_exemplo(tmp_path)
    caminho = arquivar_payload(ws, "finnest", {"desc": "PIX MERCADINHO SÃO JOÃO"}, HOJE)
    assert "SÃO JOÃO" in caminho.read_text(encoding="utf-8")


def test_status_degradado_para_a_rodada():
    """O pior modo de falha não é o provider cair: é ele devolver lista vazia sem erro porque
    uma conta parou de sincronizar, e o patrimônio encolher em silêncio."""
    erros = conferir_status([{"id": "c1", "nome": "Banco X", "status": "OK"},
                             {"id": "c2", "nome": "Banco Y", "status": "LOGIN_ERROR"}])
    assert len(erros) == 1
    assert "Banco Y" in erros[0] and "LOGIN_ERROR" in erros[0]


def test_status_todo_ok_nao_reclama():
    assert conferir_status([{"id": "c1", "nome": "Banco X", "status": "OK"}]) == []


def test_lista_de_conexoes_vazia_e_erro():
    """Nenhuma conexão não é 'tudo certo': é conta nenhuma conectada."""
    erros = conferir_status([])
    assert any("nenhuma conexão" in e for e in erros)


def test_status_desconhecido_e_tratado_como_degradado():
    """Vocabulário de status é do provider e muda sem aviso. Desconhecido não pode virar OK."""
    erros = conferir_status([{"id": "c1", "nome": "Banco X", "status": "SEI_LA"}])
    assert len(erros) == 1 and "SEI_LA" in erros[0]


# ---------------------------------------------------------------------------
# Acrescentados pelo pré-voo. Os sete testes acima passam com o módulo como o plano
# o escrevia; estes cinco não, e cobrem o que ele deixava aberto.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("conexao", ["banco-y", None, ["c1", "OK"], 7, 3.5])
def test_conexao_ilegivel_e_degradada_e_nao_traceback(conexao):
    """`conexoes` vem da resposta JSON do provider, que é a entrada menos confiável do sistema
    inteiro. `c.get("status")` num valor não-dict levanta AttributeError, e conferir_status é a
    PRECONDIÇÃO da ingestão: o usuário receberia traceback no lugar de "reconecte no app".

    Medido no pré-voo: 5 de 5 shapes levantavam. Conta cujo status não dá para ler não é conta
    sincronizada, então ela é degradada — mesma regra do status desconhecido."""
    erros = conferir_status([{"id": "c1", "nome": "Banco X", "status": "OK"}, conexao])
    assert len(erros) == 1
    assert type(conexao).__name__ in erros[0]


@pytest.mark.parametrize("conexoes", [None, "texto", 0, {"c1": "OK"}, {}])
def test_conexoes_que_nao_sao_lista_nao_levantam(conexoes):
    """Nem toda resposta malformada é uma lista malformada: a própria coleção pode vir errada."""
    erros = conferir_status(conexoes)
    assert any("nenhuma conexão" in e for e in erros)


def test_nome_de_provider_com_separador_e_recusado(tmp_path):
    """O nome entra no CAMINHO do artefato. Medido no pré-voo: com `provider="../../evil"` o
    payload virava `evil.json` fora de logs/importacoes/, e o prefixo de data — que é o que torna
    o artefato datável e localizável — era engolido em silêncio. `a/b` dava FileNotFoundError."""
    for ruim in ("../../evil", "a/b", "..", "", "A-Maiuscula"):
        with pytest.raises(ValueError, match="provider"):
            arquivar_payload(tmp_path, ruim, {"n": 1}, HOJE)


def test_nome_de_provider_valido_passa(tmp_path):
    """Contraprova da guarda acima: ela não pode barrar nome legítimo."""
    for bom in ("finnest", "pluggy", "banco-x2"):
        assert arquivar_payload(tmp_path, bom, {"n": 1}, HOJE).exists()


def test_terceira_rodada_no_mesmo_dia_continua_subindo(tmp_path):
    """O sufixo não para no -2. Quatro sincronizações num dia é rotina de quem tem várias contas."""
    nomes = [arquivar_payload(tmp_path, "finnest", {"n": n}, HOJE).name for n in range(1, 5)]
    assert nomes == ["2026-09-11-finnest.json", "2026-09-11-finnest-2.json",
                     "2026-09-11-finnest-3.json", "2026-09-11-finnest-4.json"]
