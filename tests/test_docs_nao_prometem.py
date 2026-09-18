"""Nenhum documento do repo promete no presente o que o código não cumpre. É um só invariante
espalhado por três lugares: o README (estrutura de pastas, vínculo com a Finnest, fase de cada
comando), o GUARDRAILS (a garantia menor do dado de API, a ressalva de que nenhum provider está
ligado ainda) e a docstring do ledger (a promessa de que nenhum arquivo editado à mão muda o seu
patrimônio, que só vale quando `carteira.valorar` parar de ler `dados/posicoes.csv`). Ele vale
só por disciplina até virar check mecânico, e a auditoria da Fase 1 já mostrou que não basta."""
import inspect
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
    "jabuti-importar": 2,
    "jabuti-init": 4, "jabuti-estrategia": 4, "jabuti-micro": 4, "jabuti-tese": 4,
    "jabuti-mes": 5,
    "preparar-ir": 6,
    "jabuti-divida": 4,
    "jabuti-capacidade": 4,
}

# Os três nomes que a spec §4 fundiu em /jabuti-mes. Saíram do roadmap; o teste abaixo impede
# que voltem por prosa. Nome nu, sem barra: o defeito real estava em docstring de módulo
# ("o fechar-mes da Fase 5 absorve este gerador"), não em linha de skill.
ROTINA_FUNDIDA = ("registrar-aporte", "consultar-aporte", "fechar-mes")


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
    """As fases 4b a 6 não existem em código. Se o README as descrever no presente, ele mente.
    Onboarding (4a) existe: /jabuti-init e /jabuti-estrategia saíram desta lista quando nasceram.

    Mede BLOCO, não linha. O README é quebrado em coluna fixa, então um comando e o marcador de
    fase dele caem em linhas diferentes com frequência — medir linha faria o teste policiar
    largura de quebra em vez de promessa, e reabriria a falha a cada reflow do texto."""
    proibidas = ["/jabuti-micro", "/jabuti-tese",
                 "/registrar-aporte", "/consultar-aporte", "/fechar-mes", "/preparar-ir"]
    for bloco in README.split("\n\n"):
        for termo in proibidas:
            if termo in bloco:
                assert re.search(r"[Ff]ase|Próximas", bloco), \
                    f"{termo} citado sem marcar a fase: {bloco.strip()[:120]}"
    for bloco in README.split("\n\n"):
        for termo in proibidas:
            if termo in bloco:
                assert re.search(r"[Ff]ase|Próximas", bloco), \
                    f"{termo} citado sem marcar a fase: {bloco.strip()[:120]}"


