# skills/ — o que cada skill faz, quando usar, e o que nunca faz

O `criar_workspace.py` copia estas pastas para `.claude/skills/` do workspace (`--so-skills` reinstala). Toda skill declara "O que esta skill NÃO faz". As de onboarding têm linha em `estado/SETUP.md` e terminam com um bloco "Próximo passo" pronto para colar; as de rotina terminam em "feito".

## Onboarding, na ordem (Fase 4)

| Skill | Quando | Escreve | Nunca |
|---|---|---|---|
| `/jabuti-init` | primeira thread; ou revisar o perfil | `politica/00-perfil.md` | propõe banda, olha `dados/`, cria workspace |
| `/jabuti-estrategia` | depois do perfil; ou revisar bandas | `politica/01-alocacao-alvo.md`, `logs/decisoes/` | escolhe ativo, recomenda, olha `dados/` |
| `/jabuti-importar` (modo onboarding) | depois da política, para trazer a carteira que já existe | `vault.config.yaml` (contas), `dados/` via script, `estado/ESTADO.md` | digita número, roda mapeamento sem mostrar |
| `/jabuti-micro <bloco>` | um por bloco com alvo | `teses/<bloco>/` (semente) | **Fase 4b, ainda não instalada** |
| `/jabuti-tese <ticker>` | um por ativo escolhido | tese validada com nota | **Fase 4b, ainda não instalada** |

## Rotina (Fase 2)

| Skill | Quando | Escreve | Nunca |
|---|---|---|---|
| `/jabuti-mes` | todo mês, com ou sem aporte; e sempre que você comprar, vender ou receber provento | `dados/` e `estado/` via script, `logs/aportes/`, `logs/vendas/`, `logs/decisoes/` | digita preço, divide o aporte de cabeça, escolhe ticker |
| `/jabuti-importar` (modo rotina) | extrato, provento ou fill novo | `dados/` via script, `logs/importacoes/` | digita número, corrige o documento para bater |

**Critério:** skill existe quando há decisão a tomar no meio do procedimento. Sequência fixa de comandos é regra do harness; comando só é um comando — por isso `registrar.py`, `consultar_aporte.py` e `atualizar_cotacoes.py` são CLIs chamados de dentro do `/jabuti-mes`, e não skills.

A rotina da Fase 5 é uma skill só. Não há skill separada de fechamento: o mês sem aporte é a mesma decisão rodada com valor zero. `/preparar-ir` é da Fase 6 e ainda não está instalada.
