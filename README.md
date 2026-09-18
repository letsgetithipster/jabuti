# jabuti

[![ci](https://github.com/letsgetithipster/jabuti/actions/workflows/ci.yml/badge.svg)](https://github.com/letsgetithipster/jabuti/actions/workflows/ci.yml)

Suas finanças em texto simples, operadas pela LLM que você já usa, sob guardrails que não
deixam número inventado entrar. **Ele zela, não decide:** a decisão continua sua.

O jabuti não corre. Vive oitenta anos e chega.

De brasileiros, para brasileiros.

<!-- ensina: o-que-e -->
## O que é isto

Uma pasta no seu computador. Dentro dela, alguns arquivos de texto com quem você é e a regra
que você escolheu para dividir o seu dinheiro, e cinco CSVs com o que você comprou, a que
preço e quando. Um punhado de comandos lê esses arquivos e escreve um resumo de uma tela. E
um contrato, o [GUARDRAILS.md](GUARDRAILS.md), que impede a LLM de inventar número.

Não é corretora, não é aplicativo, não movimenta o seu dinheiro e não te vende nada. Você
não precisa saber programar: você conversa com a LLM no terminal, e ela roda os comandos.

Sobre os dados de exemplo que vêm no repo, sem configurar nada:

<!-- demo:start -->
```
$ python scripts/gerar_estado.py exemplos/workspace-exemplo --data 2026-09-08
estado/ESTADO.md regenerado — Total investido: R$ 12.000,00
Pendências:
- fiis acima da banda máxima (66,7% vs 40%): rebalancear via aporte nos blocos abaixo
- rf-br abaixo do mínimo (0,0% vs 25%): priorizar nos próximos aportes
```
<!-- demo:end -->

Isso saiu de CSV canônico: toda cotação carrega fonte, data e hora, e o validador recalcula
os totais em todo commit.

> Leia **[GUARDRAILS.md](GUARDRAILS.md)** antes de usar. É o contrato que torna este produto
> confiável, e o motivo de ele existir.

<!-- ensina: por-que -->
## Por que eu usaria

Assessoria tradicional custa 0,5% a 2% ao ano, ou é remunerada por quem distribui o produto
que ela te recomenda: conflito de interesse estrutural, não má-fé de ninguém. Family office
dedicado é inacessível para quem não tem alguns milhões.

A LLM que você já paga tem mais informação do que qualquer escritório. O que falta a ela são
três coisas, e são exatamente as três que este repo entrega:

- **Memória.** Cada conversa nova começa do zero. Aqui a memória é arquivo: a sua política,
  o seu livro de operações e o seu histórico ficam no disco e são lidos toda vez.
- **Número que não é opinião do modelo.** Preço entra por script, com fonte e hora. Extrato
  de corretora só entra depois que a aritmética do próprio documento fecha. O modelo nunca
  digita um número de mercado.
- **Uma regra escrita antes.** Você declara as bandas em que quer ficar num dia calmo. Nos
  dias ruins, o sistema executa a regra que você escreveu, e mostra que ela foi atingida.

É um family office de uma pessoa só, com a disciplina que a LLM sozinha não tem. O custo é a
assinatura de LLM que você já paga.

**Declaração de vínculo:** o autor deste repositório é co-founder da Finnest, que duas skills
opcionais deste repo leem. Veja [onde a Finnest entra](#onde-a-finnest-entra).

<!-- ensina: antes-de-comecar -->
## O que eu preciso antes de começar

Quatro coisas, e três delas você provavelmente já tem.

1. **Um computador com Python 3.11 ou mais novo, e git.** Windows, macOS ou Linux.
2. **Uma assinatura de LLM que abra terminal.** Hoje o harness que o repo compila é o do
   Claude Code.
3. **Uns 30 minutos**, uma vez só, para as três conversas de onboarding.
4. **Se você já investe:** o extrato ou a foto de posições da sua corretora, em CSV ou xlsx.
   Qualquer corretora serve: o que o motor lê é um mapeamento declarado em YAML (Clear,
   Schwab, movimentação da B3 e um CSV genérico de posições vêm prontos em `mapeamentos/`),
   e a LLM escreve o seu quando não houver um pronto, mostrando antes de rodar.

**Se você nunca investiu, não precisa de nada além dos três primeiros.** Você não precisa
ter dinheiro aplicado para começar: a carteira vazia é um estado válido, e o produto foi
feito para dizer isso em vez de te devolver uma tela de zeros.

O que você **não** precisa: saber programar, ter conta em corretora específica, conectar
banco nenhum, pagar qualquer coisa para este projeto.

<!-- ensina: primeiro-dia -->
## O que eu faço no primeiro dia

Quatro comandos de terminal e três conversas.

```powershell
git clone https://github.com/letsgetithipster/jabuti.git
cd jabuti
python -m pip install -r requirements.txt
python scripts/criar_workspace.py C:\caminho\meu-vault
```

(macOS e Linux: troque os caminhos, por exemplo `python3 scripts/criar_workspace.py ~/meu-vault`.
Extrato em xlsx e o cockpit em planilha pedem também `python -m pip install -r requirements-xlsx.txt`.)

O último comando cria a **sua** pasta, separada deste repo. É ela que guarda os seus dados;
este repo guarda o método. Agora abra a LLM dentro da sua pasta e cole, uma por vez:

| Cole | O que acontece |
|---|---|
| `/jabuti-init` | você conta quem é: idade, horizonte, custo de vida, como reagiria a uma queda de 30%. Vira `politica/00-perfil.md`, e o validador recalcula os derivados. A LLM nunca aplica taxa de memória |
| `/jabuti-estrategia` | você escolhe a sua política de alocação entre três alternativas com racional, ou declara a que você já tem. Vira uma tabela de bandas e um log de decisão **seu**, datado |
| `/jabuti-importar` | você traz a carteira que já existe, a partir do extrato da sua corretora, ou responde que ainda não tem nada, e o onboarding fecha aí |

Cada conversa termina dizendo qual é a próxima, e `estado/SETUP.md` guarda onde você parou.
No fim, `estado/ESTADO.md` mostra a sua carteira lida dentro da sua política.

<!-- ensina: todo-mes -->
## O que eu faço todo mês

Uma conversa. Você abre a LLM na sua pasta e cola `/jabuti-mes`. Ela faz **uma** pergunta:
decidir onde aportar, ou registrar o que já aconteceu?

**Decidir, antes de comprar.** A skill atualiza as cotações, regenera o `ESTADO.md` e roda
a fila de aporte sobre a política que você declarou. Nos comandos abaixo, `<motor>` é a pasta
onde você clonou o jabuti e `.` é a sua pasta:

```powershell
python <motor>\scripts\atualizar_cotacoes.py .
python <motor>\scripts\gerar_estado.py .
python <motor>\scripts\consultar_aporte.py . 1500 --todos
```

A cotação vem do provider declarado em `vault.config.yaml`. O default é `yahoo`, sem token
e sem cadastro. Para o que não tem mercado (renda fixa) ou quando você prefere que nada saia
pela rede, `--manual TICKER=PRECO` grava o preço que você colou, com a fonte `manual`. Sem
rede, o script para e declara: nunca preço de memória.

O número da fila não sai da cabeça do modelo: sai de uma função testada, que ordena os
blocos pela distância até o alvo, nas três alternativas de distribuição. A LLM traduz o
resultado, e a sua escolha vira um log de decisão datado. A fila termina sempre com a mesma
frase: *isto executa a política que você declarou; não é recomendação de investimento.*

**Registrar, depois de comprar.**

```powershell
python <motor>\scripts\registrar.py . compra PETR4 50 36,00 --taxa 2,90 --data 2026-09-05
```

Ele ecoa o que entendeu, mostra o saldo depois e pede confirmação. `--dry-run` só mostra;
`--sim` grava sem perguntar, que é como a LLM roda depois do seu "de acordo".

**O mês em que você não aportou** é a mesma conversa, com aporte zero: nenhuma sugestão, e
o `ESTADO.md` diz o que o mercado moveu nas suas bandas. Sem ritual, sem comando novo.

<!-- ensina: vendi-ou-recebi -->
## O que eu faço quando vendo, ou quando cai provento

Mesma skill, mesmo comando, verbo diferente.

```powershell
python <motor>\scripts\registrar.py . venda PETR4 50 41,00 --data 2026-10-02
python <motor>\scripts\registrar.py . provento HGLG11 45,30 --tipo rendimento --data 2026-09-10
python <motor>\scripts\registrar.py . evento PETR4 split --razao 2:1 --data 2026-09-18 --confirmar
```

A venda baixa ao preço médio corrente, mostra o resultado realizado e grava um log em
`logs/vendas/`. O provento entra no livro, em `dados/proventos.csv`. O desdobramento é
aplicado ao saldo, e evento que o livro não sabe aplicar vira erro com nome, nunca silêncio.
Errou um registro? `estorno` repete a linha errada e ela sai da linha do tempo: nada em
`dados/` se edita à mão.

Se o provento já vem no extrato de movimentação da B3, você não precisa registrar nada:
importe o extrato pelo `/jabuti-importar` e ele entra por ali. E quando a sua corretora
discordar do seu livro, reimporte a foto de posições com `--conferir`: o motor faz a
aritmética da diferença, diz o que ela pode significar e entrega o comando de cada
hipótese. Ele nunca escolhe por você.

<!-- ensina: onde-a-finnest-entra -->
## Onde a Finnest entra

**Primeiro, o vínculo, porque ele muda como você lê o resto.** O autor deste repositório é
co-founder da [Finnest](https://finnest.com.br). Publicidade velada é vedada pelo CONAR e
pelo art. 36 do CDC, e contradiz a tese deste projeto, que é tornar visível o conflito de
quem aconselha.

**O que existe hoje: duas skills, opcionais, só leitura.** O jabuti conhece a sua carteira.
A Finnest conhece o seu mês: renda, despesa, cartão e dívida. São as duas perguntas que o
método precisa e que, sem ela, o `/jabuti-init` manda você responder de cabeça:

| Cole | A pergunta que responde |
|---|---|
| `/jabuti-capacidade` | quanto eu posso aportar este mês, medido em três meses de fluxo de caixa em vez de chutado. Grava `custo-vida-mensal` e `capacidade-aporte-mensal` no seu perfil, com log de decisão ao lado |
| `/jabuti-divida` | tenho fatura ou empréstimo em aberto: aporto ou quito primeiro? Rotativo de cartão na frente de ação é dinheiro perdido, e sem a medição o motor não tem como saber que o rotativo existe |

As duas exigem o MCP da Finnest conectado na sessão. Como conectar, o que cada uma lê e o que
nunca faz está em [docs/finnest-skills.md](docs/finnest-skills.md). Sem a conexão, cada uma
para e declara.

**Três limites que valem desde já.** O motor pede **um** escopo, `read:financial`; executar
transferência, pagar boleto e mexer em conexão ficam fora, com o motivo no GUARDRAILS e um
teste que quebra o build se uma tool fora do teto aparecer numa skill. Nenhuma das duas
**escreve na sua carteira**: o único número que chega ao workspace é o que você manda gravar
no perfil, e `dados/` só recebe operação conciliada contra documento ou declarada por você.
E a Finnest é atalho, nunca requisito: quem não quiser conectar banco nenhum usa o produto
do começo ao fim pelo caminho do extrato.

**O que não existe, dito no presente:** ingestão por provider. Nenhum adaptador escreve em
`dados/` a partir de uma API, da Finnest ou de qualquer outra, e a tabela de movimentações
que essa ingestão alimentaria não está no workspace. O `GUARDRAILS.md` carrega essa ressalva
com um teste que cobra as duas vias: a presença dela hoje e a remoção no dia em que houver
adaptador. É trabalho da versão seguinte (v1.1); a medição do servidor, feita para quem for
escrevê-lo, está em [docs/provider-finnest.md](docs/provider-finnest.md).

## Estrutura do repositório

| Pasta | O que mora |
|---|---|
| `templates/` | a árvore de workspace que `criar_workspace.py` copia, e os esqueletos de documento |
| `scripts/` | os CLIs e o pacote `po/`: validador, instanciador, cotações, ingestão, registro, geradores |
| `mapeamentos/` | documento de corretora → `dados/`, em YAML; superfície de contribuição |
| `skills/` | os procedimentos que a LLM executa, copiados para o seu workspace; catálogo em `skills/README.md` |
| `exemplos/` | um workspace fictício completo, validado em todo commit |
| `metodo/` | as rubricas do método, sem número pessoal |
| `rules/` | o núcleo de voz, fonte do harness compilado |
| `tests/` | a suíte, rodada pelo pre-commit e pela CI em 12 combinações |
| `docs/` | a vitrine das skills Finnest e a medição do servidor dela |
| `fiscal/` | onde os pacotes tributários por ano-fiscal vão morar, com validade declarada; hoje só o README que fixa a regra |

O que mudou desde a sua última atualização está em [CHANGELOG.md](CHANGELOG.md).

## Privacidade

O seu workspace é **privado por desenho** e nasce com git local, sem remoto. Extratos ficam
em `inbox/` fora do versionamento; o cockpit xlsx é regenerável e não versionado. O que sai
da sua máquina são três coisas, enumeradas e explicadas em **[PRIVACIDADE.md](PRIVACIDADE.md)**,
inclusive a maior delas, que é o conteúdo que você mostra à sua LLM.

Se você versionar o workspace num remoto, declare-o em `vault.config.yaml`: o validador
cobra, porque um push para repositório público não se desfaz.

## Contribuindo

Método canônico muda por issue, não por PR. As bordas estão abertas: mapeamentos de
corretora, providers de cotação, pacotes fiscais, testes. A regra dura é fixture sintética,
nunca extrato real. Tudo em **[CONTRIBUTING.md](CONTRIBUTING.md)**.

## Licença e aviso

Apache-2.0. **Não é recomendação de investimento**: o aviso legal completo está em
[GUARDRAILS.md](GUARDRAILS.md).

---

## English

**jabuti** is an open-source, LLM-operated personal portfolio system for Brazilian investors,
built under strict anti-hallucination guardrails: prices only via scripts with source and
timestamp, broker statements ingested through declarative YAML mappings with arithmetic
reconciliation against the document itself, and user-declared policy as the only decision
maker. It ships a guided onboarding (profile, allocation policy, portfolio import), a monthly
routine (decide where to contribute, record what happened, sales, dividends, corporate
actions), a canonical CSV data layer with a validator that runs on every commit, and a
compiled Claude Code harness. Asset selection inside each block and tax support are outside
this release. Portuguese-first by design; code contributions welcome, see CONTRIBUTING.md.
