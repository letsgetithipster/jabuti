# jabuti

Instruções para qualquer agente que abrir esta pasta (Codex, Cursor e outros leem este arquivo
sozinhos; o Claude Code o lê pelo `CLAUDE.md`). Aqui não há dado pessoal: o que muda é se a
raiz tem ou não um `vault.config.yaml`.

## Sem `vault.config.yaml` na raiz: o jabuti ainda não está instalado

- Pedido de uso (`/jabuti-init`, "começar", "instalar", perfil, carteira, aporte): ler e seguir
  `skills/jabuti-init/SKILL.md`. O passo 0 dela instala o jabuti aqui mesmo, e a conversa segue
  direto para o perfil. Não perguntar onde instalar: a pasta clonada é a da pessoa.
- Quem veio contribuir: `CONTRIBUTING.md` e `GUARDRAILS.md`. A suíte roda com
  `python -m pytest -q`.

## Com `vault.config.yaml` na raiz: esta pasta é uma instalação de uso

1. Ler `estado/SETUP.md` primeiro. Se o onboarding está aberto (alguma linha `- [ ]`),
   cumprimentar a pessoa com a etapa em que ela está e oferecer o próximo passo, que é a linha
   `Próximo:` desse arquivo. Não perguntar o que ela quer fazer: dizer o que falta.
2. Se o onboarding está fechado, `estado/ESTADO.md` é a primeira leitura para qualquer
   pergunta de alocação.
3. Voz e método: `rules/00-voz.md`, trocando `__CASA__`, `__USUARIO__` e `__COORDENADOR__`
   pelos nomes em `casa`, `usuario` e `coordenador` do `vault.config.yaml`. O contrato é o
   `GUARDRAILS.md`: leia antes de operar.

Regras da instalação:

- Número de mercado entra por script, nunca digitado. Sem rede, parar e declarar.
- Gerado nunca se edita à mão: `estado/ESTADO.md` sai de `scripts/gerar_estado.py`.
- Ao fim de cada skill, `python scripts/validar_workspace.py .` com zero erros.
- Nunca editar arquivo do motor: `scripts/`, `skills/`, `rules/`, `metodo/`, `templates/`,
  `docs/`, `exemplos/`, `tests/`, os mapeamentos prontos de `mapeamentos/`, este arquivo e os
  demais documentos da raiz. O motor só muda por `git pull`. O mapeamento que a pessoa pedir se
  chama `mapeamentos/meu-<corretora>.yaml`, e fica fora do git.
- Os dados da pessoa ficam fora do git do jabuti (`.gitignore`), e commit e push ficam
  bloqueados nesta pasta. Mudança no jabuti vira issue ou pull request, que o mantenedor aprova:
  https://github.com/letsgetithipster/jabuti/issues

## Skills, para qualquer agente

`/jabuti-<nome>`, ou o pedido equivalente em palavras, é ler e seguir
`skills/jabuti-<nome>/SKILL.md`. Nas skills, `<motor>` é esta pasta (`.`) quando a instalação
está na raiz; numa pasta separada, é o caminho em `caminhos.motor` do `vault.config.yaml`.
O catálogo, com a ordem de uso, está em `skills/README.md`.

Os comandos no menu do agente existem hoje só no Claude Code, configurados pelo passo 0 do
`/jabuti-init`. Nos outros agentes, as skills funcionam por este arquivo: a pessoa cola o nome, e
o agente lê a skill.