def test_texto_embarcado_nao_cita_caminho_nem_comando_inexistente():
    """O invariante "nada promete no presente o que o código não cumpre" só era cobrado no README.
    Mas o texto que chega ao workspace do usuário é outro: as SKILL.md são copiadas, rules/ é
    compilado para dentro do CLAUDE.md e templates/workspace/ nasce lá. Por esse buraco passaram o
    handoff para /jabuti-micro e o "a tabela compacta é GERADA" sem gerador.

    Mede por ARQUIVO, não por bloco: /jabuti-micro aparece 9 vezes nas duas skills e quase toda
    ocorrência é ponteiro legítimo ("isso é da outra skill"), não promessa. Exigir ressalva em
    cada bloco encheria as skills de ruído.

    CUSTO DECLARADO, e ele tem endereço: um arquivo que já tem ressalva não é reavaliado ao
    ganhar promessa nova. Os três arquivos que a ressalva cobre hoje são exatamente os que a
    fase da rotina mensal vai reescrever para apontar para /jabuti-mes, e enquanto a ressalva
    estiver neles a guarda não vê essa citação nova. Medido nos dois sentidos. Quem apagar a
    citação de /jabuti-micro APAGA A RESSALVA NO MESMO COMMIT: é o que devolve a visão daqui.

    A ressalva exige falar de NÃO-INSTALADO. Aceitar qualquer "Fase N" deixava jabuti-importar
    passar verde, porque ele cita "Fase 5" sobre outro assunto — falso negativo no arquivo com o
    defeito.

    Conceito ("analistas de classe") não tem guarda aqui: não é caminho, e detector de conceito
    seria overengineering. O pino de literal removido, logo abaixo, cobre o que dá para cobrir.

    exemplos/ fica FORA do escopo de propósito: o exemplo é uma fotografia de workspace no meio
    do onboarding, e citar a próxima etapa ali é o comportamento correto do artefato.
    README.md também fica fora: o teste por bloco que já existe cobre.

    templates/ entra INTEIRO, não só templates/workspace/: a auditoria do PRONTO v1 achou em
    templates/docs/ um esqueleto que citava /jabuti-micro sem ressalva, fora do escopo de toda
    guarda. Esqueleto de documento é texto que a LLM copia para o workspace da pessoa."""
    escopo = [RAIZ / "GUARDRAILS.md"]
    escopo += sorted(RAIZ.glob("rules/*.md"))
    escopo += sorted(RAIZ.glob("skills/*/SKILL.md"))
    escopo += sorted((RAIZ / "templates").rglob("*.md"))

    instaladas = {p.parent.name for p in RAIZ.glob("skills/*/SKILL.md")}
    ressalva = re.compile(r"ainda não (está|estão) instalad|ainda não instalad|não existe ainda")
    cmd_re = re.compile(r"/(jabuti-[a-z]+)")
    path_re = re.compile(r"(?<![\w/.])((?:scripts|metodo|rules|mapeamentos)/[\w./-]+\.(?:py|yaml|md))")

    faltando = []
    for p in escopo:
        texto = p.read_text(encoding="utf-8")
        rel = p.relative_to(RAIZ).as_posix()
        tem_ressalva = bool(ressalva.search(texto))
        for nome in sorted(set(cmd_re.findall(texto))):
            if nome not in instaladas and not tem_ressalva:
                faltando.append(f"{rel}: /{nome} citado, não instalado, e o arquivo não ressalva isso")
        for caminho in sorted(set(path_re.findall(texto))):
            if not (RAIZ / caminho).exists() and not (RAIZ / "templates" / "workspace" / caminho).exists():
                faltando.append(f"{rel}: caminho {caminho} não existe")
    assert faltando == [], "texto embarcado cita o que não existe:\n  " + "\n  ".join(faltando)


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

    Mede CLÁUSULA, não linha: a última linha de `skills/README.md` cita a rotina da Fase 5 e o
    /preparar-ir da Fase 6 separados por ponto-e-vírgula, e medir linha daria falso positivo.

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


def test_nenhum_doc_promete_a_rotina_em_tres_skills():
    """A rotina é UMA skill com UMA pergunta: decidir onde aportar, ou registrar o que já
    aconteceu. Três nomes obrigam a pessoa a saber em qual metade do mês está antes de digitar.
    E não existe fechamento separado: o mês sem aporte é a decisão rodada com valor zero, o que
    apaga um script, um nome e um ritual de uma vez."""
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
            for nome in ROTINA_FUNDIDA:
                if nome in linha:
                    achados.append(f"{rel}:{n}: cita {nome!r}, fundido em /jabuti-mes")
    assert achados == [], (
        "documento promete a rotina em três skills:\n  " + "\n  ".join(achados))


PROMESSA_DE_FONTE_UNICA = "É a única fonte de qty e PM"


