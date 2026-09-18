"""A CI é o único lugar onde a fronteira motor-máquina é exercitada, porque o pre-commit roda só
na máquina do autor, em win32. Estes testes não rodam a CI — rodam o que dá para conferir sem
GitHub: que o workflow existe, que a matriz cobre as duas plataformas e os três Pythons, que os
dois jobs de dependência existem (com e sem openpyxl), que os dois validam o exemplo, e que o
badge do README aponta para um workflow que existe.

Armadilha do YAML, e é por isso que há um teste só para ela: `on:` não é a string "on". O
resolver do YAML 1.1 que o PyYAML implementa converte `on`, `off`, `yes` e `no` para booleano,
então `yaml.safe_load("on: push")` devolve `{True: 'push'}`. Um teste escrito com `doc["on"]`
levanta KeyError e o autor "conserta" apagando o teste.
"""
import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOWS = RAIZ / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"
RELOGIO = WORKFLOWS / "relogio.yml"


def _carregar(caminho: Path) -> dict:
    assert caminho.exists(), (
        f"{caminho.relative_to(RAIZ).as_posix()} ausente — sem ele a suíte roda só na máquina do "
        "autor, e é ali que a fronteira motor-máquina deixa de ser testada")
    doc = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    assert isinstance(doc, dict), f"{caminho.name} não é um mapeamento YAML"
    return doc


def gatilhos(doc: dict):
    """O valor de `on:`, sob a chave que o PyYAML de fato produz. Ver docstring do módulo."""
    return doc[True] if True in doc else doc.get("on")


def _passos(doc: dict):
    for job in doc["jobs"].values():
        for passo in job.get("steps", []):
            yield job, passo


def test_a_chave_on_do_yaml_nao_virou_booleano_silencioso():
    """Pina a armadilha na própria suíte. Sem isto, o dia em que alguém trocar `gatilhos(doc)` por
    `doc["on"]` o teste some com KeyError e a guarda inteira vira decoração."""
    assert yaml.safe_load("on: push") == {True: "push"}
    assert gatilhos({True: "push"}) == "push"
    assert gatilhos({"on": "push"}) == "push"


def test_ci_cobre_as_duas_plataformas_e_os_tres_pythons():
    doc = _carregar(CI)
    matrizes = [job["strategy"]["matrix"] for job in doc["jobs"].values() if "strategy" in job]
    assert matrizes, "nenhum job da CI declara matriz"
    m = matrizes[0]
    assert set(m["os"]) == {"ubuntu-latest", "windows-latest"}, (
        f"a matriz cobre {m['os']}: o Windows é a máquina do autor e o Linux é a que ele nunca "
        "testou; tirar qualquer um dos dois devolve o repo ao ponto cego")
    assert set(str(v) for v in m["python"]) == {"3.11", "3.12", "3.13"}
    assert doc["jobs"]["suite"]["strategy"]["fail-fast"] is False, (
        "com fail-fast ligado, a primeira combinação vermelha esconde as outras onze — e a "
        "primeira execução vai ser vermelha de propósito")


def test_ci_tem_um_job_sem_openpyxl_e_um_com():
    """Os dois caminhos de dependência existem no mundo real: quem instala só requirements.txt (o
    que o README manda) e quem instala tudo. Sem o job mínimo, o caminho de `skipped` nunca é
    exercitado; sem o job cheio, o caminho de xlsx nunca é exercitado."""
    doc = _carregar(CI)
    m = doc["jobs"]["suite"]["strategy"]["matrix"]
    assert set(m["extras"]) == {"minimo", "xlsx"}
    condicionais = [p for _, p in _passos(doc)
                    if "requirements-xlsx.txt" in str(p.get("run", ""))]
    assert condicionais, "nenhum passo instala requirements-xlsx.txt"
    for passo in condicionais:
        assert "xlsx" in str(passo.get("if", "")), (
            f"o passo {passo.get('name')!r} instala openpyxl sem condicionar ao eixo `extras`: "
            "os dois jobs ficariam idênticos e o caminho de `skipped` voltaria a ser ponto cego")


@pytest.mark.parametrize("arquivo", ["ci.yml", "relogio.yml"])
def test_todo_workflow_roda_a_suite_e_o_validador_do_exemplo(arquivo):
    doc = _carregar(WORKFLOWS / arquivo)
    corrido = " ".join(str(p.get("run", "")) for _, p in _passos(doc))
    assert "pytest" in corrido, f"{arquivo} não roda a suíte"
    assert "validar_workspace.py exemplos/workspace-exemplo" in corrido, (
        f"{arquivo} não valida o exemplo — e o exemplo é o que o README manda o leitor rodar")
    assert "PYTHONIOENCODING" not in doc.get("env", {}), (
        "a CI define PYTHONIOENCODING e com isso esconde a classe de defeito que ela existe para "
        "achar: o console cp1252 do Windows. A variável é ferramenta de quem desenvolve, não "
        "configuração do produto")


def test_o_relogio_e_agendado_e_abre_issue_em_falha():
    """Defeito que só o calendário dispara não tem commit que o acione, e CI de push nunca o pega.
    O exemplo do repo é datado e o motor trata dado velho como alerta: o relógio é o produto
    aplicado em si mesmo."""
    doc = _carregar(RELOGIO)
    g = gatilhos(doc)
    assert isinstance(g, dict) and "schedule" in g, f"relogio.yml sem schedule: {g!r}"
    assert any("cron" in item for item in g["schedule"])
    corrido = " ".join(str(p.get("run", "")) for _, p in _passos(doc))
    assert "issue create" in corrido, "o relógio fica vermelho e ninguém fica sabendo"
    assert any("failure()" in str(p.get("if", "")) for _, p in _passos(doc)), (
        "o passo que abre issue não está condicionado a failure(): abriria issue toda semana")


def test_o_badge_do_readme_aponta_para_um_workflow_que_existe():
    """Badge que aponta para workflow inexistente rende um 404 estampado no topo da página, que é
    o pior lugar possível para um link morto. Não policia dono/repositório de propósito: fork
    legítimo troca isso, e a parte que apodrece é o nome do arquivo."""
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    alvos = re.findall(r"/actions/workflows/([\w.-]+)/badge\.svg", readme)
    assert alvos, "o README não tem badge de CI"
    faltando = [a for a in alvos if not (WORKFLOWS / a).exists()]
    assert faltando == [], f"badge aponta para workflow inexistente: {faltando}"
