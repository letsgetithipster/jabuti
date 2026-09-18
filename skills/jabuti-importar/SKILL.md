---
name: jabuti-importar
description: "Use quando o usuário pedir '/jabuti-importar', 'importar extrato', 'importa o CSV da corretora', 'sobe o export da Clear/Schwab/B3', 'popular o workspace com o extrato' ou variação que indique levar um documento exportado da corretora (CSV ou xlsx em inbox/) para dados/. Dois modos: com a linha do jabuti-importar aberta em estado/SETUP.md, roda o preâmbulo de onboarding (corretoras, propósito por conta, caminho de export) antes; fechada a linha, é a rotina de sempre. Divisão rígida: a LLM inspeciona o documento, escolhe ou ESCREVE o mapeamento (YAML em mapeamentos/) e o MOSTRA ao usuário; o script scripts/importar_extrato.py executa o parse e confere a aritmética declarada no próprio documento (saldo corrente, valor da linha ou total declarado). Não bateu, nada entra em dados/. A LLM nunca digita número de posição, provento ou fill."
---

# Importar extrato

## Quando usar

- Primeira carga do workspace a partir de um export de posições (qty e PM por ativo)
- Carga periódica de proventos, fills e eventos a partir do extrato/transactions da corretora
- Reconciliação: `--conferir` compara um export de posições com `dados/` sem gravar

Frases típicas: "importa o extrato da Clear", "sobe o CSV da Schwab", "/jabuti-importar inbox/x.xlsx".

## Princípio operacional

- **Quem lê o documento é o script.** A LLM lê o *dump* de `inspecionar_extrato.py`, não o binário, e nunca copia número dele para `dados/`.
- **Mapeamento é dado, e o usuário vê antes.** Se nenhum mapeamento pronto casa, a LLM escreve um YAML novo, `mapeamentos/meu-<corretora>.yaml` do workspace (vocabulário em `mapeamentos/README.md` do motor), mostra o arquivo inteiro ao usuário e só roda depois do "de acordo". O prefixo `meu-` vale nos dois modos: na pasta clonada, é ele que deixa o arquivo fora do git do jabuti, ao lado dos mapeamentos prontos.
- **Conciliação obrigatória.** Todo mapeamento declara como o documento prova a própria soma. Linha que não casa regra nenhuma PARA a importação; a LLM acrescenta a regra (ou um `ignorar` com motivo explícito) e mostra de novo.
- **Reimportar é seguro**: duplicata é pulada e contada. Nada em `dados/` é sobrescrito: posição que diverge da derivada do ledger (na data do documento) faz o motor calcular a diferença, nomear a leitura (compra, venda, ajuste de custo) e imprimir o comando `registrar.py` de cada saída, com exit 3 e nada gravado. A diferença é a operação que o livro ainda não tem; o motor não escolhe qual.
- **Posição não é tabela.** Cada linha de posição do documento vira um fill `saldo-inicial` em `fills.csv` (só para ticker/conta sem nenhum fill) e uma linha `ticker,classe` em `ativos.csv` (só para ticker ainda não declarado; a declaração da pessoa vence a do documento). Corretora que quebra a posição por lote ou por agente de custódia (B3 e Schwab fazem isso) gera UMA abertura consolidada por ticker/conta (qty somada, PM ponderado), e o log de importação nomeia a consolidação. Somar à mão em `dados/` não é opção.

## Contexto canônico a ler antes

- `vault.config.yaml`: ids das contas e moeda de cada uma (o mapeamento aponta uma conta; `--conta` sobrescreve; moeda do mapeamento e da conta têm que bater).
- `mapeamentos/README.md` do motor: vocabulário do mapeamento e os prontos (`clear-extrato` e `schwab-transacoes`, verificados contra export real; `b3-movimentacao` e `exemplo-posicoes-csv`, ainda não).
- `mapeamentos/` do workspace: mapeamentos que o usuário já tem. Sem `--mapeamento`, o script tenta detectar pelo cabeçalho, primeiro no workspace, depois no motor.

## Preâmbulo de onboarding (só com a linha do `/jabuti-importar` aberta no `SETUP.md`)

Etapa 3 de 5. Uma pergunta por vez:

