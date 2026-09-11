"""O README é o único documento que promete coisa para quem não leu o código. O invariante do
repo — nenhuma afirmação no presente sem código que a cumpra — precisa de check mecânico, senão
ele vale só por disciplina e a auditoria da Fase 1 já mostrou que não basta."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
README = (RAIZ / "README.md").read_text(encoding="utf-8")

IGNORADAS = {".git", ".github", ".githooks", "__pycache__", ".pytest_cache", ".venv"}


def _pastas_de_topo():
    return sorted(p.name for p in RAIZ.iterdir()
                  if p.is_dir() and p.name not in IGNORADAS and not p.name.startswith("."))


def test_toda_pasta_de_topo_aparece_na_estrutura_com_fase():
    """Pasta que existe e não está na tabela é promessa não declarada; pasta na tabela sem fase
    é promessa sem prazo. A auditoria da Fase 1 achou as duas coisas."""
    faltando = [p for p in _pastas_de_topo() if f"`{p}/`" not in README]
    assert faltando == [], f"pastas de topo fora da tabela de estrutura: {faltando}"


def test_declara_o_vinculo_com_a_finnest():
    """Publicidade velada é vedada pelo CONAR e pelo art. 36 do CDC, e contradiz a tese do
    produto, que é tornar visível o conflito de quem aconselha."""
    texto = README.lower()
    assert "finnest" in texto
    assert "co-founder" in texto or "cofundador" in texto or "sócio" in texto


def test_nao_promete_no_presente_o_que_e_de_fase_futura():
    """As fases 4 a 6 não existem em código. Se o README as descrever no presente, ele mente.

    Mede BLOCO, não linha. O README é quebrado em coluna fixa, então um comando e o marcador de
    fase dele caem em linhas diferentes com frequência — medir linha faria o teste policiar
    largura de quebra em vez de promessa, e reabriria a falha a cada reflow do texto."""
    proibidas = ["/init", "/definir-macro", "/refinar-micro", "/aprofundar-tese",
                 "/registrar-aporte", "/consultar-aporte", "/fechar-mes", "/preparar-ir"]
    for bloco in README.split("\n\n"):
        for termo in proibidas:
            if termo in bloco:
                assert re.search(r"[Ff]ase|Próximas", bloco), \
                    f"{termo} citado sem marcar a fase: {bloco.strip()[:120]}"


def test_guardrails_declara_a_garantia_menor_do_dado_de_api():
    """Se o GUARDRAILS descrevesse só a ingestão de documento, ele estaria prometendo para o
    dado de API uma garantia que o dado de API não tem."""
    texto = (RAIZ / "GUARDRAILS.md").read_text(encoding="utf-8")
    assert "soma-da-resposta" in texto
    assert "payload" in texto.lower() or "resposta crua" in texto.lower()


def _chamadores_de_provider():
    """Arquivos que USAM a camada de provider, fora da definição dela. Enquanto esta lista está
    vazia, a ingestão por provider é capacidade sem pipeline: as funções existem e ninguém as
    chama."""
    alvos = ("arquivar_payload", "conferir_status")
    achados = []
    for caminho in (RAIZ / "scripts").rglob("*.py"):
        if caminho.name == "provider.py":
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(a in texto for a in alvos):
            achados.append(caminho.relative_to(RAIZ).as_posix())
    return sorted(achados)


def test_guardrails_nao_promete_provider_sem_chamador():
    """Guarda de DUAS VIAS, e as duas importam.

    Enquanto `arquivar_payload` e `conferir_status` não tiverem chamador, o GUARDRAILS descreve
    contrato, não comportamento corrente, e **precisa** dizer isso — senão promete um pipeline que
    ninguém pode executar, que é o invariante do repo violado no documento onde ele mais pesa.

    E quando o adaptador existir, este teste falha e cobra a REMOÇÃO da ressalva. Ressalva que
    sobrevive ao fato que ela descreve é a mesma dívida ao contrário: o leitor passa a duvidar de
    uma garantia que já vale.
    """
    chamadores = _chamadores_de_provider()
    texto = (RAIZ / "GUARDRAILS.md").read_text(encoding="utf-8").lower()
    tem_ressalva = "nenhum provider" in texto
    assert tem_ressalva == (not chamadores), (
        f"a ressalva de que nenhum provider está ligado {'está' if tem_ressalva else 'não está'} "
        f"no GUARDRAILS, e os chamadores da camada de provider são {chamadores or 'nenhum'}. "
        "Ela tem que existir enquanto não houver chamador, e sair quando houver")
