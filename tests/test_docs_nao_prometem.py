"""Nenhum documento do repo promete no presente o que o código não cumpre. É um só invariante
espalhado por dois arquivos: o README (estrutura de pastas, vínculo com a Finnest, fase de cada
comando) e o GUARDRAILS (a garantia menor do dado de API, a ressalva de que nenhum provider está
ligado ainda). Ele vale só por disciplina até virar check mecânico, e a auditoria da Fase 1 já
mostrou que não basta."""
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ESTE_ARQUIVO = Path(__file__).resolve()
README = (RAIZ / "README.md").read_text(encoding="utf-8")
GUARDRAILS = (RAIZ / "GUARDRAILS.md").read_text(encoding="utf-8")

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
    dado de API uma garantia que o dado de API não tem.

    Mede o PARÁGRAFO que cita `soma-da-resposta`, não a presença da string em qualquer lugar do
    arquivo: uma reescrita que invertesse o sentido — dizendo que essa conciliação é tão forte
    quanto as outras três — manteria a string 'soma-da-resposta' e passaria pelo assert antigo
    mesmo mentindo sobre a garantia que a seção existe para não prometer."""
    assert "payload" in GUARDRAILS.lower() or "resposta crua" in GUARDRAILS.lower()
    paragrafos_da_conciliacao = [p for p in GUARDRAILS.split("\n\n") if "soma-da-resposta" in p]
    assert paragrafos_da_conciliacao, "nenhum parágrafo do GUARDRAILS cita soma-da-resposta"
    assert any("mais fraca" in p for p in paragrafos_da_conciliacao), (
        "soma-da-resposta é citado sem declarar que é mais fraca que as outras três "
        "conciliações — a seção existe para prometer essa garantia MENOR, não uma garantia igual")


def _chamadores_de_provider():
    """Arquivos que USAM a camada de provider, fora da definição dela. Enquanto esta lista está
    vazia, a ingestão por provider é capacidade sem pipeline: as funções existem e ninguém as
    chama.

    Grep sobre AST, com dois limites conhecidos e aceitos, não consertados de propósito:

    1. Falso positivo que dói: um comentário como
       `# TODO: quando o adaptador existir, chamar arquivar_payload` em qualquer arquivo de
       scripts/ conta como chamador. Isso empurra quem vir a falha a apagar a ressalva do
       GUARDRAILS — a correção errada — em vez de perceber que é só um comentário. É a direção
       de erro mais cara desta guarda: falso negativo deixa a suíte calada, falso positivo aponta
       a correção para o lado errado (fazer o documento mentir em vez de corrigir o comentário).
    2. Falso negativo que importa: o skip é por basename (`provider.py`), então um chamador
       escrito DENTRO do próprio `provider.py` — o lugar mais natural para o primeiro
       orquestrador, já que é o módulo onde as duas funções moram — nunca é achado. AST não
       resolve isso sozinho: é um problema de escopo (chamador e definição no mesmo arquivo),
       não de sintaxe.

    A escolha de grep sobre AST só se sustenta enquanto ninguém escrever um TODO com o nome da
    função, e TODO com nome de função é exatamente o tipo de coisa que aparece num repo que
    acabou de deixar essa camada sem chamador de propósito.
    """
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


def _ressalva_coerente(tem_ressalva: bool, chamadores: list[str]) -> bool:
    """A ressalva tem que existir enquanto não houver chamador, e sair quando houver."""
    return tem_ressalva == (not chamadores)


def test_ressalva_coerente_nas_quatro_combinacoes():
    """A lógica de `test_guardrails_nao_promete_provider_sem_chamador` só é testada, hoje, contra
    o estado atual do repo — ressalva presente, zero chamadores — onde `tem_ressalva == (not
    chamadores)` e `tem_ressalva or not chamadores` dão o mesmo resultado. Uma mutação que trocasse
    `==` por `or` sobreviveria em silêncio até o dia em que um chamador aparecesse. Testar a
    função pura nas quatro combinações prende a lógica antes desse dia, não depois."""
    assert _ressalva_coerente(True, []) is True
    assert _ressalva_coerente(False, []) is False
    assert _ressalva_coerente(True, ["scripts/x.py"]) is False
    assert _ressalva_coerente(False, ["scripts/x.py"]) is True


def test_guardrails_nao_promete_provider_sem_chamador():
    """Guarda de DUAS VIAS, e as duas importam.

    Enquanto `arquivar_payload` e `conferir_status` não tiverem chamador, o GUARDRAILS descreve
    contrato, não comportamento corrente, e **precisa** dizer isso — senão promete um pipeline que
    ninguém pode executar, que é o invariante do repo violado no documento onde ele mais pesa.

    E quando o adaptador existir, este teste falha e cobra a REMOÇÃO da ressalva. Ressalva que
    sobrevive ao fato que ela descreve é a mesma dívida ao contrário: o leitor passa a duvidar de
    uma garantia que já vale.

    A presença da ressalva é medida por uma SENTINELA em comentário HTML
    (`<!-- sentinela: nenhum-provider-ligado -->`) dentro do blockquote, não por prosa em
    português. Antes, o teste procurava a frase "nenhum provider", que também aparecia numa nota
    meta logo abaixo do blockquote explicando a própria guarda — e quem apagasse o blockquote
    inteiro mantendo só a nota meta via a suíte passar com a ressalva de fato ausente do
    documento. A nota meta foi removida junto com a troca: era o segundo lugar onde a frase podia
    morar, e um comentário HTML dentro do blockquote não sobrevive a uma reescrita da prosa nem
    aparece no markdown renderizado.
    """
    chamadores = _chamadores_de_provider()
    tem_ressalva = "sentinela: nenhum-provider-ligado" in GUARDRAILS
    assert _ressalva_coerente(tem_ressalva, chamadores), (
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
    conceito ("compilador multi-LLM", "pacotes tributários por ano-fiscal") fica de fora — e é
    lugar-comum no repo: a maior parte dessas menções descreve corretamente quando algo nasceu
    (a Fase 2 do cockpit, a Fase 1 do brainstorming de providers), não promete um comando. Mapear
    conceito para fase fecharia essa lacuna, mas o vocabulário é fuzzy o bastante pra dar teste
    frágil; prefiro guarda parcial e honesta a guarda ampla e quebradiça.
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


def _bloco_de_demo():
    """As linhas entre os sentinelas `demo:start` e `demo:end` do README.

    Sentinela em comentário HTML em vez de prosa: sobrevive a qualquer reescrita do texto ao
    redor, ninguém parafraseia um comentário HTML, e não aparece no markdown renderizado. Mesma
    convenção da sentinela do GUARDRAILS — e a razão de ser sentinela, e não uma frase, é que
    uma frase sobre o teste pode satisfazer o próprio teste, o que já aconteceu neste repo.
    """
    m = re.search(r"<!-- demo:start -->(.*?)<!-- demo:end -->", README, re.S)
    assert m, "os sentinelas demo:start/demo:end desapareceram do README"
    return [l for l in m.group(1).splitlines() if l.strip() and not l.startswith("```")]


WORKSPACE_DA_DEMO = "exemplos/workspace-exemplo"


def _argv_da_demo(linhas, ws):
    """O comando do bloco de demo, traduzido para argv executável contra a cópia `ws`.

    Duas substituições, e só duas: `python` vira o interpretador que roda a suíte (para a demo
    ser verificada no mesmo ambiente que o teste, não num `python` qualquer do PATH), e o
    workspace do repositório vira a cópia temporária (para o teste não mutar o repo). O nome do
    script vem do README e não é substituído — é ele que precisa ser verificado, porque é a
    linha que o leitor copia e cola.

    As asserções de forma existem para que qualquer mudança no comando falhe alto, em vez de o
    teste passar a verificar silenciosamente um comando que o README não promete mais.
    """
    comandos = [l for l in linhas if l.startswith("$ ")]
    assert len(comandos) == 1, f"esperava um comando no bloco de demo, achei {len(comandos)}"
    tokens = shlex.split(comandos[0][2:])
    assert len(tokens) == 3, (
        f"o comando da demo tem {len(tokens)} palavras ({comandos[0].strip()!r}) e este teste "
        "sabe executar exatamente `python <script> <workspace>`. Se o comando do README mudou "
        "de forma, reveja aqui o que é substituído antes de aceitar o novo formato.")
    interpretador, script, workspace = tokens
    assert interpretador == "python", (
        f"o comando da demo começa com {interpretador!r}: este teste substitui `python` pelo "
        "interpretador da suíte, e não sabe traduzir outro interpretador.")
    assert workspace == WORKSPACE_DA_DEMO, (
        f"o comando da demo aponta para {workspace!r}, e este teste só sabe copiar "
        f"{WORKSPACE_DA_DEMO!r}. O README estaria prometendo saída de um workspace que o teste "
        "não verifica.")
    return [sys.executable, str(RAIZ / script), str(ws)]


def test_a_demo_do_readme_roda_e_produz_o_que_o_readme_promete(tmp_path):
    """A primeira tela do README cola a saída de um comando, e é ela que faz a conexão com quem
    chega. Se o comando quebrar ou a saída mudar, o README mente na primeira tela — e mentir ali
    é pior que mentir no meio, porque é a única parte que todo mundo lê.

    O comando executado é o do README, traduzido por `_argv_da_demo`: só duas partes são
    substituídas, o interpretador (para rodar no mesmo ambiente da suíte) e o workspace (uma
    CÓPIA de `exemplos/workspace-exemplo`, para o teste não mutar o repo). O nome do script não
    é substituído — é a linha que o leitor copia e cola, e é por isso que precisa ser a que
    de fato roda aqui.
    """
    from test_validar_dados import copia_exemplo

    linhas = _bloco_de_demo()
    esperadas = [l for l in linhas if not l.startswith("$ ")]
    assert esperadas, "o bloco de demo não promete saída nenhuma"

    ws = copia_exemplo(tmp_path)
    # Apaga aqui, confere no assert abaixo que o arquivo existe de novo: é o par que prova que
    # o comando GERA o ESTADO.md. Tirar qualquer uma das duas metades desarma a verificação.
    (ws / "estado" / "ESTADO.md").unlink()
    saida = subprocess.run(
        _argv_da_demo(linhas, ws),
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert (ws / "estado" / "ESTADO.md").exists(), (
        "a demo nao regenerou o ESTADO.md que o teste apagou antes de rodar")
    assert saida.returncode == 0, f"a demo do README falhou: {saida.stderr.strip()[:300]}"
    reais = {l.rstrip() for l in saida.stdout.splitlines()}
    for linha in esperadas:
        assert linha.rstrip() in reais, (
            f"o README promete a linha {linha!r} e a demo não produziu.\n"
            f"Saída real:\n{saida.stdout}")


def test_argv_da_demo_deriva_o_script_do_readme():
    """Prende a separação entre o comando executado e o comando prometido: o nome do script
    sai do README, não de uma constante. Sem este teste, um hardcode volta e a suíte não vê —
    ele passaria a verificar um comando que o README não promete mais, em silêncio."""
    argv = _argv_da_demo(["$ python scripts/qualquer_coisa.py " + WORKSPACE_DA_DEMO],
                         Path("/tmp/ws"))
    assert argv[0] == sys.executable
    assert argv[1] == str(RAIZ / "scripts/qualquer_coisa.py")
    assert argv[2] == str(Path("/tmp/ws"))


@pytest.mark.parametrize("comando", [
    "$ python scripts/gerar_estado.py exemplos/outro",                 # workspace não copiado
    "$ python3 scripts/gerar_estado.py " + WORKSPACE_DA_DEMO,          # interpretador
    "$ python scripts/gerar_estado.py",                                # aridade de menos
    "$ python scripts/gerar_estado.py --data 2026-01-01 " + WORKSPACE_DA_DEMO,   # aridade demais
])
def test_argv_da_demo_recusa_comando_que_nao_sabe_executar(comando):
    """As três asserções de forma nunca são exercidas pelo caminho feliz. Se o README mudar o
    comando, o teste tem que falhar alto, e não passar a verificar outra coisa."""
    with pytest.raises(AssertionError):
        _argv_da_demo([comando], Path("/tmp/ws"))