1. **Quais corretoras você usa hoje?** Para cada uma: um `id` (minúsculas, sem espaço), a moeda, e o **propósito** — quais blocos aquela conta serve, do vocabulário `acoes-br, fiis, rv-int, reits-us, rf-br, cripto, caixa, commodities`. Propor o bloco `contas:` do `vault.config.yaml` inteiro, mostrar, e escrever depois do "de acordo" (`blocos: []` significa qualquer bloco). O validador cobra o vocabulário.
2. **Para cada conta, o caminho de export**, com honestidade sobre o que está verificado — a lista é a tabela "Prontos" de `mapeamentos/README.md` do motor, que diz mapeamento por mapeamento se foi conferido contra export real. Apontar para ela, não copiar. Corretora fora da lista cai no fluxo normal: a LLM escreve o mapeamento e mostra antes de rodar.
3. **Arquivo em `inbox/`**, e daí o fluxo abaixo, documento por documento.
4. **Estou do zero** (nenhuma corretora, nenhuma posição): pular tudo, marcar no `SETUP.md` `- [x] `/jabuti-importar` — n/a, começando do zero`, trocar `Próximo:` para `/jabuti-mes`, rodar `python <motor>/scripts/gerar_estado.py .` (sem posição o ESTADO sai com uma linha só, "Nenhuma posição em `dados/` ainda", com o `registrar.py . compra` pronto: nem total zero nem pendência inútil) e emitir o handoff.

Ao fim do último documento: rodar `python <motor>/scripts/gerar_estado.py .` e ler as **Pendências** com a pessoa. É a primeira vez que ela vê a carteira dela dentro da política dela — bloco acima ou abaixo da banda que acabou de declarar. Marcar `- [x]` na linha do `/jabuti-importar`, trocar `Próximo:` para `/jabuti-mes` e emitir o handoff.

Conta já declarada no config não é perguntada de novo; documento já importado é duplicata, pulada e contada.

## Fluxo

1. Confirmar o arquivo em `inbox/` e a conta de destino.
2. `python <motor>/scripts/inspecionar_extrato.py inbox/<arquivo>` e ler o dump (abas, cabeçalho, amostra, tipos das células).
3. Escolher o mapeamento:
   - Um pronto casa com o cabeçalho → seguir.
   - Nenhum casa → escrever `mapeamentos/meu-<corretora>.yaml` no workspace (nunca editar um mapeamento pronto do motor), com `verificado-contra-export-real: false`, `numeros:` lido da amostra (`pt-BR` se o documento escreve `1.234,56`; `en-US` se escreve `1,234.56` — é obrigatório e o motor não adivinha), regras explícitas para cada tipo de linha visto na amostra, e a conciliação que o documento permite (saldo corrente se há coluna de saldo; valor da linha se há qty × preço = valor; senão total declarado). **Mostrar o YAML ao usuário e esperar o de acordo.**
   - Rodapé de saldo **dentro** da tabela ("SALDO DISPONIVEL", "Saldo bloqueado") vira regra `ignorar` com `fora-da-cadeia: true`. `ignorar` sozinho só diz "não vira registro"; sem `fora-da-cadeia` a linha continua na aritmética do `saldo-corrente` e a quebra. Subir a `tolerancia` para esconder essa quebra é a saída errada: desliga a conferência do documento inteiro.
   - Documento sem coluna de data (posições): pedir ao usuário a data da posição para `--data`.
   - Conciliação `total-declarado` com `origem: flag`: pedir ao usuário o total que a corretora mostra e passar em `--total-declarado`. A LLM não calcula esse número.
4. `python <motor>/scripts/importar_extrato.py <raiz> inbox/<arquivo> --mapeamento <nome> [--conta] [--data] [--total-declarado] --dry-run`. Ler: contagens por tabela, ignoradas por motivo, regras que nunca casaram (aviso só no `--dry-run`), resultado da conciliação.
   - ERRO de linha não classificada → voltar ao passo 3 e acrescentar a regra.
   - ERRO de conciliação → não "ajustar" nada para bater: mostrar a linha apontada ao usuário; documento e mapeamento é que se corrigem.
   - ERRO "nenhuma linha de dados abaixo do cabeçalho" → aba errada, cabeçalho que o mapeamento não achou, ou export em branco: voltar ao `inspecionar_extrato.py`.
