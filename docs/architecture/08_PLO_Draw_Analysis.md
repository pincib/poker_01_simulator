# Análise de draws PLO: definições e limites

O detector trabalha com PLO high de quatro cartas e usa a avaliação Omaha existente em todas as classificações: exatamente duas cartas fechadas e três cartas comunitárias. Considera flop, turn e river; no river não há outs futuros.

## Saídas

- **Straight outs / wrap:** cartas distintas ainda disponíveis que criam uma sequência legal. Um wrap segue o material de estudo: mais de oito outs distintos. Cada carta é contada uma vez, mesmo quando várias combinações de duas cartas da mão a utilizam.
- **Flush outs:** carta da próxima street que deixa pelo menos três cartas de um naipe no board e duas desse naipe nas quatro cartas do jogador. Uma carta de naipe só na mão nunca basta. A categoria é detectada pela combinação legal, mesmo quando uma mão melhor (por exemplo, full house) vence o flush.
- **Improvement outs / redraws próprios:** cartas que melhoram o ranking Omaha atual. São separadas de straight/flush outs porque melhorar o ranking não garante ganhar.
- **Nut outs:** entre outs de straight, flush ou melhoria, cartas em que a mão do jogador iguala ou supera a melhor mão Omaha que qualquer par de cartas adversário ainda disponível poderia formar no board resultante. É “nuts agora nesse board”, não garantia contra todas as cartas futuras.
- **Nut flush outs / non-nut outs:** subconjuntos dos draws correspondentes; aceitam empates no topo. Board pareado, duplicação de ranks, straight flushes e redraws são avaliados pelo ranking legal, não por regra de atalho.
- **Clean / dirty / unverified:** com quatro cartas de um adversário expostas, uma straight/flush out é limpa apenas se o herói terminar à frente em todos os rivers restantes; empate ou ultrapassagem em qualquer river torna-a dirty. Sem mão exposta, outs ficam unverified e o coach não afirma que são limpas.
- **Blockers:** cartas do adversário conhecidas que seriam straight/flush outs sem a carta bloqueadora são listadas. As quatro cartas próprias e o número de combinações de quatro cartas removidas por elas também são explicitados. Esse total é combinatório e não aplica peso de range.
- **Opponent redraws:** após uma carta de melhoria do herói no turn, enumera rivers que permitem ao adversário exposto empatar ou ultrapassar quando o herói estava à frente no turn. O resultado descreve apenas a mão exposta.

## Evidência no coach

O snapshot inclui `draw_analysis` com cartas em códigos, textura atual (board pareado, padrão de naipes, conexão e wetness), listas de outs, blockers, redraws e frases que explicam contagens e qualificam incerteza. A análise não transforma contagem de outs em equity nem substitui o cálculo Monte Carlo.
