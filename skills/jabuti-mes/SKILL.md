---
name: jabuti-mes
description: "Use quando o usuário pedir '/jabuti-mes', 'onde aporto esse mês', 'fechar o mês', 'comprei X', 'registrar compra', 'vendi', 'caiu provento', 'teve split', ou abrir uma sessão num workspace com o onboarding fechado. Abre com UMA pergunta: decidir onde aportar, ou registrar o que já aconteceu? Ramo A roda scripts/atualizar_cotacoes.py, scripts/gerar_estado.py e scripts/consultar_aporte.py e traduz as três alternativas de distribuição para a pessoa escolher. Ramo B roda scripts/registrar.py (compra, venda, provento, evento, ativo, estorno) com eco de confirmação e log datado. A LLM nunca digita preço nem divide o aporte de cabeça: os dois números saem de script."
---

# jabuti-mes — o mês, todo mês

## Quando usar

- Todo mês, uma vez, com ou sem aporte
- Quando a pessoa disser que comprou, vendeu, recebeu provento ou viu um evento societário
- Quando ela quiser saber onde o dinheiro do mês deve entrar

Frases típicas: "/jabuti-mes", "onde aporto", "comprei 50 PETR4 a 36", "vendi", "caiu rendimento".

## Princípio operacional

- **Uma pergunta, dois ramos.** Abrir com: *"decidir onde aportar, ou registrar o que já aconteceu?"* Nada antes dela.
- **O modelo não divide dinheiro.** A fila sai de `consultar_aporte.py`, que executa a política declarada. A LLM traduz; não calcula gap, não ranqueia ativo, não escolhe ticker.
- **O modelo não digita preço.** Cotação entra por script, com fonte, data e hora.
- **Operação da pessoa entra por `registrar.py`**, com eco de confirmação e log datado. É a fronteira inteira: preço de mercado por script, fato seu por comando com eco.
- **Valor declarado não é valor conferido.** O CLI imprime isso; a conferência contra a corretora é a importação de foto, e ela pega no mês seguinte, não no ato.
- `dados/` é append-only e nada ali se edita à mão, nem para consertar divergência.

## Contexto canônico a ler antes

- `estado/ESTADO.md`: primeira leitura de qualquer pergunta de alocação. É gerado; desatualizado, regenerar antes de ler.
- `politica/01-alocacao-alvo.md`: bandas e caps. É o que `consultar_aporte.py` executa.
- `vault.config.yaml`: `caminhos.motor`, contas e moedas.

## Fluxo — ramo A, decidir (antes de comprar)

1. `python <motor>/scripts/atualizar_cotacoes.py .` — ver a seção Cotações abaixo. Só passa ao 2 quando a saída não trouxer `Falta você informar`.
2. `python <motor>/scripts/gerar_estado.py .` — ESTADO derivado do ledger.
3. `python <motor>/scripts/consultar_aporte.py . <valor> --todos` — a fila por bloco, com gap e sugerido, nas **três alternativas**: cascata pura por gap, concentrar tudo no bloco mais fora da banda, espalhar proporcionalmente ao gap.
4. Traduzir a saída, com o racional de cada alternativa, e dizer o que a política aponta. Nunca "recomendo comprar X": esta skill decide **bloco**, nunca ticker.
5. A pessoa escolhe. Gravar `logs/decisoes/AAAA-MM-DD-aporte.md` (frontmatter `tipo: log-decisao`) com as alternativas, a escolhida e o racional dela.
6. Fim. Quando a compra acontecer, ela volta pelo ramo B.

## Fluxo — ramo B, registrar (depois de comprar)

1. Coletar o que falta, uma pergunta por vez: ticker, quantidade, preço, taxa, conta, data.
2. `python <motor>/scripts/registrar.py . compra <TICKER> <QTY> <PRECO> --taxa <T> --data AAAA-MM-DD --dry-run`
3. Ler o eco para a pessoa e esperar o "de acordo". Rodar de novo com `--sim` no lugar de `--dry-run` (sem terminal, o CLI não pergunta: sem `--sim` nada é gravado).
4. `atualizar_cotacoes.py` → `gerar_estado.py` → `validar_workspace.py`.
5. Dizer o que mudou: bloco, banda, o que entrou ou saiu de faixa.

## Cotações

Ramificar pelo **código de saída**, nunca pelo texto:

| Código | Significa | O que fazer |
|---|---|---|
| 0 | tudo obtido e gravado | seguir |
| 1 | rodada abortada — **nada gravado** | ler a frase, corrigir a causa, rodar de novo |
| 2 | sem rede — nada gravado | parar e declarar; nunca preço de memória |
| 3 | parcial: parte obtida, parte falhou | **não seguir**: perguntar o que falta (abaixo) |

**Código 1 não é "quase deu certo"**: é o oposto de 3. Tratar 1 como sucesso parcial faz a carteira ser lida com preço velho sem ninguém avisar.

- **Sem rede: parar e declarar.** Não repetir preço de memória, não estimar, não usar "o último conhecido" como se fosse novo.
- **`--manual TICKER=PRECO` só com valor que a pessoa colou nesta conversa.** A fonte fica gravada como `manual`.
- **O que o cotador não alcança** (fundo, previdência, renda fixa, ticker que o provider não acha): a saída fecha com `Falta você informar (não consegui atualizar sozinho):`, o último valor de cada um e o `--manual` pronto. Dizer: *"já atualizei o que tem cotação; não consegui atualizar sozinho X e Y. Qual o valor atual de cada um?"*, uma pergunta por vez, e rodar o `--manual`. **Enquanto a lista existir, a posição do mês não está atualizada: nada de `gerar_estado.py` nem `consultar_aporte.py`.** Sem o valor agora, quem decide seguir é a pessoa, e o log da decisão registra qual ativo ficou com valor de qual data. Saldo em conta (`caixa`) não entra: vale 1,00 na própria moeda, fonte `definicao`.
- **Variação acima de 30%**: o script grava a cotação e propõe um evento em `dados/eventos.csv`. Split, grupamento ou ticker trocado são as causas comuns; quem confirma é a pessoa, pelo `registrar.py evento`. Evento já confirmado entre a última cotação e a nova ajusta a base da comparação: recotar depois de confirmar não propõe o mesmo evento de novo.

## Casos especiais

- **Mês sem aporte**: ramo A com `consultar_aporte.py . 0`. Sobra zero, nenhuma sugestão, e o ESTADO diz o que o mercado moveu nas bandas. Não há ritual de fechamento separado.
- **Carteira vazia**: o ESTADO sai com uma linha só ("Nenhuma posição em `dados/` ainda", com o `registrar.py . compra` pronto), sem total nem pendência. Oferecer o ramo B.
- **Provento**: `registrar.py . provento <TICKER> <VALOR> --tipo rendimento --data ...`. Se o extrato entrar por `/jabuti-importar`, não registrar de novo.
- **Venda**: `registrar.py . venda <TICKER> <QTY> <PRECO> --data ...`. O CLI baixa ao PM corrente, imprime o resultado realizado e grava `logs/vendas/`. Venda acima do saldo é recusada com a frase pronta.
- **Evento societário**: `registrar.py . evento <TICKER> split --razao 2:1 --data ... --confirmar`. A razão é sempre `novas:antigas`. Tipo que o ledger não sabe aplicar (`cisao`, `fusao`, `subscricao`) é erro nomeado: registrar o efeito como fill e deixar o evento como registro não aplicável.
- **Ticker novo**: fill de ticker sem linha em `dados/ativos.csv` acusa erro com o comando pronto, `registrar.py . ativo <TICKER>=<classe>`. `ativos.csv` é declaração sua, e é a única coisa em `dados/` que se edita à mão.
- **Errei o registro**: `registrar.py . estorno <TICKER> <QTY> <PRECO> --data ...` repetindo a linha do fill errado, que sai da linha do tempo. Casou zero ou mais de um, o CLI recusa e diz qual. Nunca editar `dados/fills.csv`.
- **A corretora diz outro número**: é conferência, nunca escrita — `/jabuti-importar` com `--conferir`. O motor faz a aritmética e entrega o comando; a corretora não sobrescreve o seu histórico.

## O que esta skill NÃO faz

- **Não escolhe ativo nem ranqueia ticker**: decide bloco, executando a política declarada
- **Não digita preço** e não estima: sem rede, para e declara
- **Não calcula a fila de aporte de cabeça** (→ `consultar_aporte.py`)
- **Não edita `dados/` à mão**, nem para consertar divergência
- **Não importa documento de corretora** (→ `/jabuti-importar`)
- **Não altera política, perfil nem banda** (→ `/jabuti-estrategia`)
- **Não commita**