5. Rodar sem `--dry-run`. Relatar o que entrou (`fills +N (N aberturas, tipo=saldo-inicial) · ativos +N`, `proventos +N`...), duplicadas puladas e o caminho do log em `logs/importacoes/`.
6. Cada ticker sem nenhum fill ganha um fill `saldo-inicial`, a **abertura de livro**: "nesta data eu tinha isto, a este custo declarado". Dizer isso à pessoa com o caveat que o CLI imprime: a abertura é honesta sobre o custo e **muda sobre a data de aquisição**, então apuração de ganho de capital sobre lote coberto por abertura vai exigir a data real ou as notas do período. A condição é "sem fill", não "posição nova": ticker que já tem fill de verdade nunca ganha abertura sintética, e uma rodada de recuperação completa a que faltou sem duplicar nada. O log de importação registra quantas aberturas entraram.
7. Rodar `validar_workspace.py`. Posição importada sem cotação é ERRO esperado: seguir com `atualizar_cotacoes.py` (seção Cotações abaixo) e depois `python <motor>/scripts/gerar_estado.py <raiz>` (e `gerar_cockpit.py`, se o usuário usa o cockpit).

## Códigos de saída (é por eles que a LLM ramifica, não pelo texto)

| Código | Significa | O que fazer |
|---|---|---|
| 0 | importou, ou `--dry-run`/`--conferir` sem divergência | seguir o fluxo |
| 1 | erro que impediu a rodada: config, mapeamento, leitura, conciliação ou gravação | corrigir a causa apontada e rodar de novo |
| 2 | uso inválido da linha de comando (argparse) | conferir os argumentos |
| 3 | o documento contradiz o livro, com ou sem `--conferir` | nada gravado; ler a aritmética e o comando de cada saída (seção Conferência) |

`--conferir` é a rodada de diagnóstico: **3 = divergiu, 0 = não divergiu**. Não é erro de execução, é resultado — ramificar pelo código, não pelo texto do relatório.

## Casos especiais

- **Gravação que morre no meio** (arquivo aberto no Excel, disco cheio): sai **1**, mas parte entrou. É a **única** saída de erro em que `dados/` mudou. O script nomeia tabela por tabela o que chegou a entrar e aponta o log em `logs/importacoes/`. A recuperação é resolver a causa e **rodar de novo**: a importação é idempotente, o que já entrou não duplica. Nunca editar `dados/` à mão para "completar" o que faltou.
- **"N provento(s) apenas transcrito(s) do documento"** na descrição da conciliação **não é aviso de falha**: é a conciliação sendo honesta sobre linhas cujo valor gravado É a própria célula lida, ou seja, que não provam nada (os dois lados da comparação saem da mesma coluna). A importação segue normalmente. Traduzir assim ao usuário. Só quando **todos** os proventos são assim e nenhuma linha foi de fato conferida vira ERRO, com o remédio na própria mensagem: declarar `conciliacao.tipo: saldo-corrente`, ou apontar `proventos:` para um campo que o documento calcule (`valor_liquido`, quando há coluna de imposto).
- Extrato da Clear traz operações em bolsa agregadas por nota: fills por ticker NÃO saem dele (vêm da nota de corretagem ou do export de movimentação da B3). O mapeamento pronto ignora essas linhas com motivo.
- JCP em extrato brasileiro vem líquido: `valor_bruto` é gravado igual ao líquido e o mapeamento declara isso em `observacoes`.
- Schwab: `NRA Tax Adj` é ajuste do líquido do dividendo do mesmo dia/ticker; `Stock Split` e `Stock Merger` viram propostas em `eventos.csv` (confirmado `nao`) para o usuário completar a razão.
- `.xlsx` sem openpyxl instalado: o script diz `pip install -r requirements-xlsx.txt`; alternativa é o usuário exportar como CSV.
- **A foto da corretora diverge do livro**: não é conflito, é conferência, e ela tem próximo comando (seção Conferência abaixo). Nunca editar `dados/` para "bater".

## Conferência

Foto de posições que diverge do livro sai com **3 e nada gravado**, com ou sem `--conferir`. O script compara cada ticker/conta do documento contra a posição derivada dos fills **na data do documento**, faz a aritmética e imprime as leituras possíveis, cada uma com o comando pronto. Ler e traduzir; **não recalcular a diferença em prosa** — o número é do script. A corretora nunca sobrescreve o seu histórico: é o histórico que sustenta o IR.

