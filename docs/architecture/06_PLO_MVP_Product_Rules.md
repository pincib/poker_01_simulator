# Regras do MVP de PLO

**Estado:** decisão de produto para a primeira versão jogável local.  
**Escopo:** treino de PLO high contra bots; sem dinheiro real.

## Mesa e configuração

- Modalidade fixa: Pot-Limit Omaha high (PLO4). Cada jogador recebe exatamente quatro cartas fechadas. A mão final usa exatamente duas cartas fechadas e exatamente três das cinco cartas comunitárias.
- Mesa fixa de seis lugares no MVP, com o herói e cinco bots; pelo menos dois jogadores com fichas iniciam cada mão. O motor deve aceitar 2–6 jogadores para testes e evolução, mas a UI de treino inicia em seis.
- Blinds fixos em $1/$2 e stack inicial/recompra de $200 (100 big blinds). São fichas fictícias inteiras; não há seleção de limite, número de lugares, stack ou blind na interface inicial.
- Sem ante, straddle, rake, taxa ou jackpots. O pote disputável equivale às contribuições; não há dedução antes do payout.
- Buy-in e recompra são configuração operacional da mesa de treino, não transferência de dinheiro. Ao perder todas as fichas, o assento recebe $200 antes da próxima mão.

## Distribuição e posições

- Baralho padrão de 52 cartas, sem coringas. Embaralhar uma vez por mão; distribuir uma carta por vez em sentido horário a partir do primeiro assento à esquerda do botão, repetindo quatro voltas.
- Heads-up: botão é small blind e age primeiro pré-flop; pós-flop age primeiro o big blind. Com 3–6 jogadores, small blind e big blind são os dois assentos seguintes ao botão; pré-flop começa à esquerda do big blind e pós-flop à esquerda do botão.
- Queimar uma carta antes do flop, turn e river. O flop tem três cartas; turn e river uma cada. Cartas queimadas não são reveladas.

## Apostas e all-in

- Apostas sem limite de tempo, em unidades inteiras de ficha. O small blind é $1 e big blind $2; blinds podem ser postados parcialmente quando o stack é menor.
- Estrutura pot-limit em todas as streets. O máximo raise-to inclui o call: primeiro considerar o call necessário para igualar a aposta atual; depois o tamanho do pote após esse call é o máximo que pode ser aumentado. O total colocado pelo jogador inclui sua contribuição já feita na street. Sem aposta, a primeira aposta máxima é o pote atual.
- A aposta mínima é $2 quando ninguém apostou na street. Raise mínimo é o tamanho da última aposta/raise completo. Apostas/raises abaixo do mínimo são aceitos somente se forem all-in por stack insuficiente.
- Call compromete até o valor devido ou todo o stack restante. All-in pode ser curto e não reabre o direito de raise de quem já agiu, salvo se o incremento cumulativo alcançar um raise completo conforme a regra de reabertura definida no motor.
- Não há side pot sem pelo menos dois jogadores contribuindo para a camada. Contribuição não igualada é devolvida; contribuições igualadas formam pote principal e potes laterais em camadas. Jogador que desistiu contribui, mas não pode ganhar. Cada pote é disputado apenas entre seus elegíveis.
- Quando ninguém mais pode apostar, completar automaticamente as streets restantes até cinco cartas comunitárias e ir ao showdown; não se criam apostas fictícias nas streets puladas.

## Showdown e pagamento

- Se todos menos um desistirem, o sobrevivente recebe todas as contribuições, sem mostrar cartas obrigatoriamente. Se houver dois ou mais jogadores ativos no showdown, todos os ativos elegíveis revelam as quatro cartas.
- Avaliar cada mão ativa por exatamente duas cartas da mão e três do board; ranking padrão high de poker, sem low. Board-only ou uso de uma, três ou quatro cartas fechadas nunca é permitido.
- Resolver cada pote principal/lateral separadamente. Melhor ranking divide o pote entre empatados elegíveis; fichas indivisíveis são distribuídas uma por vez no sentido horário a partir do primeiro assento à esquerda do botão. Devoluções de aposta não igualada não são ganhos de showdown.
- Fichas são conservadas: stacks finais somados equivalem aos stacks iniciais da mão; payout soma exatamente as contribuições sujeitas a pote/devolução. Sem rake, o total de payout é igual ao total contribuído.

## Coach

Prioridade de vocabulário e explicações: **nuts/nut hands** (melhor mão possível agora), **redraws** (melhora ou proteção futura de uma mão feita), **wraps** (draw de sequência com mais de oito outs de sequência, contando cartas distintas), **blockers** (cartas próprias que removem combinações do range), **equity** (fração esperada do pote, considerando empates) e **SPR** (stack efetivo restante dividido pelo pote atual). O coach deve distinguir mão feita de potencial/redraw, outs que completam a mão de outs limpos, e estimativas de certezas. Em multiway, não reduzir SPR a uma única relação de heads-up quando houver stacks efetivos diferentes.

## Fora das opções do MVP

PLO5/PLO6, Hi-Lo, straddles, antes, rake, seleção de stakes/stacks/tamanho de mesa, torneios, dinheiro real e estratégia solver/GTO. A ausência de rake é explícita para que pot odds e payouts do simulador sejam interpretáveis, e não uma afirmação sobre salas comerciais.