def test_ledger_so_promete_ser_a_fonte_unica_quando_carteira_parar_de_ler_posicoes():
    """A promessa mais cara do repo, um andar abaixo do README: a docstring do ledger dizia, no
    presente, que ele é a única fonte de qty e PM e que "não existe arquivo cuja edição mude o
    seu patrimônio". Medido no exemplo, com `fills.csv` intacto e editando só `dados/posicoes.csv`
    (PETR4 100 -> 900), o total do ESTADO ia de R$ 12.000,00 a R$ 44.000,00 — porque
    `carteira.valorar` ainda lê o arquivo. Quem acusa a divergência hoje é o validador, não o
    gerador, que é exatamente o defeito que a fase existe para fechar.

    Guarda de DUAS VIAS, como a do provider: enquanto `valorar` ler `posicoes.csv`, a frase tem
    que estar no futuro; no dia em que a leitura sair, este teste falha e cobra a volta dela ao
    presente. Ressalva que sobrevive ao fato que ela descreve é a mesma dívida ao contrário.
    """
    import po.carteira
    import po.ledger

    le_posicoes = '_ler("posicoes"' in inspect.getsource(po.carteira.valorar)
    promete_presente = PROMESSA_DE_FONTE_UNICA in (po.ledger.__doc__ or "")
    assert le_posicoes != promete_presente, (
        f"carteira.valorar {'ainda lê' if le_posicoes else 'não lê mais'} dados/posicoes.csv, e a "
        f"docstring do ledger {'promete' if promete_presente else 'não promete'} no presente ser a "
        f"única fonte de qty e PM. Enquanto a leitura existir, a frase tem que estar no futuro; "
        f"quando ela sair, a frase volta ao presente e este teste é o lembrete.")


PROMESSAS_APAGADAS = {
    "painel de gatilhos": "artefato que o motor nunca construiu e nenhuma fase agenda",
    "analistas de classe": "rules/ tem um arquivo: 00-voz.md. Nenhuma persona por classe",
    "analistas da casa": "idem: não há analista para o coordenador coordenar",
    "persona da classe": "idem",
    "personas de classe": "idem",
    "tabela compacta": "nenhum script do motor gera tabela compacta de teses",
    "nota ≥7": "nada no motor calcula nota de ativo",
}


def test_literal_de_promessa_apagada_nao_volta():
    """Pino de regressão sobre literais REMOVIDOS, não detector de conceito.

    O bloco C removeu cinco promessas em tempo presente. Duas eram caminho, e a guarda de texto
    embarcado acima as cobra sozinha. As outras são conceito, e a decisão de não construir
    detector de intenção está certa: nenhuma regra mecânica honesta separa promessa de ponteiro
    legítimo em prosa que ainda não foi escrita.

    Esta guarda não faz isso. Ela pina sete literais que já saíram, que é a única parte do
    defeito que uma regra mecânica alcança sem mentir — e é exatamente a varredura que a ordem
    de serviço mandava rodar à mão depois de cada item.

    Limite declarado: é literal, não sentido. "nota >= 7" ou "nota ≥ 7" com espaço passam. Não
    é para valer contra quem quer burlar; é para valer contra o copiar-e-colar do vault pessoal
    do autor, que é como os quatro entraram.

    Guarda de DUAS VIAS, no molde do PLANEJADAS de test_skills_catalogo: no dia em que as
    personas por classe existirem em rules/, ou em que algum script gerar a tabela compacta, a
    entrada correspondente SAI daqui, no mesmo commit do código que a torna verdadeira. Manter a
    proibição depois do fato é a mesma dívida ao contrário."""
    achados = []
    for rel in _versionados_de_texto():
        caminho = RAIZ / rel
        if caminho.resolve() == ESTE_ARQUIVO:
            continue
        try:
            texto = caminho.read_text(encoding="utf-8").lower()
        except (UnicodeDecodeError, OSError):
            continue
        for literal, motivo in PROMESSAS_APAGADAS.items():
            if literal.lower() in texto:
                achados.append(f"{rel}: {literal!r} presente — {motivo}")
    assert achados == [], (
        "o texto afirma o que o motor não cumpre (literal que o bloco C remove):\n  "
        + "\n  ".join(sorted(achados)))


