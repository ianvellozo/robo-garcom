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

**Demonstração automática** (pedidos aleatórios e coleta confirmada sozinha):

```bash
roslaunch garcom_bringup sim.launch
```

**Alertas de prazo** (prazo de 30 s e um pedido a cada 5 s):

```bash
roslaunch garcom_bringup sim.launch deadline_s:=30 order_period_s:=5
```

**Você fazendo os pedidos e montando a bandeja** (três terminais):

```bash
roslaunch garcom_bringup sim.launch auto_orders:=false auto_pickup:=false
rosrun garcom_interface interface_node.py     # tela da mesa: escolhe mesa e itens
rosrun garcom_interface station_panel.py      # tela da estação: mostra o que pôr na bandeja; ENTER confirma
```

**Repor um item no estoque** com o sistema rodando:

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
| `garcom_interface` | Ian | Tela da mesa (pedidos) e tela da estação de coleta |
| `garcom_simulation` | Ana | Restaurante e P3-DX no Gazebo |
| `garcom_navigation` | Ana | Mapa, localização, A* e controle |

O cardápio (itens, estação de cada item e estoque inicial) fica em `garcom_stock/config/cardapio.yaml`.

## Comunicação entre os nós

| Nome | Tipo | De → Para |
| --- | --- | --- |
| `/garcom/orders` | tópico `Order` | interface → order_queue |
| `/garcom/check_stock` | serviço `CheckStock` | order_queue → stock_server (confere e reserva os itens) |
| `/garcom/restock` | serviço `Restock` | quem quiser repor → stock_server |
| `/garcom/stock` | tópico `StockLevels` | stock_server → interface |
| `/garcom/order_status` | tópico `OrderStatus` | order_queue, mission_manager → interface |
| `/garcom/next_order` | serviço `NextOrder` | mission_manager → order_queue |
| `/garcom/go_to_point` | ação `GoToPoint` | mission_manager → navigation |
| `/garcom/robot_at` | tópico `std_msgs/String` | navigation → quem quiser saber onde o robô chegou |
| `/garcom/pickup_request` | tópico `PickupRequest` | mission_manager → station_panel |
| `/garcom/pickup_done` | tópico `PickupDone` | station_panel → mission_manager |

## Situação atual (19/10)

- **Fila de pedidos com prazo máximo de entrega:** cronômetro por pedido, alerta aos 70% do prazo, marcação de atraso, atendimento do pedido com menos tempo restante e métricas (tempo médio e % no prazo).
- **Estoque:** reserva os itens quando o pedido é aceito, recusa o pedido se faltar item, avisa quando um item está acabando e aceita reposição.
- **Missões:** agrupa os itens por estação (cada estação é visitada uma vez por pedido), pede a coleta e espera a confirmação antes de seguir para a mesa.
- **Interfaces:** tela da mesa no terminal (cardápio com estoque, mesa e itens) e tela da estação (lista do que colocar na bandeja e confirmação).
- **Coleta:** a leitura de marcadores ArUco foi retirada do projeto, com o aval do professor. No lugar, a tela da estação confirma a coleta.
- **Falta:** a navegação ainda é simulada (finge a viagem). O próximo passo é o robô andando no Gazebo e depois no P3-DX real.
