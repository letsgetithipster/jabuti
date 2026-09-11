# GUARDRAILS — o contrato anti-alucinação da Mesa Própria

Este documento existe para ser lido ANTES do primeiro uso. Ele responde à
pergunta certa: "por que eu confiaria numa LLM para operar minha carteira?"
Resposta: você não confia na LLM. Você confia nestas quatro camadas, que
valem para qualquer skill deste repo, em qualquer LLM.

Este documento é o contrato de TODAS as fases do produto; o que já está construído hoje está listado no README, seção "Estado atual".

## Camada 1 — Mecânica (script, não modelo)

- O modelo NÃO digita preço. Todo número de mercado entra por script, com
  fonte, data e hora gravadas em `dados/cotacoes.csv` (append-only).
- Sem internet na sessão: a skill PARA e declara. Nunca preço de memória.
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
- `estado/ESTADO.md` e o painel de gatilhos têm escritor único (skill),
  nunca edição à mão.
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

## Modo mínimo viável (honestidade sobre cadência)

Obrigatórios: registrar aporte, fechar o mês, atualizar cotações.
Avançados (declarados como tais): radar de mercado, releases trimestrais,
destilados de fontes externas, watchlist ativa.
Dado velho é tratado como alerta de primeira classe: o fechamento avisa
quando algo está defasado demais para sustentar análise.

## Aviso legal

A Mesa Própria é uma ferramenta de organização e execução da política de
investimento declarada pelo próprio usuário. Não é consultoria de valores
mobiliários, não é análise de valores mobiliários e não é recomendação de
investimento (Res. CVM 19/2021 e 20/2021). Decisões de investimento são
suas e de sua exclusiva responsabilidade.
