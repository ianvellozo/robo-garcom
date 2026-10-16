# Robô Garçom Autônomo

Projeto do Laboratório de Robótica Móvel (ENE137, UFJF). Um robô P3-DX recebe pedidos das mesas de um restaurante, confere o estoque, vai até as estações de coleta (confirmadas por marcadores ArUco) e entrega o pedido na mesa.

**Equipe:** Ian (integração e missões), Ana (simulação e navegação), Mariana (percepção, interface e estoque).

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

```bash
roslaunch garcom_bringup sim.launch
```

Em outro terminal (com `source ~/catkin_ws/devel/setup.bash`), para ver os nós e tópicos:

```bash
rqt_graph
```

## Pacotes

| Pacote | Responsável | Função |
| --- | --- | --- |
| `garcom_msgs` | Ian (definido pela equipe) | Mensagens, serviços e ações do projeto |
| `garcom_bringup` | Ian | Arquivos launch do sistema completo |
| `garcom_mission` | Ian | Fila de pedidos, prazos e missões |
| `garcom_simulation` | Ana | Restaurante e P3-DX no Gazebo |
| `garcom_navigation` | Ana | Mapa, localização, A* e controle |
| `garcom_perception` | Mariana | USBcam e detecção ArUco |
| `garcom_interface` | Mariana | Interface de pedidos das mesas |
| `garcom_stock` | Mariana | Estoque |

## Comunicação entre os nós

| Nome | Tipo | De → Para |
| --- | --- | --- |
| `/garcom/orders` | tópico `Order` | interface → order_queue |
| `/garcom/check_stock` | serviço `CheckStock` | order_queue → stock_server |
| `/garcom/order_status` | tópico `OrderStatus` | order_queue, mission_manager → interface |
| `/garcom/next_order` | serviço `NextOrder` | mission_manager → order_queue |
| `/garcom/go_to_point` | ação `GoToPoint` | mission_manager → navigation |
| `/garcom/robot_at` | tópico `std_msgs/String` | navigation → perception |
| `/garcom/station_detected` | tópico `std_msgs/String` | perception → mission_manager |

## Situação atual (19/10)

- Estrutura do repositório no padrão catkin, com todos os pacotes criados.
- Mensagens do projeto definidas em `garcom_msgs`.
- Fila de pedidos com **prazo máximo de entrega**: cronômetro por pedido, alerta aos 70% do prazo, marcação de atraso, atendimento do pedido com menos tempo restante e métricas (tempo médio e % no prazo).
- Gerenciador de missões funcionando com nós-esqueleto: navegação, percepção e interface ainda são simuladas e serão substituídas pelos módulos reais de cada integrante.

Para ver os alertas de prazo, rode com prazo curto e pedidos mais frequentes:

```bash
roslaunch garcom_bringup sim.launch deadline_s:=30 order_period_s:=5
```
