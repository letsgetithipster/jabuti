"""O README é o único documento que promete coisa para quem não leu o código. O invariante do
repo — nenhuma afirmação no presente sem código que a cumpra — precisa de check mecânico, senão
ele vale só por disciplina e a auditoria da Fase 1 já mostrou que não basta."""
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ESTE_ARQUIVO = Path(__file__).resolve()
README = (RAIZ / "README.md").read_text(encoding="utf-8")

IGNORADAS = {".git", ".github", ".githooks", "__pycache__", ".pytest_cache", ".venv"}

EXTENSOES_DE_TEXTO = {".py", ".md", ".yaml", ".template"}

FASE_DO_COMANDO = {
    "atualizar-cotacoes": 2, "importar-extrato": 2,
    "init": 4, "definir-macro": 4, "refinar-micro": 4, "aprofundar-tese": 4,
    "registrar-aporte": 5, "consultar-aporte": 5, "fechar-mes": 5,
    "preparar-ir": 6,
}


def _versionados_de_texto():
    """Arquivos de texto versionados (`.py`, `.md`, `.yaml`, `.template`), via `git ls-files` —
    não `Path.rglob`, que enxergaria arquivo ignorado ou apagado só no working tree."""
    saida = subprocess.run(["git", "ls-files", "-z"], cwd=RAIZ, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    if saida.returncode != 0:
        raise RuntimeError(
            "varredura da guarda não pôde ser feita: `git ls-files` falhou "
            f"(returncode {saida.returncode}): {saida.stderr.strip()}. "
            "Rode a suíte dentro de um clone git (com .git), não numa árvore copiada sem ele."
        )
    return [p for p in saida.stdout.split("\0")
            if p and Path(p).suffix in EXTENSOES_DE_TEXTO]


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


def test_numero_de_fase_citado_bate_com_o_roadmap():
    """A numeração de fase é um fato afirmado em vários lugares do repo, e a reordenação da spec
    deixou 13 deles errados — um na mensagem que todo usuário novo lê ao criar workspace. Este
    teste prende a citação ao mapa canônico.

    Mede CLÁUSULA, não linha: `skills/README.md` cita funil e rotina na mesma linha, com fases
    diferentes, e medir linha daria falso positivo.

    Ponto cego declarado: cobre só citação que nomeia um comando. Cláusula que cita fase por
    conceito ("compilador multi-LLM (Fase 3)", "pacotes tributários (Fase 5)") fica de fora, e
    são 6 lugares hoje. Fechar isso exigiria mapear conceito para fase, que é vocabulário fuzzy
    e daria teste frágil; preferi guarda parcial e honesta a guarda ampla e quebradiça.
    """
    fase_re = re.compile(r"[Ff]ase (\d)")
    clausula_re = re.compile(r"[;.\n—]")
    achados = []
    for rel in _versionados_de_texto():
        caminho = RAIZ / rel
        if caminho.resolve() == ESTE_ARQUIVO:
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, linha in enumerate(texto.splitlines(), start=1):
            for clausula in clausula_re.split(linha):
                fases = {int(x) for x in fase_re.findall(clausula)}
                if not fases:
                    continue
                for comando, esperada in FASE_DO_COMANDO.items():
                    if comando in clausula:
                        for f in fases - {esperada}:
                            achados.append(f"{rel}:{n}: {comando} citado com Fase {f}, "
                                           f"devia ser {esperada}")
    assert achados == [], "numeração de fase divergente do roadmap:\n  " + "\n  ".join(achados)
