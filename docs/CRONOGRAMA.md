# Cronograma semanal

Situação em **21/10/2026**. Os marcos podem ser revistos ao longo do semestre, como prevê o plano da disciplina. A demonstração final precisa ser no **P3-DX real**; o Gazebo serve para desenvolver e testar cada parte antes.

**Mudanças:**

- **19/10:** a Mariana saiu da disciplina. O estoque e a interface passaram para o Ian, e a leitura de ArUco foi retirada do projeto com o aval do professor. No lugar dela entrou a **tela da estação**, que mostra o que colocar na bandeja e confirma a coleta.
- **21/10:** para a Apresentação 2, o **Ian assumiu a simulação e a navegação** (Gazebo, mapa e rota), para aliviar a Ana. Entrou também a **parada e o desvio de obstáculos** pelo laser, pedido pelo professor para o robô não "derrubar tudo". Na Etapa 2, a Ana leva a navegação para o P3-DX real.

**Legenda:** ✅ feito · ⏳ pendente

## Etapa 1: até a Apresentação 2 (26/10, peso 30)

| Semana | Pedidos, estoque, missões e interfaces (Ian) | Simulação e navegação (Ana; na parcial, Ian) |
| --- | --- | --- |
| 05/10 | ✅ Pacote `garcom_msgs` com as mensagens do projeto e launch subindo todos os nós (`rqt_graph`) | ✅ Modelo do P3-DX para o Gazebo, com tração diferencial e laser (plugins da aula 7) |
| 12/10 | ✅ Fila de pedidos por ordem de chegada e gerador de pedidos de teste | ✅ Restaurante para o Gazebo (base, bancadas, 15 mesas com cadeiras) e mapa, gerados do `pontos.yaml` |
| 19/10 | ✅ Prazo máximo de entrega: cronômetro por pedido, alerta aos 70% do prazo, atraso e métricas<br>✅ Estoque: reserva dos itens, recusa por falta, aviso de estoque baixo e reposição<br>✅ Telas no navegador: a da mesa (cliente) e a da bancada (funcionário, com ajuste de estoque), no lugar do ArUco | ✅ Rota com A\* no mapa, com margem de segurança em volta dos móveis<br>✅ Controle seguindo a rota com a odometria, com aceleração suave por causa da bandeja |
| 26/10 | ✅ Vários pedidos por viagem e ordem das paradas otimizada (adiantado da semana 09/11)<br>✅ Escolha da mesa na planta do salão, com 15 mesas<br>⏳ P3-DX real no ROS (RosAria, teleoperação e odometria) | ✅ Parada e desvio de obstáculos pelo laser, com aviso nas telas<br>✅ Simulador 2D leve para testar sem Gazebo<br>⏳ Conferir tudo no Gazebo do computador da equipe |

**Demonstração de 26/10:**

- [x] Pedido feito na tela da mesa (navegador), com os itens reservados no estoque e prazo controlado
- [x] Viagem com pedidos de várias mesas, coleta confirmada na tela da bancada e entrega mesa por mesa
- [x] Rota A\* no mapa e robô indo sozinho entre base, bancada e mesa (testado no simulador 2D)
- [ ] O mesmo no Gazebo, com o RViz mostrando o mapa, o laser e a rota
- [x] Cliente entrando na frente do robô: ele para, desvia ou espera, e as telas avisam (testado no simulador 2D)
- [ ] P3-DX real se movendo por comando ROS
- [ ] Resultados e dificuldades encontradas

## Etapa 2: até a Apresentação Final (07/12, peso 40)

A partir de 02/11, toda semana algo é testado no P3-DX real, mesmo com o projeto incompleto.

| Semana | Ian | Ana | Marco da equipe |
| --- | --- | --- | --- |
| 02/11 | P3-DX real no ROS: RosAria, laser SICK e teleoperação; launch do robô real com os tópicos `/RosAria/cmd_vel` e `/RosAria/pose` | Mapa do laboratório com o `gmapping` (andando com o joystick) | Robô real andando por comando ROS; mapa do laboratório |
| 09/11 | Parada por obstáculo no P3-DX real, com o laser de verdade | Localização no mapa do laboratório (AMCL) e pontos do laboratório no `pontos.yaml` | Robô real indo a um ponto e parando diante de uma pessoa |
| 16/11 | Telas abertas no celular ou tablet pela rede do laboratório | Ajustes da navegação no robô real (velocidade, margens, desvio) | Primeiro pedido completo no laboratório |
| 23/11 | Tratamento de falhas (rota impossível, robô travado, bancada sem resposta) | Ajustes de navegação com vários pedidos | Ciclo completo no robô real com vários pedidos |
| 30/11 | Métricas no robô real (tempo médio, % no prazo) | Vídeos da demo e ajustes finais | Demo ensaiada; rascunho do relatório |
| 07/12 | Pedidos, estoque, missões e telas no relatório; README final; slides | Navegação no robô real no relatório; vídeo final | Demo completa, relatório de 8 a 10 páginas e apresentação |

**Demonstração de 07/12:**

- [ ] Ciclo completo: pedido na tela da mesa → coleta confirmada na estação → entrega na mesa
- [ ] Vários pedidos por viagem, com prioridade e alerta de atraso
- [ ] Demo no P3-DX real (obrigatória), parando diante de obstáculos
- [ ] Métricas: tempo médio de entrega e % de pedidos no prazo
- [ ] Relatório de 8 a 10 páginas, README com instruções e vídeos por marco

## Rotina semanal

- **Touchpoint de segunda (5 a 10 min):** cada um mostra o que fez, o que travou e o próximo passo, com demo ao vivo ou vídeo curto.
- **GitHub:** cada um envia a sua parte e mexe só nos próprios arquivos.
- **Feriados:** 02/11 cai numa segunda. Se não houver aula, a entrega é mostrada na aula seguinte, e o teste no robô real fica para outro dia de laboratório naquela semana.
