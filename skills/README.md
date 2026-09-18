# skills/ — o que cada skill faz, quando usar, e o que nunca faz

Qualquer agente lê as skills daqui: `/jabuti-<nome>`, ou o pedido equivalente, é ler e seguir `skills/jabuti-<nome>/SKILL.md`, como diz o `AGENTS.md` da raiz. Por isso nenhuma skill cita arquivo ou comando de um agente só. No Claude Code, o `criar_workspace.py` também as copia para `.claude/skills/`, para virarem comandos do menu (`--so-skills` reinstala; na pasta clonada, o `git pull` reinstala sozinho). Toda skill declara "O que esta skill NÃO faz". As de onboarding têm linha em `estado/SETUP.md` e terminam com um bloco "Próximo passo" pronto para colar; as de rotina terminam em "feito".

## Onboarding, na ordem (Fase 4)

| Skill | Quando | Escreve | Nunca |
|---|---|---|---|
| `/jabuti-init` | na pasta recém-clonada (o passo 0 instala ali mesmo); primeira thread; ou revisar o perfil | a instalação na raiz (via `criar_workspace.py .`), `politica/00-perfil.md` | propõe banda, olha `dados/`, pergunta onde instalar |
| `/jabuti-estrategia` | depois do perfil; ou revisar bandas | `politica/01-alocacao-alvo.md`, `logs/decisoes/` | escolhe ativo, recomenda, olha `dados/` |
| `/jabuti-importar` (modo onboarding) | depois da política, para trazer a carteira que já existe | `vault.config.yaml` (contas), `dados/` via script, `estado/ESTADO.md` | digita número, roda mapeamento sem mostrar |

## Rotina (Fase 2)

| Skill | Quando | Escreve | Nunca |
|---|---|---|---|
| `/jabuti-mes` | todo mês, com ou sem aporte; e sempre que você comprar, vender ou receber provento | `dados/` e `estado/` via script, `logs/aportes/`, `logs/vendas/`, `logs/decisoes/` | digita preço, divide o aporte de cabeça, escolhe ticker |
| `/jabuti-importar` (modo rotina) | extrato, provento ou fill novo | `dados/` via script, `logs/importacoes/` | digita número, corrige o documento para bater |

**Critério:** skill existe quando há decisão a tomar no meio do procedimento. Sequência fixa de comandos é regra do harness; comando só é um comando — por isso `registrar.py`, `consultar_aporte.py` e `atualizar_cotacoes.py` são CLIs chamados de dentro do `/jabuti-mes`, e não skills.

A rotina da Fase 5 é uma skill só. Não há skill separada de fechamento: o mês sem aporte é a mesma decisão rodada com valor zero. Este catálogo lista só o que está instalado.

## Bônus com a Finnest, opcional e só leitura

Nenhuma skill do onboarding nem da rotina depende destas. Exigem o MCP da Finnest conectado na sessão (`docs/provider-finnest.md`). Sem ele, cada uma para e declara. Nenhuma escreve em `dados/`: a carteira canônica só recebe operação conciliada contra documento. O que dá para fazer com elas, o teto de escopo e como conectar: `docs/finnest-skills.md`.

| Skill | Quando | Escreve | Nunca |
|---|---|---|---|
| `/jabuti-divida` | antes do aporte, com fatura ou empréstimo em aberto | `logs/decisoes/` | move dinheiro, sincroniza conexão, escreve em `dados/` |
| `/jabuti-capacidade` | para medir custo de vida e capacidade de aporte em vez de declarar de cabeça | `politica/00-perfil.md`, `logs/decisoes/` | decide o aporte, escolhe ativo, escreve em `dados/` |
| `/jabuti-sobra` | antes da `/jabuti-mes`, para levar o valor do aporte medido | `logs/decisoes/` | decide o aporte, grava no perfil, escreve em `dados/`, move dinheiro |
| `/jabuti-vazamentos` | a cada três meses, ou quando aparece cobrança nova | `logs/decisoes/` | cancela assinatura, julga gasto, grava no perfil, escreve em `dados/` |
