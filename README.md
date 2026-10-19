# Robô Garçom Autônomo

Projeto do Laboratório de Robótica Móvel (ENE137, UFJF). Um robô P3-DX recebe pedidos das mesas de um restaurante, reserva os itens no estoque, vai até as estações de coleta, espera a confirmação de que a bandeja foi montada e entrega o pedido na mesa.

**Equipe:** Ian (pedidos, estoque, missões e interfaces) e Ana (simulação e navegação).

## Documentação

- [Guia da equipe](docs/GUIA_DA_EQUIPE.md): instalação, como rodar, o que cada integrante faz e como enviar código.
- [Cronograma semanal](docs/CRONOGRAMA.md): entregas de cada integrante até 07/12.

## Requisitos

- Ubuntu 20.04
- ROS Noetic (`ros-noetic-desktop-full`)

## Como compilar

O repositório fica dentro da pasta `src` de um workspace catkin:

```bash
mkdir -p ~/catkin_ws/src
cd ~/catkin_ws/src
git clone https://github.com/ianvellozo/robo-garcom.git robo-garcom
cd ~/catkin_ws
catkin_make
source devel/setup.bash
```

Se um nó não abrir, confira se os scripts estão executáveis:

```bash
chmod +x ~/catkin_ws/src/robo-garcom/*/scripts/*.py
```

## Como rodar

**Com as telas no navegador** (você faz os pedidos e monta a bandeja):

```bash
roslaunch garcom_bringup sim.launch auto_orders:=false auto_pickup:=false
```

Depois abra no navegador do mesmo computador:

| Tela | Endereço | Para quem |
| --- | --- | --- |
| Mesa | http://localhost:8080/mesa?mesa=2 | Cliente: escolhe os itens, faz o pedido e acompanha o robô |
| Bancada | http://localhost:8080/bancada | Funcionário: vê o que pôr na bandeja, confirma e ajusta o estoque |

A bancada pode mostrar só uma estação: http://localhost:8080/bancada?estacao=estacao_cafe

**Demonstração automática** (pedidos aleatórios e coleta confirmada sozinha):

```bash
roslaunch garcom_bringup sim.launch
```

**Alertas de prazo** (prazo de 30 s e um pedido a cada 5 s):

```bash
roslaunch garcom_bringup sim.launch deadline_s:=30 order_period_s:=5
```

**Telas no terminal**, sem navegador:

```bash
rosrun garcom_interface interface_node.py     # tela da mesa
rosrun garcom_interface station_panel.py      # tela da estação; ENTER confirma
```

**Repor um item no estoque** pelo terminal:

```bash
rosservice call /garcom/restock "{item: 'rosquinha', quantity: 5}"
```

Para ver os nós e tópicos, rode `rqt_graph` em outro terminal.

## Pacotes

| Pacote | Responsável | Função |
| --- | --- | --- |
| `garcom_msgs` | Ian | Mensagens, serviços e ações do projeto |
| `garcom_bringup` | Ian | Arquivo launch do sistema completo |
| `garcom_mission` | Ian | Fila de pedidos, prazos e missões |
| `garcom_stock` | Ian | Cardápio e estoque |
| `garcom_interface` | Ian | Telas no navegador (mesa e bancada) e versões no terminal |
| `garcom_simulation` | Ana | Restaurante e P3-DX no Gazebo |
| `garcom_navigation` | Ana | Mapa, localização, A* e controle |

O cardápio (itens, estação de cada item e estoque inicial) fica em `garcom_stock/config/cardapio.yaml`.

## Comunicação entre os nós

| Nome | Tipo | De → Para |
| --- | --- | --- |
| `/garcom/orders` | tópico `Order` | tela da mesa → order_queue |
| `/garcom/check_stock` | serviço `CheckStock` | order_queue → stock_server (confere e reserva os itens) |
| `/garcom/restock` | serviço `Restock` | quem quiser repor → stock_server |
| `/garcom/set_stock` | serviço `SetStock` | web_server (botão Estoque) → stock_server |
| `/garcom/stock` | tópico `StockLevels` | stock_server → telas |
| `/garcom/order_status` | tópico `OrderStatus` | order_queue, mission_manager → telas |
| `/garcom/next_order` | serviço `NextOrder` | mission_manager → order_queue |
| `/garcom/go_to_point` | ação `GoToPoint` | mission_manager → navigation |
| `/garcom/robot_at` | tópico `std_msgs/String` | navigation → quem quiser saber onde o robô chegou |
| `/garcom/pickup_request` | tópico `PickupRequest` | mission_manager → tela da bancada |
| `/garcom/pickup_done` | tópico `PickupDone` | tela da bancada → mission_manager |

## Situação atual (19/10)

- **Fila de pedidos com prazo máximo de entrega:** cronômetro por pedido, alerta aos 70% do prazo, marcação de atraso, atendimento do pedido com menos tempo restante e métricas (tempo médio e % no prazo).
- **Estoque:** reserva os itens quando o pedido é aceito, recusa o pedido se faltar item, avisa quando um item está acabando e aceita reposição.
- **Missões:** agrupa os itens por estação (cada estação é visitada uma vez por pedido), pede a coleta e espera a confirmação antes de seguir para a mesa.
- **Telas no navegador:** a da mesa (cardápio com estoque, carrinho e o trajeto do robô até a mesa) e a da bancada (comanda com o que pôr na bandeja, botão Bandeja pronta, pedidos do salão com alertas e botão Estoque para ajustar as quantidades). Também há versões no terminal.
- **Coleta:** a leitura de marcadores ArUco foi retirada do projeto, com o aval do professor. No lugar, a tela da estação confirma a coleta.
- **Falta:** a navegação ainda é simulada (finge a viagem). O próximo passo é o robô andando no Gazebo e depois no P3-DX real.