TABELA_CITADA_RE = re.compile(r"([a-z_]+)\.csv")


def _documentacao():
    """A documentação que o usuário lê: README, GUARDRAILS, catálogo de skills, rules/, as
    SKILL.md, o template do workspace e o exemplo publicado.

    Fora, e cada exclusão tem motivo: `docs/` é registro datado de decisão, que fala de propósito
    de tabela que já saiu; `tests/` e `scripts/` são código, e código que nomeia a tabela errada
    quebra sozinho; e `.claude/skills/` do exemplo não é versionado, então incluí-lo faria o
    resultado depender da máquina."""
    escopo = [RAIZ / "README.md", RAIZ / "GUARDRAILS.md", RAIZ / "skills" / "README.md"]
    escopo += sorted(RAIZ.glob("rules/*.md"))
    escopo += sorted(RAIZ.glob("skills/*/SKILL.md"))
    escopo += sorted((RAIZ / "templates").rglob("*.md"))
    escopo += sorted((RAIZ / "exemplos").rglob("*.md"))
    return [p for p in escopo if p.is_file() and ".claude" not in p.parts]


def _tabelas_citadas():
    """(tabela, arquivo, linha) de cada citação de tabela canônica na documentação.

    Ocorrência precedida de separador de caminho só conta se o segmento anterior for `dados`:
    `inbox/posicoes.csv` é o export que a pessoa baixou da corretora, não a tabela do motor, e
    os dois se chamam igual no caminho feliz do produto. Confundi-los mandaria quem conserta
    editar o comando do usuário em vez do nome da tabela, que é a direção de erro mais cara:
    falso negativo deixa a suíte calada, falso positivo aponta a correção para o lado errado."""
    achados = []
    for p in _documentacao():
        rel = p.relative_to(RAIZ).as_posix()
        for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            for m in TABELA_CITADA_RE.finditer(linha):
                antes = linha[: m.start()]
                if (antes.endswith("/") or antes.endswith("\\")) and not re.search(r"dados[/\\]$", antes):
                    continue
                achados.append((m.group(1), rel, n))
    return achados


