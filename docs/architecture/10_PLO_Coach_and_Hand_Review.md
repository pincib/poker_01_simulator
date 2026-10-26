# Coach, histórico e revisão para PLO4

## Coach ao vivo

O coach seleciona o variant pelo `GameRules` e valida quantidade de cartas. Hold'em mantém ranges de duas cartas e categorias atuais. PLO4 avalia exatamente duas cartas fechadas e três comunitárias; Heads-up parte de combinações uniformes de quatro cartas, enquanto multiway usa amostras determinísticas por seed, ajustadas de forma heurística por posição e ação pré-flop. A fonte, tamanho da amostra, iterações e seed ficam no snapshot.

Cada decisão tem uma aula navegável em cinco passos: situação e ações legais; regra/conceito pertinente; significado dos números e comparação equity/preço; sugestão de processo; pergunta prática para a próxima mão. Fatos das regras, métricas estimadas e sugestões aparecem com rótulos próprios. Pot odds explicam a equity de break-even para o call atual; equity descreve share esperado e empates; EV é resultado médio no modelo; SPR compara stack efetivo ao pote. Sem preço de call, o coach explica por que pot odds/EV de call não se aplicam.

Para PLO, o conselho cita nut potential e redraws; pares de Hold'em não são tratados como regra de compromisso. A análise de draws marca outs nut/não-nut e limitações. A estimativa não modela decisões futuras do oponente, pode ter variância Monte Carlo e simplifica SPR/potes laterais em multiway.

Depois da ação do jogador, uma reflexão processual compara o call/fold com preço e equity modelados, ou convida a revisar o propósito de check/bet/raise. A reflexão não usa vitória ou derrota como nota e acompanha a revisão da mão. A aula completa também fica recolhível no histórico para consulta posterior.

A classificação de propósito de aposta pré-flop em PLO4 retorna `unmodeled`: o índice estrutural de starting hand não é equity nem evidência de value/bluff. No pós-flop, comparação de mãos usa o avaliador Omaha e ranges de quatro cartas.

## Histórico reconstituível

O histórico atual é da sessão em memória do processo local. Mãos concluídas guardam variant, cartas do herói, board, jogadores e cartas reveladas no showdown, stacks inicial/final, contribuições, ações com street/chips/bet-to/variant, payouts, vencedores, rankings, combinações vencedoras e prêmios de pote principal/laterais. Cartas de jogadores que desistiram permanecem ocultas; não são necessárias para reconstruir a sequência de apostas e a liquidação.

Decision notes guardam variante, ação, pot odds, equity estimada, EV, fonte/tamanho de range, iterações, seed, draw analysis, racional e limitações. Importações incompletas podem omitir métricas; a revisão apresenta somente os dados recebidos.

## Leaks por variante

O relatório agrupa indicadores em `by_variant`. A primeira métrica PLO é a frequência de calls abaixo da equity estimada no preço, exibida separada do indicador Hold'em. Hold'em mantém os prompts de folds a continuation bets e pots fora de posição. Indicadores são prompts de estudo, não prova de erro. Outs, blockers e redraws são evidências por mão; ainda não são convertidos em uma nota independente de leak.
