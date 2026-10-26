# Perfis heurísticos de bots PLO

## Escopo

Os bots jogam PLO high de quatro cartas e consultam o `GameState` para ações legais e limites pot-limit. Os perfis são heurísticas configuráveis de treino; não são solver, GTO, nem estimativas de estratégia ótima.

Perfis aceitos por `OpponentAI`: `tight` (`nit`), `aggressive` (`tag`), `calling_station` (`station`) e `balanced`. Nomes de exibição são Nitty Norman, Aggro Alex, Calling Kevin e Balanced Blair.

## Pré-flop

A função `plo_starting_hand_score` produz um índice estrutural de 0 a 100; não é equity. A pontuação recompensa ranks altos, pares, duas cartas do mesmo naipe com potencial de nut flush, suited ace e ranks conectados. Limiares mudam por posição e perfil; preço do call e stack/pote ajustam a continuação. A faixa não reutiliza classes de mãos de Hold'em.

## Pós-flop

Para cada oponente ativo, o bot amostra combinações de quatro cartas sem bloquear as cartas da própria mão e o board. Posição e última ação ajustam a largura da faixa. A equity usa o avaliador PLO e a regra exata de duas cartas fechadas e três comunitárias. A decisão combina equity amostrada, pot odds, posição, SPR, textura do board, nut outs e nut-flush outs identificados pelo analisador Omaha.

Os perfis alteram limiares de call, valor, blefe e agressividade. A aposta é limitada pelo `GameState.betting_bounds`; sizing em porcentagem do pote é apenas um alvo anterior ao limite. All-ins curtos só são escolhidos quando a ação consta como legal.

## Auditoria e reprodução

Cada `AIDecision` guarda ação, alvo total, explicação textual, perfil, seed e tamanho agregado de ranges quando aplicável. `OpponentAI.decide(..., seed=N)` reinicia o gerador para a decisão; a mesma versão do código, estado e seed reproduzem decisão, ranges e rollouts. `decision_history` conserva as decisões daquela instância. Os motivos indicam equity estimada, rollouts, tamanho de range, pot odds, nut outs e SPR quando disponíveis, sem tratar a estimativa como certeza.

## Validação

Os testes cobrem ordenação estrutural pré-flop, decisões com seed repetível, limites de aposta e uma mão PLO completa entre perfis distintos com guarda contra deadlock e conferência de conservação dos payouts. A validação usa iterações reduzidas para ser rápida; benchmarks de equity e precisão são tratados em `07_PLO_Equity_Accuracy_and_Performance.md`.
