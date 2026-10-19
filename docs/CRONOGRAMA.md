# Cronograma semanal

Situação em **19/10/2026**. Os marcos podem ser revistos ao longo do semestre, como prevê o plano da disciplina. A demonstração final precisa ser no **P3-DX real**; o Gazebo serve para desenvolver e testar cada parte antes.

**Mudança em 19/10:** a Mariana saiu da disciplina. O estoque e a interface passaram para o Ian, e a leitura de ArUco foi retirada do projeto com o aval do professor. No lugar dela entrou a **tela da estação**, que mostra o que colocar na bandeja e confirma a coleta.

**Legenda:** ✅ feito · ⏳ pendente

## Etapa 1: até a Apresentação 2 (26/10, peso 30)

| Semana | Ian: pedidos, estoque, missões e interfaces | Ana: simulação e navegação |
| --- | --- | --- |
| 05/10 | ✅ Pacote `garcom_msgs` com as mensagens do projeto e launch subindo todos os nós (`rqt_graph`) | ⏳ P3-DX no Gazebo andando por teleoperação |
| 12/10 | ✅ Fila de pedidos por ordem de chegada e gerador de pedidos de teste | ⏳ Restaurante no Gazebo (base, estações e mesas) e mapa |
| 19/10 | ✅ Prazo máximo de entrega: cronômetro por pedido, alerta aos 70% do prazo, atraso e métricas<br>✅ Estoque: reserva dos itens, recusa por falta, aviso de estoque baixo e reposição<br>✅ Tela da mesa e tela da estação no terminal (no lugar do ArUco) | ⏳ Localização e rota entre dois pontos |
| 26/10 | ⏳ Ajudar a montar o mundo do restaurante no Gazebo<br>⏳ P3-DX real no ROS (RosAria, teleoperação e odometria) | ⏳ Robô indo sozinho no Gazebo entre base, estação e mesa |

**Demonstração de 26/10:**

- [ ] Navegação no Gazebo entre base, estação e mesa (Ana, com o mundo montado junto com o Ian)
- [x] Pedido feito na tela da mesa, com os itens reservados no estoque e prazo controlado (Ian)
- [x] Coleta confirmada na tela da estação (Ian)
- [ ] P3-DX real se movendo por comando ROS (Ian)
- [ ] Resultados e dificuldades encontradas (todos)

## Etapa 2: até a Apresentação Final (07/12, peso 40)

A partir de 02/11, toda semana algo é testado no P3-DX real, mesmo com o projeto incompleto.

| Semana | Ian | Ana | Marco da equipe |
| --- | --- | --- | --- |
| 02/11 | Missão usando a navegação real do Gazebo; sensores e odometria do P3-DX real conferidos | Pontos nomeados no `pontos.yaml` e ação `GoToPoint` movendo o robô de verdade | Primeiro pedido completo no Gazebo |
| 09/11 | Vários pedidos por viagem (capacidade da bandeja) e prazo por item | Mapa do laboratório feito com o P3-DX real | Fila com vários pedidos; mapa real |
| 16/11 | Tela da mesa e tela da estação na web (celular ou tablet) | Navegação A* no P3-DX real | Navegação no robô real; telas web |
| 23/11 | Launch do robô real e tratamento de falhas; primeiro pedido completo no laboratório | Ajustes de navegação no ciclo completo | Ciclo completo no Gazebo e primeiro ciclo no robô real |
| 30/11 | Ciclo completo no P3-DX real com vários pedidos e métricas | Ajustes finais no robô real e vídeos da demo | Demo ensaiada; rascunho do relatório |
| 07/12 | Pedidos, estoque, missões e telas no relatório; README final; slides | Simulação e navegação no relatório; vídeo final | Demo completa, relatório de 8 a 10 páginas e apresentação |

**Demonstração de 07/12:**

- [ ] Ciclo completo: pedido na tela da mesa → coleta confirmada na estação → entrega na mesa
- [ ] Vários pedidos com prioridade e alerta de atraso
- [ ] Demo no P3-DX real (obrigatória)
- [ ] Métricas: tempo médio de entrega e % de pedidos no prazo
- [ ] Relatório de 8 a 10 páginas, README com instruções e vídeos por marco

## Rotina semanal

- **Touchpoint de segunda (5 a 10 min):** cada um mostra o que fez, o que travou e o próximo passo, com demo ao vivo ou vídeo curto.
- **GitHub:** cada um envia a sua parte e mexe só nos próprios arquivos.
- **Feriados:** 02/11 cai numa segunda. Se não houver aula, a entrega é mostrada na aula seguinte, e o teste no robô real fica para outro dia de laboratório naquela semana.
