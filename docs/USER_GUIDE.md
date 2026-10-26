# Guia do usuário

O Poker Mastery Simulator roda no seu computador e oferece mesas de treino locais de Texas Hold'em e PLO4 high contra bots. Não há dinheiro real nem conexão com uma sala de poker.

## Iniciar

Requer Python 3.10 ou mais recente. Abra um terminal na pasta do projeto e execute:

```powershell
python run_simulator.py
```

O navegador abre a interface local. Se preferir abrir a página manualmente, ou se não quiser que o navegador seja aberto automaticamente:

```powershell
python run_simulator.py --no-browser
```

Depois, acesse `http://127.0.0.1:8000`. Para escolher outra porta, use `--port 8001` e abra `http://127.0.0.1:8001`. Encerre o servidor com `Ctrl+C` no terminal.

## Jogar PLO

1. No campo **Game**, escolha **Pot-Limit Omaha** antes de distribuir.
2. Leia o resumo de limites exibido abaixo do seletor e pressione **Deal hand**.
3. Confira as quatro cartas fechadas. Use apenas as ações legais habilitadas; o backend valida todas as apostas e informa os limites pot-limit.
4. Em **Session review**, abra uma mão concluída para ver cartas, ações, contribuições, payouts, combinação vencedora e notas do coach.

A modalidade só pode mudar entre mãos. O seletor fica bloqueado enquanto uma mão está em andamento. Após perder todo o stack, o assento recebe novamente $200 ao distribuir a próxima mão.

## Limites fixos do modo PLO

- PLO high com quatro cartas fechadas e seis assentos: você e cinco bots.
- Blinds $1/$2 e stacks de $200 por assento; sem antes, straddles, rake ou taxas.
- O showdown usa exatamente duas cartas fechadas e três cartas do board. Não é permitido jogar o board sem usar duas cartas da mão.
- Os bots usam perfis heurísticos para gerar situações de treino. Eles não são solver nem representam estratégia GTO.
- Equity, ranges, EV e draws do coach são estimativas. Amostras multiway, ação futura dos adversários e pot odds/SPR com vários stacks podem ser simplificados. Consulte as notas e limitações junto a cada decisão.
- Histórico e revisão ficam na memória do servidor local. Parar ou reiniciar o servidor apaga as mãos da sessão.

PLO5/PLO6, Hi-Lo, torneios, dinheiro real, seleção de stakes e análise baseada em solver não fazem parte deste MVP.

## Aprender com o coach e a revisão

O coach mostra pot odds, equity estimada, EV de call, SPR e evidências Omaha disponíveis, como nut outs, draws e redraws. Uma estimativa descreve a amostra e as premissas informadas; não garante o resultado da mão. A classificação pré-flop de value/bluff em PLO permanece não modelada.

Ao terminar uma mão, a revisão é atualizada automaticamente. Também é possível selecionar **Refresh review**. Indicadores semanais agrupam Hold'em e PLO separadamente e são sugestões de estudo, não prova de erro. A revisão mantém as cartas de jogadores que desistiram ocultas.

## Solução de problemas

- **Server unavailable:** confirme que o processo Python continua ativo e que a página usa a mesma porta indicada no terminal; atualize a página depois.
- **Ação recusada:** verifique se ainda é sua vez e se o valor total de aposta está entre os limites mostrados.
- **Seletor desabilitado:** finalize a mão atual antes de trocar de modalidade.
- **Revisão vazia após reinício:** o histórico é temporário e local ao processo; mãos anteriores não são persistidas em disco.

Para payloads e rotas HTTP, consulte a [referência da API](API.md). Para escopo e expansão futura, consulte o [plano de liberação do MVP PLO](architecture/12_PLO_MVP_Release_and_Roadmap.md).