O que a saída traz, ticker a ticker:

- `OK — qty @ PM`: livro e documento concordam.
- **Quantidade maior no documento**: a diferença em unidades e em custo, e o **preço implícito**. Três saídas, e a pessoa escolhe: compra ainda não registrada (`registrar.py . compra <TICKER> <QTY> <PRECO-IMPLICITO> --data <data-da-compra>`), evento societário (`registrar.py . evento <TICKER> split --razao <novas:antigas> --data <data> --confirmar`; aí o preço implícito não significa nada), ou `--aceitar-como compra`, que grava a diferença como fill datado **na foto**, não na operação (o CLI diz o custo disso para o IR na hora e no log).
- **Quantidade menor no documento**: a foto traz preço médio, não preço de venda, então não há preço implícito e o motor não o inventa. Saída: `registrar.py . venda <TICKER> <QTY> <preco-de-venda> --data <data-da-venda>`, com o preço que a pessoa informa.
- **Ticker no livro e ausente do documento**: se a posição foi zerada, registrar a venda; se o documento é de outra conta ou período, corrigir o arquivo.

Depois de registrar, rodar a importação de novo: ela passa quando livro e documento concordarem.

## Cotações

Posição importada sem cotação é ERRO esperado no validador. Rode `python <motor>/scripts/atualizar_cotacoes.py .` e ramifique pelo **código de saída**, nunca pelo texto:

| Código | Significa | O que fazer |
|---|---|---|
| 0 | tudo obtido e gravado | seguir para `gerar_estado.py` |
| 1 | rodada abortada — **nada gravado** | ler a frase, corrigir a causa, rodar de novo |
| 2 | sem rede — nada gravado | parar e declarar; nunca preço de memória |
| 3 | parcial: parte obtida, parte falhou | **não seguir**: perguntar o que falta (abaixo) |

**Código 1 não é "quase deu certo"**: é o oposto de 3. Tratar 1 como sucesso parcial faz a carteira ser lida com preço velho sem ninguém avisar.

- **`--manual TICKER=PRECO` só com valor que a pessoa colou nesta conversa.** A fonte fica gravada como `manual`.
- **O que o cotador não alcança** (fundo, previdência, renda fixa, ticker que o provider não acha): a saída fecha com `Falta você informar (não consegui atualizar sozinho):`, o último valor de cada um e o `--manual` pronto. Dizer: *"já atualizei o que tem cotação; não consegui atualizar sozinho X e Y. Qual o valor atual de cada um?"*, uma pergunta por vez, e rodar o `--manual`. **Enquanto a lista existir, a posição do mês não está atualizada: nada de `gerar_estado.py` nem `consultar_aporte.py`.** Sem o valor agora, quem decide seguir é a pessoa, e o log da decisão registra qual ativo ficou com valor de qual data. Saldo em conta (`caixa`) não entra: vale 1,00 na própria moeda, fonte `definicao`.
- **Variação acima de 30%**: o script grava a cotação e propõe um evento em `dados/eventos.csv`; quem confirma é a pessoa, pelo `registrar.py evento` do `/jabuti-mes`.

## O que esta skill NÃO faz

- **Não digita número**: nem posição, nem provento, nem fill, nem total declarado
- **Não escreve parser Python por corretora** — só mapeamento YAML
- **Não grava com conciliação falhando** e não "corrige" o documento para bater
- **Não aplica evento corporativo em qty/PM**: só registra a proposta; confirmar é `registrar.py evento --confirmar`, pelo `/jabuti-mes`
- **Não decide aporte nem registra operação sua** (→ `/jabuti-mes`)
- **Não regenera ESTADO/cockpit sozinha** (→ `gerar_estado.py`, `gerar_cockpit.py`)
- **Não commita**

## Próximo passo

Só no modo onboarding (linha aberta no `SETUP.md`), e só com o validador em zero erros e o `ESTADO.md` regenerado (do zero: sem posição, não há o que gerar). Fechada a linha, a skill termina em "feito", sem este bloco. Formato fixo:

```
✔ jabuti-importar concluído — carteira em dados/, lida dentro da política em estado/ESTADO.md.

Próximo: abra uma thread nova e cole
    /jabuti-mes

Tenha à mão: nada. É a rotina do mês, e ela começa perguntando o que você quer fazer.
```
