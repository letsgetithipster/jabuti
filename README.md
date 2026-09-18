# jabuti

[![ci](https://github.com/letsgetithipster/jabuti/actions/workflows/ci.yml/badge.svg)](https://github.com/letsgetithipster/jabuti/actions/workflows/ci.yml)

Suas finanças em arquivos de texto simples, operadas pela LLM que você já usa, com regras que
não deixam número inventado entrar. Ele organiza e confere; quem decide é você.

O jabuti não corre: vive oitenta anos e chega. Feito por brasileiros, para brasileiros.

<!-- ensina: o-que-e -->
## O que é isto

Na prática, o jabuti vira uma pasta no seu computador. Nela ficam alguns arquivos de texto
que dizem quem você é e qual regra você escolheu para dividir o seu dinheiro, e cinco
planilhas CSV com o que você comprou, quando e a que preço. Alguns comandos leem esses
arquivos e escrevem um resumo que cabe numa tela. O [GUARDRAILS.md](GUARDRAILS.md) é o
contrato que a LLM segue, e ele a proíbe de inventar número.

O jabuti não é corretora nem aplicativo, não movimenta dinheiro e não vende nada. Para usar,
você conversa com a LLM no terminal e ela roda os comandos; não é preciso saber programar.

Cada etapa é uma skill, uma conversa guiada que você começa colando o nome dela na LLM. O
caminho tem quatro, na ordem em que você vai usar:

| | Quando | Cole | Para quê |
|---|---|---|---|
| 1 | no primeiro dia | `/jabuti-init` | contar quem você é: idade, horizonte, custo de vida e quanto de queda você aguenta |
| 2 | no primeiro dia | `/jabuti-estrategia` | escolher como dividir o dinheiro entre os tipos de investimento |
| 3 | no primeiro dia, e a cada extrato novo | `/jabuti-importar` | trazer a carteira que você já tem, pelo extrato da corretora |
| 4 | todo mês | `/jabuti-mes` | atualizar as cotações, informar o valor dos fundos, decidir onde vai o aporte e registrar compra, venda e provento |

Se você conecta a Finnest, ganha duas skills de bônus, que leem as suas contas pelo Open
Finance e medem o que, sem ela, você calcula à mão no app do banco:

| Quando | Cole | Para quê |
|---|---|---|
| depois do perfil, e quando a sua renda ou despesa mudar | `/jabuti-capacidade` | medir o seu custo de vida e quanto sobra por mês |
| antes do aporte, se houver fatura ou empréstimo em aberto | `/jabuti-divida` | pôr o custo da dívida ao lado do aporte do mês |

Nenhuma das quatro skills do caminho depende delas. Como a Finnest entra no modelo está em
[onde a Finnest entra](#onde-a-finnest-entra).

Com os dados de exemplo que vêm no repositório, sem configurar nada, o resumo sai assim:

<!-- demo:start -->
```
$ python scripts/gerar_estado.py exemplos/workspace-exemplo --data 2026-09-08
estado/ESTADO.md regenerado — Total investido: R$ 12.000,00
Pendências:
- fiis acima da banda máxima (66,7% vs 40%): rebalancear via aporte nos blocos abaixo
- rf-br abaixo do mínimo (0,0% vs 25%): priorizar nos próximos aportes
```
<!-- demo:end -->

Os números saem dos CSVs: cada cotação tem fonte, data e hora, e o validador recalcula os
totais a cada commit.

> Leia o [GUARDRAILS.md](GUARDRAILS.md) antes de usar. Ele define o que a LLM pode e não pode
> fazer com os seus números, e traz o aviso legal.

<!-- ensina: por-que -->
## Por que eu usaria

Assessoria tradicional custa de 0,5% a 2% ao ano, ou é paga por quem distribui o produto que
ela recomenda a você. É um conflito de interesse que vem do modelo de remuneração, sem que
ninguém precise agir de má-fé. Um family office dedicado só atende quem tem alguns milhões.

A LLM que você já assina sabe muito sobre investimentos, mas falta a ela o que este
repositório acrescenta. A primeira coisa é memória: cada conversa nova com a LLM começa do
zero, e aqui a sua política, as suas operações e o seu histórico ficam em arquivo e são
relidos toda vez. A segunda é número confiável. Preço entra por script, com fonte e hora, e
extrato de corretora só entra quando a conta do próprio documento fecha, então o modelo nunca
digita um número de mercado. A terceira é uma regra escrita com calma: você declara as faixas
em que quer ficar e, nos dias ruins, o sistema aplica a regra que você escreveu e mostra quando
ela foi atingida.

Funciona como um family office de uma pessoa só, e o custo é a assinatura de LLM que você já
paga.

<!-- ensina: antes-de-comecar -->
## O que eu preciso antes de começar

São quatro coisas, e você provavelmente já tem três.

1. Um computador com Windows, macOS ou Linux, Python 3.11 ou mais novo e git.
2. Uma assinatura de LLM que trabalhe no terminal. Por enquanto o jabuti vem configurado para
   o Claude Code.
3. Uns 30 minutos, uma vez só, para as conversas do primeiro dia.
4. Se você já investe, o extrato ou o relatório de posições da sua corretora, em CSV ou xlsx.
   Serve qualquer corretora, porque o motor lê o arquivo através de um mapeamento em YAML. Já
   vêm prontos em `mapeamentos/` os da Clear, da Schwab, da movimentação da B3 e um CSV
   genérico de posições; para outra corretora, a LLM escreve o mapeamento e mostra a você
   antes de rodar.

Se você nunca investiu, bastam os três primeiros itens. Não é preciso ter dinheiro aplicado
para começar: com a carteira vazia, o resumo diz que ainda não há posição e mostra o comando
para registrar a primeira compra.

Você também não precisa saber programar, ter conta numa corretora específica, conectar o seu
banco ou pagar nada a este projeto.

<!-- ensina: primeiro-dia -->
## O que eu faço no primeiro dia

Quatro comandos de terminal e três conversas.

```powershell
git clone https://github.com/letsgetithipster/jabuti.git
cd jabuti
python -m pip install -r requirements.txt
python scripts/criar_workspace.py C:\caminho\meu-vault
```

No macOS e no Linux, troque os caminhos: `python3 scripts/criar_workspace.py ~/meu-vault`.
Para ler extrato em xlsx e gerar o cockpit em planilha, rode também
`python -m pip install -r requirements-xlsx.txt`.

O último comando cria a sua pasta, separada deste repositório: os seus dados ficam nela, e o
método fica aqui. Abra a LLM dentro da sua pasta e cole uma conversa de cada vez:

| Cole | O que acontece |
|---|---|
| `/jabuti-init` | você responde, uma pergunta por vez, quem é: idade, horizonte, custo de vida, como reagiria a uma queda de 30%. As respostas viram `politica/00-perfil.md`, e o validador refaz as contas que saem delas. A taxa usada nessas contas vem do método, nunca da memória do modelo |
| `/jabuti-estrategia` | você escolhe como dividir o dinheiro entre três alternativas explicadas, ou declara a divisão que já usa. O resultado é uma tabela de faixas por tipo de investimento (as bandas) e um registro datado da sua decisão |
| `/jabuti-importar` | você traz a carteira que já tem, pelo extrato da corretora. Se ainda não tem nada, responde isso e o primeiro dia termina aí |

Cada conversa termina dizendo qual é a próxima, e `estado/SETUP.md` guarda onde você parou.
No fim, `estado/ESTADO.md` mostra a sua carteira comparada com a política que você escolheu.

<!-- ensina: todo-mes -->
## O que eu faço todo mês

Você abre a LLM na sua pasta e cola `/jabuti-mes`. A conversa começa com uma pergunta: você
quer decidir onde aportar ou registrar o que já aconteceu?

Para decidir, antes de comprar, a skill atualiza as cotações, refaz o `ESTADO.md` e calcula a
fila de aporte com a política que você declarou. Nos comandos abaixo, `<motor>` é a pasta onde
você clonou o jabuti e `.` é a sua pasta:

```powershell
python <motor>\scripts\atualizar_cotacoes.py .
python <motor>\scripts\gerar_estado.py .
python <motor>\scripts\consultar_aporte.py . 1500 --todos
```

As cotações vêm do serviço configurado em `vault.config.yaml`; o padrão é o `yahoo`, que não
pede cadastro nem token. Sem internet, o script para e avisa, e nunca usa preço de memória.
Fundo, previdência e renda fixa não têm cotação que um script consiga buscar. Nesses casos o
cotador termina com a lista do que ficou sem valor novo, o último valor conhecido de cada um e
o comando `--manual TICKER=PRECO` pronto, e a `/jabuti-mes` pergunta a você os valores atuais
antes de calcular a fila. O `--manual` também serve se você prefere que nada saia pela rede;
o preço fica gravado com a fonte `manual`.

Quem calcula a fila é uma função testada, e não o modelo. Ela ordena os blocos pela distância
até o alvo e mostra três formas de distribuir o dinheiro. A LLM explica o resultado, você
escolhe, e a escolha fica num log de decisão datado. A saída termina sempre com a frase
*isto executa a política que você declarou; não é recomendação de investimento.*

Para registrar uma compra, depois de feita:

```powershell
python <motor>\scripts\registrar.py . compra PETR4 50 36,00 --taxa 2,90 --data 2026-09-05
```

O comando repete o que entendeu, mostra como fica o saldo e pede confirmação. Com `--dry-run`
ele só mostra; com `--sim` grava sem perguntar, que é o que a LLM usa depois do seu "de acordo".

No mês em que você não aporta, a conversa é a mesma, com aporte zero: não sai sugestão, e o
`ESTADO.md` mostra o que o mercado mudou nas suas faixas.

<!-- ensina: vendi-ou-recebi -->
## O que eu faço quando vendo, ou quando cai provento

Use a mesma `/jabuti-mes` e o mesmo `registrar.py`, trocando o verbo:

```powershell
python <motor>\scripts\registrar.py . venda PETR4 50 41,00 --data 2026-10-02
python <motor>\scripts\registrar.py . provento HGLG11 45,30 --tipo rendimento --data 2026-09-10
python <motor>\scripts\registrar.py . evento PETR4 split --razao 2:1 --data 2026-09-18 --confirmar
```

A venda baixa a posição pelo preço médio atual, mostra o resultado realizado e grava um
registro em `logs/vendas/`. O provento vai para `dados/proventos.csv`. O desdobramento (split)
é aplicado ao saldo, e um evento que o livro não sabe aplicar gera um erro que diz qual é. Se
você errou um registro, o `estorno` repete a linha errada e ela deixa de valer. Nada em
`dados/` é editado à mão.

Se o provento já aparece no extrato de movimentação da B3, importe o extrato pelo
`/jabuti-importar` e ele entra por ali, sem registro manual. Quando a corretora mostrar um
número diferente do seu livro, importe de novo a posição com `--conferir`: o motor calcula a
diferença, explica o que ela pode significar e mostra o comando para cada hipótese, e a
escolha fica com você.

<!-- ensina: onde-a-finnest-entra -->
## Onde a Finnest entra

O jabuti conhece a sua carteira. A [Finnest](https://finnest.com.br) lê as suas contas pelo
Open Finance e conhece o seu mês: renda, despesa, cartão e dívida. Quem escreveu o jabuti
também é cofundador da Finnest. Para quem a conecta, ela acrescenta duas skills de bônus, e a
rotina do mês continua a mesma com ou sem elas.

O `/jabuti-capacidade` lê três meses fechados do seu fluxo de caixa e grava no perfil o custo
de vida e a capacidade de aporte que você escolher entre os três, no lugar da conta que você
faria à mão. O `/jabuti-divida` põe a fatura e os empréstimos em aberto ao lado do aporte do
mês e abre três alternativas para você decidir se quita ou investe primeiro. Comprar ação
enquanto paga rotativo de cartão é perder dinheiro, e sem essa leitura o jabuti não tem como
saber que o rotativo existe.

As duas pedem o MCP da Finnest conectado na sessão. Como conectar, o que cada uma lê e o que
nunca faz está em [docs/finnest-skills.md](docs/finnest-skills.md). Sem a conexão, cada uma
para e avisa.

As duas só leem. O jabuti pede à Finnest um único escopo, `read:financial`: transferir
dinheiro, pagar boleto e mexer nas suas conexões ficam de fora, e um teste quebra o build se
alguma skill citar uma tool além desse limite (o motivo está no GUARDRAILS). Nada da Finnest
entra na sua carteira. O único número que chega à sua pasta é o que você manda gravar no
perfil, e `dados/` só recebe operação conferida contra documento ou declarada por você. Quem
preferir não conectar banco nenhum usa o jabuti inteiro pelo caminho do extrato.

A importação automática pela Finnest ainda não existe: nenhum adaptador grava em `dados/` a
partir de uma API, e a tabela de movimentações que ele alimentaria não está no workspace. O
`GUARDRAILS.md` registra essa ressalva, e um teste cobra as duas pontas: que ela esteja lá
hoje e que saia no dia em que o adaptador existir. O adaptador fica para a v1.1, e a medição
do servidor da Finnest, para quem for escrevê-lo, está em
[docs/provider-finnest.md](docs/provider-finnest.md).

## Estrutura do repositório

| Pasta | O que tem |
|---|---|
| `templates/` | a estrutura da sua pasta, que `criar_workspace.py` copia, e os esqueletos de documento |
| `scripts/` | os comandos e o pacote `po/`: validador, criação da pasta, cotações, importação, registro e geradores |
| `mapeamentos/` | como ler o arquivo de cada corretora, em YAML; é onde contribuir é mais fácil |
| `skills/` | as conversas guiadas que a LLM executa, copiadas para a sua pasta; catálogo em `skills/README.md` |
| `exemplos/` | uma pasta fictícia completa, validada a cada commit |
| `metodo/` | as regras do método, sem dado pessoal |
| `rules/` | o texto de voz da LLM, que vira o `CLAUDE.md` da sua pasta |
| `tests/` | a suíte, rodada pelo pre-commit e pela CI em 12 combinações |
| `docs/` | a documentação das skills da Finnest e a medição do servidor dela |
| `fiscal/` | onde vão ficar os pacotes de imposto de cada ano, com validade declarada; hoje só tem o README com a regra |

O que mudou desde a sua última atualização está no [CHANGELOG.md](CHANGELOG.md).

## Privacidade

A sua pasta é privada desde o início: nasce com git local, sem remoto. Os extratos ficam em
`inbox/`, fora do versionamento, e o cockpit em xlsx pode ser gerado de novo a qualquer hora,
então também não é versionado. Três coisas saem da sua máquina, e o
[PRIVACIDADE.md](PRIVACIDADE.md) explica cada uma, inclusive a maior delas: o que você mostra à
sua LLM.

Se você enviar a sua pasta para um repositório remoto, declare isso em `vault.config.yaml`. O
validador cobra a declaração, porque um push para repositório público não se desfaz.

## Contribuindo

Mudança no método se propõe por issue. Pull requests são bem-vindos nas bordas: mapeamentos de
corretora, fontes de cotação, pacotes fiscais e testes. Toda fixture de teste é sintética;
extrato real não entra. Os detalhes estão no [CONTRIBUTING.md](CONTRIBUTING.md).

## Licença e aviso

Licença Apache-2.0. **Não é recomendação de investimento.** O aviso legal completo está no
[GUARDRAILS.md](GUARDRAILS.md).

---

## English

**jabuti** is an open-source personal portfolio system for Brazilian investors, operated by
the LLM you already use. Prices enter only through scripts, with source and timestamp; broker
statements are read through declarative YAML mappings and accepted only when the document's
own arithmetic reconciles; and the allocation policy you declare is the only thing that makes
decisions. It ships a guided onboarding (profile, allocation policy, portfolio import), a
monthly routine (where to contribute, purchases, sales, dividends, corporate actions), a CSV
data layer with a validator that runs on every commit, and a compiled Claude Code harness.
Two optional bonus skills, read-only, measure cash flow and debt through Finnest, which reads bank
accounts via Brazil's Open Finance and was co-founded by the author; neither writes to the
portfolio. Picking assets inside each block and tax support are outside this release. The
project is written in Portuguese first; code contributions are welcome, see CONTRIBUTING.md.
