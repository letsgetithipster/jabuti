---
name: atualizar-cotacoes
description: "Use quando o usuário pedir 'atualizar cotações', 'atualiza os preços', 'refresh de cotações', '/atualizar-cotacoes' ou variação que indique buscar preço de mercado para as posições do workspace. Roda scripts/atualizar_cotacoes.py do motor: posicoes.csv → provider da config (yahoo, brapi; câmbio via bcb-sgs) → append em dados/cotacoes.csv com fonte, data e hora. Puramente mecânica: NÃO decide aporte, NÃO registra compra, NÃO altera posição, nota ou tese. Sem internet na sessão: PARA e declara — nunca preço de memória. Variação acima de 30% vira proposta em dados/eventos.csv para o usuário confirmar."
---

# Atualizar cotações

## Quando usar

- Antes de olhar alocação, banda ou fila de aporte (o número do ESTADO e do cockpit depende disto)
- Quando o usuário quiser a carteira com preço do dia

Frases típicas: "atualiza as cotações", "refresh de preços", "/atualizar-cotacoes".

## Princípio operacional

- **O modelo não digita preço.** O script busca, valida a moeda, carimba fonte/data/hora e anexa. O papel da LLM é rodar, ler o relatório e traduzir os alertas.
- **Sem rede: parar e declarar.** O script sai com código 2 e "Sem acesso à rede". Não repita preço de memória, não estime, não "use o último conhecido" como se fosse novo.
- **Cotação manual é do usuário.** `--manual TICKER=PRECO` só com valor que o usuário passou nesta conversa (colado da tela da corretora). A fonte fica gravada como `manual`.
- Append-only: nada em `cotacoes.csv` é reescrito. A cotação vencedora é a de data mais recente.

## Contexto canônico a ler antes

- `vault.config.yaml`: `cotacoes.provider` (yahoo | brapi | manual) e `cotacoes.cambio` (bcb-sgs | yahoo | manual). `brapi` exige a variável de ambiente `BRAPI_TOKEN` e cobre **só a B3 em BRL**: com ativo internacional na carteira, o provider é `yahoo`.
- `dados/posicoes.csv`: é de lá que saem os tickers. Posição fora do BRL puxa o par de câmbio automaticamente.

## Fluxo

1. Rodar `python <motor>/scripts/atualizar_cotacoes.py <raiz> --dry-run` (o caminho do motor está em `vault.config.yaml`, `caminhos.motor`).
2. Ler o relatório e traduzir:
   - **FALHA por classe sem mercado** (`rf-br`): pedir ao usuário o valor atual e rodar de novo com `--manual TICKER=VALOR`. Saldo em conta (classe `caixa` sem código da B3) **não** é falha: vale 1,00 na própria moeda por definição da unidade, com fonte `definicao`, e sai marcado assim no relatório.
   - **FALHA de ticker** (404, moeda diferente): conferir se o ticker mudou (fusão, troca de código) antes de qualquer coisa.
   - **Variação acima de 30%**: dizer ao usuário que o script vai gravar a cotação e propor um evento em `eventos.csv`; split, grupamento ou ticker trocado são as causas comuns. Quem confirma o evento (e o tipo real) é o usuário, editando `confirmado: sim` e o `tipo`.
3. Rodar sem `--dry-run`. Relatar quantas cotações entraram, quantas manuais, quantas falhas.
4. Sugerir `python <motor>/scripts/gerar_estado.py <raiz>` (ESTADO.md com o total novo) e, se o usuário usa o cockpit, `python <motor>/scripts/gerar_cockpit.py <raiz>` (exige openpyxl; a aba Aporte anuncia no topo quando a valoração trouxe avisos, e o detalhe fica no fim da aba LEIAME).
5. Se houver falha remanescente, deixar claro: "N posição(ões) sem cotação; o validador vai acusar até resolver".

## Códigos de saída (é por eles que a LLM ramifica, não pelo texto)

| Código | Significa | O que fazer |
|---|---|---|
| 0 | tudo obtido e gravado | seguir para `gerar_estado.py` |
| 1 | erro que impediu a rodada — **nada gravado** | ler a frase, corrigir a causa, rodar de novo |
| 2 | sem rede — nada gravado | parar e declarar; nunca preço de memória |
| 3 | resultado parcial: parte obtida, parte falhou | aceitável, mas declarar o que faltou |

**Código 1 não é "quase deu certo".** É o oposto de 3: rodada abortada, `cotacoes.csv` intocado. Tratar 1 como sucesso parcial faz a carteira ser lida com preço velho sem ninguém avisar.

## Casos especiais

- Provider `manual` na config sem `--manual`: o relatório lista cada ticker com a instrução; oferecer trocar `cotacoes.provider` para `yahoo`.
- `--dry-run` com falha em parte dos tickers também sai **3** (parte seria obtida). Com falha em tudo, sai 1.
- **A cotação entrou mas a proposta de anomalia não** (arquivo de eventos travado no Excel/OneDrive): o script avisa e imprime as linhas prontas para colar no fim de `dados/eventos.csv`. Cole-as, ou a anomalia some: o preço novo vira a base e a próxima comparação dá 0%.
- Cripto: o símbolo é `TICKER-MOEDA` (BTC-BRL para posição em BRL, BTC-USD para posição em USD).
- Ticker já cotado hoje aparece como "já definida hoje" e não é buscado de novo.

## O que esta skill NÃO faz

- **Não decide onde aportar** (→ `/consultar-aporte`, Fase 4)
- **Não registra compra nem venda** (→ `/registrar-aporte`, Fase 4)
- **Não confirma evento corporativo** — só propõe; confirmar e aplicar em qty/PM é do usuário e da Fase 4
- **Não altera posição, nota, tese ou política**
- **Não estima preço**: sem rede ou sem cotação = declarar
- **Não gera ESTADO.md nem cockpit sozinha** (→ `gerar_estado.py`, `gerar_cockpit.py`)
- **Não commita** (o usuário decide quando)