def test_toda_tabela_citada_na_documentacao_esta_em_schemas():
    """Nome de tabela é um fato afirmado pelo texto e sustentado pelo código. `po.csvs.SCHEMAS`
    é a lista do que existe; documentação que nomeia outra coisa promete um arquivo que o motor
    não escreve nem lê.

    Guarda de valor PROSPECTIVO declarado: hoje as 14 citações batem e o teste nasce verde. Ela
    existe para o dia em que uma tabela SAIR do SCHEMAS — o desenho do laço recorrente tira três
    — e a documentação continuar descrevendo o que já não existe. Medido: com `posicoes` fora do
    SCHEMAS, a citação em skills/jabuti-importar/SKILL.md fica vermelha na hora, numa SKILL.md
    que o usuário recebe copiada dentro do workspace dele.

    Ela também pega o caso inverso, que é o mais provável no dia a dia: SKILL nova citando
    `dados/registrar.csv` antes de a tabela existir."""
    from po.csvs import SCHEMAS

    fora = [f"{rel}:{n}: dados/{tab}.csv citado, e {tab!r} não está em po.csvs.SCHEMAS "
            f"({sorted(SCHEMAS)})"
            for tab, rel, n in _tabelas_citadas() if tab not in SCHEMAS]
    assert fora == [], "documentação nomeia tabela que o motor não tem:\n  " + "\n  ".join(fora)


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
    assert len(tokens) in (3, 5), (
        f"o comando da demo tem {len(tokens)} palavras ({comandos[0].strip()!r}) e este teste "
        "sabe executar `python <script> <workspace>` com um par `--data AAAA-MM-DD` opcional. "
        "Se o comando do README mudou de forma, reveja aqui o que é substituído antes de "
        "aceitar o novo formato.")
    interpretador, script, workspace, *extra = tokens
    assert extra in ([], ["--data", "2026-09-08"]), (
        f"a demo passa {extra!r}; este teste só sabe traduzir `--data AAAA-MM-DD`.")
    assert interpretador == "python", (
        f"o comando da demo começa com {interpretador!r}: este teste substitui `python` pelo "
        "interpretador da suíte, e não sabe traduzir outro interpretador.")
    assert workspace == WORKSPACE_DA_DEMO, (
        f"o comando da demo aponta para {workspace!r}, e este teste só sabe copiar "
        f"{WORKSPACE_DA_DEMO!r}. O README estaria prometendo saída de um workspace que o teste "
        "não verifica.")
    return [sys.executable, str(RAIZ / script), str(ws), *extra]


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
    reais = {l.rstrip() for l in saida.stdout.splitlines() if l.strip()}
    promete = {l.rstrip() for l in esperadas if l.strip()}
    assert reais == promete, (
        "a demo do README não bate linha a linha com o que ele promete. Subconjunto não basta: "
        "foi assim que a demo pôde ganhar uma terceira pendência (cotação velha) sem nenhum "
        "teste ficar vermelho.\n"
        f"Só na saída real: {sorted(reais - promete)}\n"
        f"Só no README:     {sorted(promete - reais)}\n"
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


def test_argv_da_demo_repassa_a_data_que_o_readme_declara():
    """O `--data` do README é o que desarma a bomba de calendário: sem ele a demo ganha uma
    terceira pendência no dia em que a cotação do exemplo completa 7 dias, e o teste da demo só
    ficaria vermelho naquele dia — tarde, e por calendário. Aqui o repasse ao subprocesso é
    cobrado hoje, com o valor que o README declara: tirar a flag do README, ou perdê-la no
    caminho até o argv, cai agora."""
    argv = _argv_da_demo(_bloco_de_demo(), Path("/tmp/ws"))
    assert argv[3:] == ["--data", "2026-09-08"], argv


@pytest.mark.parametrize("comando", [
    "$ python scripts/gerar_estado.py exemplos/outro",                 # workspace não copiado
    "$ python3 scripts/gerar_estado.py " + WORKSPACE_DA_DEMO,          # interpretador
    "$ python scripts/gerar_estado.py",                                # aridade de menos
    "$ python scripts/gerar_estado.py --data 2026-01-01 " + WORKSPACE_DA_DEMO,   # --data fora
    # de lugar: 5 tokens é aridade aceita desde que a demo ganhou a flag, então quem recusa este
    # é a guarda de valor do par `--data`, não a de aridade.
])
def test_argv_da_demo_recusa_comando_que_nao_sabe_executar(comando):
    """As quatro asserções de forma nunca são exercidas pelo caminho feliz. Se o README mudar o
    comando, o teste tem que falhar alto, e não passar a verificar outra coisa."""
    with pytest.raises(AssertionError):
        _argv_da_demo([comando], Path("/tmp/ws"))


DOCS_DE_RAIZ = ("README.md", "GUARDRAILS.md", "PRIVACIDADE.md", "CONTRIBUTING.md", "CHANGELOG.md")
# CHANGELOG fica FORA da guarda de caminho, e isso é decisão, não esquecimento: o trabalho dele é
# nomear o que foi REMOVIDO. Uma entrada correta como "sai dados/posicoes.csv" cita um caminho que
# deixou de existir, e uma guarda que a barrasse forçaria o changelog a mentir sobre o passado.
SOB_GUARDA_DE_CAMINHO = tuple(d for d in DOCS_DE_RAIZ if d != "CHANGELOG.md")

LINK_MD = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _pastas_de_topo_para_caminho():
    """As pastas de topo reais, derivadas do disco. Lista à mão aqui divergiria em silêncio no dia
    em que uma pasta nascesse — e é o dia em que a guarda mais precisaria estar certa."""
    return sorted(p.name for p in RAIZ.iterdir() if p.is_dir() and not p.name.startswith("."))


def _caminho_re():
    """Caminho de arquivo citado em prosa, com `/` ou `\\` (o README mostra comando PowerShell).

    Ancorado nas pastas de topo de propósito: sem essa âncora, `C:\\caminho\\meu-vault\\inbox\\
    extrato.xlsx` — exemplo legítimo, que descreve a MÁQUINA do leitor e não este repo — viraria
    falso positivo, e a guarda passaria a barrar texto correto. Medido contra os documentos de
    raiz de hoje: 24 caminhos e links citados (README 13, GUARDRAILS 3, PRIVACIDADE 4, CONTRIBUTING 4), 24 existentes,
    zero falso positivo.
    """
    grupo = "|".join(_pastas_de_topo_para_caminho())
    return re.compile(r"(?<![\w./\\-])((?:" + grupo + r")[/\\][\w./\\-]+\.(?:py|yaml|yml|md|txt|csv|json))")


def _citados(texto):
    alvos = set()
    for bruto in LINK_MD.findall(texto):
        alvo = bruto.split("#", 1)[0]
        if alvo and not alvo.startswith(("http://", "https://", "mailto:")):
            alvos.add(alvo)
    alvos |= set(_caminho_re().findall(texto))
    return sorted(alvos)


def test_a_raiz_traz_os_cinco_documentos_de_publicacao():
    """Os cinco são o que um estranho procura antes de rodar qualquer coisa: o que é (README), sob
    que contrato (GUARDRAILS), o que acontece com os meus dados (PRIVACIDADE), como eu ajudo
    (CONTRIBUTING), o que mudou desde que eu clonei (CHANGELOG). Faltar um é o repo respondendo
    'não sei' a uma pergunta que todo mundo faz."""
    faltando = [d for d in DOCS_DE_RAIZ if not (RAIZ / d).exists()]
    assert faltando == [], f"documento de publicação ausente na raiz: {faltando}"


def test_documento_de_raiz_nao_cita_link_nem_caminho_inexistente():
    """O invariante "nada promete no presente o que o código não cumpre" era cobrado por BLOCO no
    README (fase de comando) e por CAMINHO no texto embarcado (skills, rules, templates). Faltava
    a forma mais banal de promessa falsa num repo público: o link quebrado e o caminho que mudou
    de lugar. Quem clica e cai em 404 no primeiro minuto não volta.

    Cobre link markdown relativo e caminho de arquivo citado em prosa, com `/` ou `\\`.
    """
    quebrados = []
    for nome in SOB_GUARDA_DE_CAMINHO:
        caminho = RAIZ / nome
        if not caminho.exists():
            continue                       # a ausência é assunto do teste acima
        for alvo in _citados(caminho.read_text(encoding="utf-8")):
            if not (RAIZ / alvo.replace("\\", "/")).exists():
                quebrados.append(f"{nome}: {alvo}")
    assert quebrados == [], (
        "documento de raiz cita o que não existe:\n  " + "\n  ".join(quebrados))


def test_o_changelog_comeca_por_uma_secao_de_versao():
    """Changelog sem cabeça de versão vira diário. A seção do topo é onde a próxima mudança entra,
    e é o que faz a entrada nascer no commit dela em vez de ser reconstruída depois pelo git log."""
    texto = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
    secoes = [l for l in texto.splitlines() if l.startswith("## ")]
    assert secoes, "CHANGELOG.md não tem nenhuma seção `## `"
    assert re.match(r"^## (Não lançado|\d{4}-\d{2}-\d{2}|v?\d+\.\d+\.\d+)", secoes[0]), (
        f"a primeira seção do CHANGELOG é {secoes[0]!r}; esperava `## Não lançado`, `## AAAA-MM-DD` "
        "ou `## vX.Y.Z`")


# As sete perguntas de quem nunca investiu, na ordem em que ele as faz. Sentinela em comentário
# HTML e não título em português, pela mesma razão das duas sentinelas que o repo já tem: ninguém
# parafraseia um comentário HTML, ele sobrevive a qualquer reescrita da prosa ao redor e não
# aparece no markdown renderizado. Título seria reescrito na primeira revisão de texto e a guarda
# passaria a policiar redação em vez de cobertura.
ENSINA = ("o-que-e", "por-que", "antes-de-comecar", "primeiro-dia", "todo-mes",
          "vendi-ou-recebi", "onde-a-finnest-entra")
SENTINELA_ENSINA = re.compile(r"<!-- ensina: ([a-z-]+) -->")
# Casa `python scripts/x.py` e `python <motor>\scripts\x.py`, as duas formas que o README usa:
# a primeira quando o leitor está na pasta do motor, a segunda quando está no workspace dele.
COMANDO_PY = re.compile(r"(?:<motor>[\\/])?((?:scripts|tests)[\\/][\w.-]+\.py)")


def _secoes_do_readme():
    """(ordem das sentinelas, {sentinela: corpo até a próxima})."""
    marcas = list(SENTINELA_ENSINA.finditer(README))
    secoes = {}
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(README)
        secoes[m.group(1)] = README[m.end():fim]
    return [m.group(1) for m in marcas], secoes


def test_o_readme_ensina_as_sete_coisas_na_ordem():
    """O README deixou de ser status de projeto e virou porta de entrada. Sem guarda, ele volta ao
    gênero antigo no terceiro commit: descrever fase é o reflexo natural de quem escreve de
    dentro, e foi assim que este repo acumulou promessa em tempo presente.

    Limite declarado, porque guarda que finge medir o que não mede é pior que guarda ausente:
    isto cobra que as sete seções EXISTAM, estejam na ordem e não sejam vazias. Não mede se a
    prosa ensina. Nenhuma regra mecânica honesta mede isso, e construir detector de didática
    seria a sobre-engenharia que este repo já tem demais.
    """
    ordem, secoes = _secoes_do_readme()
    assert ordem == list(ENSINA), (
        f"as sentinelas do README são {ordem} e deviam ser {list(ENSINA)}. A ordem é a ordem em "
        "que quem nunca investiu faz as perguntas: o que é, por que eu usaria, o que preciso, o "
        "que faço hoje, o que faço todo mês, o que faço quando vendo, onde a Finnest entra.")
    curtas = [k for k in ENSINA
              if len([l for l in secoes[k].splitlines() if l.strip()]) < 4]
    assert curtas == [], (
        f"estas seções têm menos de quatro linhas com conteúdo: {curtas}. Sentinela sobre seção "
        "vazia é a forma mais barata de fazer a guarda passar sem responder a pergunta.")


def test_as_secoes_de_comando_do_readme_rodam_comandos_que_existem():
    """As três seções que mandam a pessoa digitar coisa são as que doem quando mentem: o leitor
    cola, o comando não existe, e ele fecha a aba. A guarda de caminho da raiz já cobre prosa;
    esta cobre o que está DENTRO de bloco de código, onde a forma `<motor>\\scripts\\x.py`
    escapava do padrão ancorado em pasta de topo."""
    _, secoes = _secoes_do_readme()
    faltando = []
    for chave in ("primeiro-dia", "todo-mes", "vendi-ou-recebi"):
        blocos = re.findall(r"```[a-z]*\n(.*?)```", secoes[chave], re.S)
        assert blocos, f"a seção {chave} não mostra nenhum comando, e ela existe para mostrar"
        for bloco in blocos:
            for alvo in COMANDO_PY.findall(bloco):
                if not (RAIZ / alvo.replace("\\", "/")).exists():
                    faltando.append(f"{chave}: {alvo}")
    assert faltando == [], (
        "o README manda rodar o que não existe:\n  " + "\n  ".join(faltando))
