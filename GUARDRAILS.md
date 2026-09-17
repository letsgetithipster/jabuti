# GUARDRAILS — o contrato anti-alucinação do jabuti

Este documento existe para ser lido ANTES do primeiro uso. Ele responde à
pergunta certa: "por que eu confiaria numa LLM para operar minha carteira?"
Resposta: você não confia na LLM. Você confia nestas quatro camadas, que
valem para qualquer skill deste repo, em qualquer LLM.

Este documento é o contrato de TODAS as fases do produto; o que já está construído hoje está listado no README, seção "Estado atual".

## Camada 1 — Mecânica (script, não modelo)

- O modelo NÃO digita preço. Todo número de mercado entra por script, com
  fonte, data e hora gravadas em `dados/cotacoes.csv` (append-only).
- Sem internet na sessão: a skill PARA e declara. Nunca preço de memória.
- A fronteira do que VOCÊ pode digitar é esta, e ela é explícita: preço de
  mercado entra por script de cotação; OPERAÇÃO SUA (compra, venda, provento,
  estorno de um lançamento errado, a classe de um ticker) entra por
  `scripts/registrar.py`, com eco de confirmação,
  `--dry-run` e log datado. O que você declara ali nasce marcado como
  declarado por você, não conferido contra documento.
- Extrato de corretora só entra em `dados/` depois que o script confere a
  aritmética declarada no próprio documento (saldo corrente, valor da linha
  ou total declarado). O mapeamento do documento é um arquivo que você vê
  antes de rodar; linha que nenhuma regra explica PARA a importação.
- Imposto de renda é cálculo determinístico sobre `dados/`, com regras de
  um pacote fiscal versionado por ano (`fiscal/<ano>.yaml`) com validade
  estampada. A LLM nunca aplica alíquota de memória.
- O validador roda em todo commit (pre-commit) e recalcula totais. Ele
  falha ALTO se o Python estiver ausente — nunca passa em silêncio.

## Camada 2 — Estrutural (permissão de escrita)

- Cada skill declara onde escreve e o que NÃO faz. Editar fora da própria
  zona exige o seu "de acordo" explícito.
- `estado/ESTADO.md` tem escritor único (script), nunca edição à mão.
- Seus dados nunca saem do workspace: o repo do método (este) é público;
  o SEU workspace é privado por estrutura, com extratos em `inbox/`
  fora do versionamento.

## Camada 3 — Epistemológica (rotulagem)

- Análise rotula cada afirmação: [fato] / [inferência] / [opinião].
- Número de fonte externa é hipótese até conferido.
- Tese-semente (sem nota, `validada: false`) é visivelmente diferente de
  tese validada. Aporte não flui para semente.
- Toda rodada de pesquisa declara o que NÃO cobriu.

## Camada 4 — Decisória (política declarada)

- O sistema NUNCA decide. Ele apresenta alternativas com racional
  (tipicamente 3: conservadora / equilibrada / agressiva), você escolhe,
  e a escolha vira um log de decisão SEU, datado.
- Todo output de consulta termina com: "isto executa a política que você
  declarou; não é recomendação de investimento".

## Dado que vem de API

> **Estado hoje:** <!-- sentinela: nenhum-provider-ligado -->
> as três regras abaixo são o contrato, e o motor já tem as peças que as cumprem
> (o arquivador de payload, a coluna obrigatória de data de referência, a conferência de status).
> Mas **nenhum provider está ligado ainda** — nenhum adaptador existe, e portanto nada nesta seção
> descreve algo que você possa rodar hoje. O dia em que um adaptador entrar, esta ressalva sai, e
> há teste que cobra as duas coisas: a presença dela agora e a remoção dela depois.

A ingestão de documento tem uma garantia que a ingestão por API não tem: o arquivo que você
baixou é prova de si mesmo. Ele é imutável, reexecutável e auditável por um terceiro, e os três
tipos de conciliação comparam o documento contra a aritmética do próprio documento.

Resposta de API é volátil. Rodar de novo amanhã dá outro resultado, e o número de ontem deixa
de ser conferível. Por isso três regras valem só aqui:

1. **A resposta crua é arquivada** em `logs/importacoes/AAAA-MM-DD-<provider>.json`. Sem ela,
   "todo número tem origem rastreável" degenera em "o provider disse".
2. **A data de referência do provider é gravada** em cada linha, separada da data em que a
   importação rodou. Número de API sem idade declarada é pior que número de planilha, porque
   parece fresco.
3. **O status de sincronização é precondição.** Conta que parou de sincronizar devolve lista
   vazia sem erro; se a ingestão não conferir o status antes, o seu patrimônio encolhe em
   silêncio. Lacuna nunca é tratada como zero.

A conciliação desse dado se chama `soma-da-resposta` e é **declaradamente mais fraca** que as
outras três, porque compara a resposta contra uma afirmação de fora dela. Quando você ler
`soma-da-resposta` no relatório, é isso que ela quer dizer.

**Segredo nunca vai para argumento de tool MCP**, porque argumento entra no transcript do modelo.

## Modo mínimo viável (honestidade sobre cadência)

Obrigatórios: registrar aporte, fechar o mês, atualizar cotações.
Avançados (declarados como tais): radar de mercado, releases trimestrais,
destilados de fontes externas, watchlist ativa.
Dado velho é tratado como alerta de primeira classe: o fechamento avisa
quando algo está defasado demais para sustentar análise.

## Aviso legal

O jabuti é uma ferramenta de organização e execução da política de
investimento declarada pelo próprio usuário. Não é consultoria de valores
mobiliários, não é análise de valores mobiliários e não é recomendação de
investimento (Res. CVM 19/2021 e 20/2021). Decisões de investimento são
suas e de sua exclusiva responsabilidade.
