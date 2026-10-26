# Referência da API local

A API é servida pelo mesmo processo HTTP da interface e não exige token. O servidor escuta em `127.0.0.1`; por padrão, a base é `http://127.0.0.1:8000`. Contratos atuais usam `api_version: 1` em `/api/config`; não há prefixo `/v1` nas rotas.

## Estado, regras e ações

### `GET /api/health`

Retorna `{"status":"ok","service":"poker-simulator"}` quando o processo responde.

### `GET /api/config`

Retorna o nome do produto, `api_version`, variante padrão, variantes suportadas, número de cartas, estrutura de apostas e limites de assentos. O seletor do cliente é alimentado por este contrato.

### `GET /api/game/state`

Antes da primeira mão, retorna `{"started":false}`. Depois, retorna o snapshot da mesa, incluindo `variant_id`, `hole_card_count`, `legal_actions`, `betting_limits`, board, assentos, pote, payouts, showdown, ações e coach.

`variant` continua sendo o rótulo legível legado; clientes novos devem usar `variant_id` (`texas_holdem` ou `pot_limit_omaha`). As cartas dos bots ficam ocultas enquanto a mão não termina.

### `POST /api/game/start`

Inicia uma mão, ou escolhe a variante para as mãos seguintes:

```json
{"variant":"pot_limit_omaha"}
```

`variant` aceita `texas_holdem` ou `pot_limit_omaha`; se omitida, a seleção mantida pelo servidor é usada. A resposta é o snapshot. O modo PLO do produto usa seis assentos, $1/$2, stacks de $200 e zero rake, sem opções de configuração para esses valores.

### `POST /api/game/action`

Avança a mão com uma ação do herói:

```json
{"action":"raise","amount":24,"variant":"pot_limit_omaha"}
```

`action` deve estar em `legal_actions`. `amount` é o total da aposta do jogador na street (raise-to), em fichas inteiras, e só é aceito para `bet` ou `raise`. `variant` é opcional; quando enviada, precisa corresponder à mão ativa. A autoridade para limites e legalidade é o backend. A resposta contém o novo snapshot; ações de bots podem ser executadas antes da resposta.

O snapshot de uma decisão inclui:

- `legal_actions` para o jogador da vez;
- `betting_limits.amount_to_call`, `minimum_raise_to`, `maximum_raise_to` e `all_in_to`;
- `coach_feedback` após a ação anterior do herói, com uma reflexão baseada no preço/range e sem usar o resultado como nota;
- `hand_complete`, `winners`, `payouts`, `showdown_ranks`, `winning_hands` e `pot_awards` após a liquidação.

## Coach e propósito de aposta

### `POST /api/coach/analyze`

Aceita `hero_hole`, `board`, `pot`, `call_amount`, `hero_stack`, `opponent_stack` e campos opcionais de posição, ranges, iterações, seed e variante. Hold'em exige duas cartas fechadas por mão; PLO exige quatro cartas para herói e cada combinação de range. No PLO, a avaliação usa duas cartas da mão e três do board.

Use `opponent_range` para uma lista de combinações concretas do oponente ou `opponent_ranges` para vários oponentes. `iterations` controla a amostra; `seed` permite reproduzir a mesma análise na mesma versão do código. A resposta inclui variante, origem e tamanho do range, iterações/seed, equity, pot odds, EV, SPR, conselho e limitações quando aplicáveis. `learning_steps` contém cinco etapas de ensino, identificadas como contexto, conceito, estimativa, sugestão e pergunta prática. Em análise de mesa, o contexto também inclui as ações legais calculadas pelo servidor. As definições de regra e conceito ficam separadas de números estimados e recomendações do coach. Após uma ação, a mesa devolve `coach_feedback`, uma reflexão que compara a decisão com as premissas registradas sem julgar o resultado da mão. Não interprete resultados heurísticos ou de Monte Carlo como certeza.

### `POST /api/coach/action-purpose`

Aceita `hero_hole`, `board`, `pot` e `bet_amount`, além de contexto opcional. Com quatro cartas fechadas detecta PLO; a classificação pré-flop pode responder `unmodeled`, pois o índice estrutural não é evidência de value ou bluff.

## Histórico e revisão

### `GET /api/session/hands`

Retorna as mãos concluídas na sessão atual em `{ "hands": [...] }`.

### `GET /api/session/hands/{hand_id}`

Retorna uma mão ou HTTP `404` quando o identificador não está na sessão.

### `POST /api/session/hands`

Registra um payload de mão concluída enviado por uma integração local. O payload requer `hero_id`, `players`, board, pote, ações e payouts; `variant` define a validação das cartas. Para PLO, o herói precisa ter quatro cartas e combinações vencedoras precisam obedecer à avaliação Omaha. O registro expõe cartas do herói, cartas reveladas, variante, ações, contribuições, payouts, winners, combinações vencedoras, pot awards e notas de decisão disponíveis.

### `GET /api/session/leaks`

Retorna alvos e indicadores de revisão. `by_variant` mantém as métricas PLO e Hold'em separadas. Indicadores são prompts de estudo.

Todos esses registros são mantidos em memória pelo processo local e desaparecem quando o servidor para.

## Erros e limites

Entradas inválidas, variante não suportada, quantidade de cartas incorreta, ação ilegal, aposta fora dos limites ou tentativa de trocar a variante durante a mão retornam HTTP `400` com `{ "error": "mensagem" }`. Um recurso de revisão inexistente retorna `404`. O limite de corpo JSON é 1 MB. A API não fornece persistência em disco, torneios, importação de históricos de salas, PLO5/PLO6 ou análise solver.
