# Cronograma semanal

Situação em **16/10/2026**. Os marcos podem ser revistos ao longo do semestre, como prevê o plano da disciplina. A demonstração final precisa ser no **P3-DX real**; o Gazebo serve para desenvolver e testar cada parte antes.

**Legenda:** ✅ feito · ⏳ pendente

## Etapa 1: até a Apresentação 2 (26/10, peso 30)

| Semana | Ian: integração e missões | Ana: simulação e navegação | Mariana: percepção, interface e estoque |
| --- | --- | --- | --- |
| 05/10 | ✅ Pacote `garcom_msgs` com as mensagens do projeto e launch subindo todos os nós (`rqt_graph`) | ⏳ P3-DX no Gazebo andando por teleoperação | ⏳ USBcam no ROS (`usb_cam`) e marcadores ArUco impressos, um por estação |
| 12/10 | ✅ Fila de pedidos por ordem de chegada e gerador de pedidos de teste | ⏳ Restaurante no Gazebo (base, estações e mesas) e mapa | ⏳ Nó de detecção ArUco publicando a estação detectada |
| 19/10 | ✅ Prazo máximo de entrega: cronômetro por pedido, alerta aos 70% do prazo, atraso e métricas | ⏳ Localização e rota A* entre dois pontos | ⏳ Interface v1 (mesa e itens) publicando pedidos na fila |
| 26/10 | ⏳ P3-DX real no ROS (RosAria, teleoperação e odometria) | ⏳ Robô indo sozinho no Gazebo entre base, estação e mesa | ⏳ Estoque com itens por estação; pedido com item em falta recusado |

**Demonstração de 26/10:**

- [ ] Navegação no Gazebo entre base, estação e mesa (Ana)
- [x] Pedido validado no estoque e entrando na fila com prazo (Ian)
- [ ] Pedido feito pela interface de verdade (Mariana)
- [ ] ArUco das estações detectado pela câmera (Mariana)
- [ ] P3-DX real se movendo por comando ROS (Ian)
- [ ] Resultados e dificuldades encontradas (todos)

## Etapa 2: até a Apresentação Final (07/12, peso 40)

A partir de 02/11, toda semana algo é testado no P3-DX real, mesmo com o projeto incompleto.

| Semana | Ian | Ana | Mariana | Marco da equipe |
| --- | --- | --- | --- | --- |
| 02/11 | Missão chamando a navegação real; um pedido completo no Gazebo; sensores e odometria do robô real conferidos | Pontos nomeados no `pontos.yaml` e ação `GoToPoint` usada pela missão | ArUco no Gazebo: marcadores nas estações e câmera simulada no P3-DX | Primeiro pedido completo no Gazebo |
| 09/11 | Vários pedidos: prioridade por prazo de cada item, ordem de coleta e capacidade da bandeja | Mapa do laboratório feito com o P3-DX real | Interface v2 com o estado e o tempo restante de cada pedido | Fila com vários pedidos; mapa real |
| 16/11 | Coleta validada por ArUco com tempo limite e nova tentativa; baixa no estoque | Navegação A* no P3-DX real | Câmera montada no P3-DX real e detecção embarcada | Coleta validada no Gazebo; navegação e câmera no robô real |
| 23/11 | Launch único e tratamento de falhas; primeiro pedido completo no robô real | Ajustes de navegação no ciclo completo | Interface e estoque integrados ao ciclo | Ciclo completo no Gazebo e primeiro ciclo no robô real |
| 30/11 | Ciclo completo no P3-DX real com vários pedidos e métricas | Ajustes finais no robô real e vídeos da demo | Testes de robustez da visão e interface final | Demo ensaiada; rascunho do relatório |
| 07/12 | Arquitetura e missões no relatório; README final | Simulação e navegação no relatório; vídeo final | Percepção, interface e estoque no relatório; slides | Demo completa, relatório de 8 a 10 páginas e apresentação |

**Demonstração de 07/12:**

- [ ] Ciclo completo: pedido → coleta validada por ArUco → entrega na mesa
- [ ] Vários pedidos com prioridade e alerta de atraso
- [ ] Demo no P3-DX real (obrigatória)
- [ ] Métricas: tempo médio de entrega e % de pedidos no prazo
- [ ] Relatório de 8 a 10 páginas, README com instruções e vídeos por marco

## Rotina semanal

- **Touchpoint de segunda (5 a 10 min):** cada um mostra o que fez, o que travou e o próximo passo, com demo ao vivo ou vídeo curto.
- **GitHub:** cada um envia a sua parte e mexe só nos próprios arquivos.
- **Feriados:** 02/11 cai numa segunda. Se não houver aula, a entrega é mostrada na aula seguinte, e o teste no robô real fica para outro dia de laboratório naquela semana.
