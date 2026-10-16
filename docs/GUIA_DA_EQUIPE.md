# Guia da equipe: como começar e o que cada uma faz

Este guia é para quem nunca mexeu com ROS, Linux ou Git. Siga na ordem.

**Resumo:** o sistema inteiro já roda. Cada parte do robô é um programa separado (um "nó"), e as partes da Ana e da Mariana já existem como **esqueletos** que só fingem funcionar. O trabalho de cada uma é **trocar o "fingir" pelo de verdade**, sem mudar os nomes dos canais de comunicação.

---

## 1. ROS em 2 minutos (com o exemplo do restaurante)

| No ROS | No restaurante | No nosso projeto |
| --- | --- | --- |
| **Nó** (um programa pequeno) | Um funcionário | `interface`, `order_queue`, `navigation`... |
| **Mensagem** (formato combinado) | A comanda | `Order`: número, mesa, itens e hora do pedido |
| **Tópico** (canal com nome) | O trilho onde se pendura a comanda | `/garcom/orders`: a mesa "pendura" o pedido ali |
| **Serviço** (pergunta e resposta) | "Tem croissant?" → "Tem" | `/garcom/check_stock`: a fila pergunta ao estoque |
| **Ação** (tarefa demorada) | "Leva isso na mesa 2" | `/garcom/go_to_point`: "vá até a mesa_2" |
| **roscore** | A central que apresenta todo mundo | Precisa estar ligado antes de tudo |

## 2. Como um pedido anda pelo sistema

1. A **interface** (Mariana) publica o pedido em `/garcom/orders`.
2. A **fila** (Ian) pergunta ao **estoque** (Mariana) se tem os itens. Se faltar algum, recusa o pedido.
3. A fila controla o **prazo máximo de entrega**: avisa quando o pedido passa de 70% do prazo e marca como atrasado se passar do prazo.
4. O **gerente de missões** (Ian) pega o pedido mais urgente e manda a **navegação** (Ana) ir até a estação de cada item.
5. Ao chegar, a **percepção** (Mariana) lê o marcador ArUco da estação e confirma em `/garcom/station_detected`.
6. O gerente manda a navegação ir até a mesa e depois voltar para a base. Cada mudança de estado do pedido sai em `/garcom/order_status`.

| Nó | Responsável | Hoje |
| --- | --- | --- |
| `order_queue` (fila e prazos) | Ian | **Real** |
| `mission_manager` (missões) | Ian | **Real** |
| `navigation` | Ana | Esqueleto: finge a viagem em 3 s |
| `perception` | Mariana | Esqueleto: finge que leu o ArUco |
| `interface` | Mariana | Esqueleto: gera pedidos aleatórios |
| `stock_server` | Mariana | Funciona com o `estoque.yaml`; falta dar baixa a cada entrega |

---

## 3. Instalar (só na primeira vez)

Precisa de **Ubuntu 20.04 com ROS Noetic**. Se você já tem, pule para o passo 4.

**No Windows (WSL):** abra o PowerShell como administrador e rode:

```
wsl --install -d Ubuntu-20.04 --web-download
```

Reinicie se pedir, abra "Ubuntu 20.04" no menu Iniciar e crie usuário e senha (a senha não aparece enquanto você digita, é normal).

**ROS Noetic:** no terminal do Ubuntu, cole esta linha inteira (no terminal, colar é com o **botão direito** do mouse ou Ctrl+Shift+V) e digite a senha:

```bash
sudo apt update && sudo apt install -y curl git && curl -L -o /tmp/ros-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/1.2.0/ros-apt-source_1.2.0.focal_all.deb" && sudo dpkg -i /tmp/ros-apt-source.deb && sudo apt update && sudo apt install -y ros-noetic-desktop-full && echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc && echo 'export ROS_HOSTNAME=localhost' >> ~/.bashrc && echo 'export ROS_MASTER_URI=http://localhost:11311' >> ~/.bashrc && source ~/.bashrc
```

Leva de 20 a 40 minutos. No final, `rosversion -d` tem que mostrar `noetic`.

## 4. Baixar o projeto e compilar

```bash
mkdir -p ~/catkin_ws/src && cd ~/catkin_ws/src && git clone https://github.com/ianvellozo/robo-garcom.git robo-garcom && cd ~/catkin_ws && catkin_make && echo "source ~/catkin_ws/devel/setup.bash" >> ~/.bashrc && source ~/.bashrc
```

No final do `catkin_make` tem que aparecer `[100%]`, sem erro em vermelho.

**Para pegar as atualizações dos outros** (faça sempre antes de começar a mexer):

```bash
cd ~/catkin_ws/src/robo-garcom && git stash && git pull && cd ~/catkin_ws && catkin_make
```

## 5. Rodar

```bash
roslaunch garcom_bringup sim.launch
```

Os pedidos começam a aparecer no terminal. Para ver o "organograma" dos nós, abra **outro terminal** do Ubuntu e rode `rqt_graph`. Para parar, aperte **Ctrl+C**.

Para ver os alertas de prazo funcionando (prazo de 30 s e pedidos a cada 5 s):

```bash
roslaunch garcom_bringup sim.launch deadline_s:=30 order_period_s:=5
```

---

## 6. A sua parte

A regra é uma só: **troque o que é simulado pelo de verdade, mas mantenha os mesmos nomes de tópicos, serviços e ações.** Assim o resto do sistema continua funcionando sem ninguém precisar mexer no código do outro. Os arquivos têm comentários `TODO` mostrando onde mexer.

### Ana: simulação e navegação

**Arquivos:** `garcom_simulation/` (mundo e robô no Gazebo) e `garcom_navigation/scripts/navigation_node.py`.

**O que o seu nó precisa fazer (o "contrato"):**

| Recebe | Envia |
| --- | --- |
| Ação `/garcom/go_to_point` com o nome do ponto (`base`, `estacao_cafe`, `mesa_2`...) | Resultado `success = True` quando chegar |
| Coordenadas de cada ponto em `config/pontos.yaml` | `/garcom/robot_at` (texto com o nome do ponto) ao chegar |
| | `/cmd_vel` (velocidade) para mover o robô |

**Ordem sugerida, do mais fácil ao mais difícil.** Para a apresentação de 26/10, o mínimo é chegar ao passo 3:

1. **P3-DX no Gazebo andando pelo teclado.** A aula 7 (`Gazebo.pdf`) traz o modelo do P3DX (`pioneer3dx.xacro` e `pioneer3dx.gazebo`, com laser e o plugin de tração diferencial). Teste com `rosrun teleop_twist_keyboard teleop_twist_keyboard.py` (instale com `sudo apt install ros-noetic-teleop-twist-keyboard`) ou com `rostopic pub /cmd_vel ...`, como na aula.
2. **Restaurante no Gazebo:** paredes, a base, duas estações e quatro mesas (podem ser caixas simples). Salve em `garcom_simulation/worlds/` e crie um launch em `garcom_simulation/launch/` que abre o mundo com o robô.
3. **Ir até um ponto:** no `navigation_node.py`, troque o "finge 3 s" por um controle que lê a posição do robô em `/odom` e publica em `/cmd_vel` até chegar nas coordenadas do `pontos.yaml`. Depois atualize as coordenadas do `pontos.yaml` para o seu mundo.
4. **Mapa e A\*:** gere o mapa com o `gmapping` e use o `move_base` com o planejador global em modo A\* (`global_planner` com `use_dijkstra: false`).

**Testar sozinha:** com o seu launch rodando, mande o robô para um ponto:

```bash
rostopic pub -1 /garcom/go_to_point/goal garcom_msgs/GoToPointActionGoal "goal: {point_name: 'mesa_2'}"
```

### Mariana: percepção, interface e estoque

**Arquivos:** `garcom_perception/scripts/aruco_node.py`, `garcom_interface/scripts/interface_node.py` e `garcom_stock/`.

**O que os seus nós precisam fazer (o "contrato"):**

| Nó | Recebe | Envia |
| --- | --- | --- |
| `perception` | Imagem da câmera | `/garcom/station_detected` (texto com o nome da estação, ex.: `estacao_cafe`) |
| `interface` | `/garcom/order_status` (para mostrar o andamento) | `/garcom/orders` (mensagem `Order`) |
| `stock_server` | Serviço `/garcom/check_stock` | Responde `available` e a lista `missing` |

**Ordem sugerida.** Para a apresentação de 26/10, o mínimo é chegar ao passo 3:

1. **Marcadores ArUco:** gere e imprima dois marcadores do dicionário **4x4_50**, ID 0 (café) e ID 1 (croissant). A relação ID → estação já está em `garcom_perception/config/marcadores.yaml`.
2. **Câmera no ROS:** `sudo apt install ros-noetic-usb-cam` e depois `rosrun usb_cam usb_cam_node _video_device:=/dev/video0`. A imagem sai em `/usb_cam/image_raw`. No WSL a webcam não aparece direto; dá para testar no PC do laboratório ou numa máquina virtual com a webcam liberada.
3. **Detecção ArUco no `aruco_node.py`:** assinar `/usb_cam/image_raw`, converter a imagem com o `cv_bridge`, detectar com `cv2.aruco.detectMarkers` (dicionário `DICT_4X4_50`), converter o ID no nome da estação pelo `marcadores.yaml` e publicar em `/garcom/station_detected`.
4. **Interface de verdade:** um modo em que a pessoa digita a mesa e os itens no terminal (`input()`) e o nó publica o `Order`. Mantenha o modo automático atual como opção, porque ele é usado nos testes. Depois pode virar uma página web.
5. **Estoque:** dar baixa nos itens a cada pedido entregue (previsto para 16/11).

**Testar sozinha:** rode o seu nó e, em outro terminal, veja o que ele publica:

```bash
rostopic echo /garcom/station_detected
rostopic echo /garcom/orders
```

---

## 7. Enviar o seu código para o GitHub

Antes, mande o seu **nome de usuário do GitHub** para o Ian adicionar você como colaboradora. Você recebe um convite por e-mail; é só aceitar.

**Jeito mais fácil (pelo site):**

1. No GitHub, abra o arquivo que você mudou (ex.: `garcom_navigation/scripts/navigation_node.py`).
2. Clique no **lápis** (Edit), apague tudo, cole o seu código novo e clique em **Commit changes**.
3. Arquivo novo: entre na pasta certa no site e use **Add file → Upload files**.

**Pelo terminal (git):** funciona depois que você cria um token em GitHub → Settings → Developer settings → Personal access tokens → **Tokens (classic)**, marcando a permissão `repo`. Quando o `git push` pedir a senha, cole o token.

```bash
cd ~/catkin_ws/src/robo-garcom
git add -A
git commit -m "Descreva o que você fez"
git pull --rebase
git push
```

Cada uma mexe só nos próprios arquivos, assim ninguém atrapalha o outro.

---

## 8. Problemas comuns

| Problema | Solução |
| --- | --- |
| `roscore` trava depois de "Done checking log file disk usage" | Rode `echo 'export ROS_HOSTNAME=localhost' >> ~/.bashrc && echo 'export ROS_MASTER_URI=http://localhost:11311' >> ~/.bashrc` e abra o terminal de novo |
| "Failed to contact master" | O `roscore` (ou o `roslaunch`) não está rodando em outro terminal |
| `rosrun` "não é reconhecido" | Você está no PowerShell, não no Ubuntu. Digite `wsl` ou abra "Ubuntu 20.04" |
| Ctrl+V não cola no terminal | Use o botão direito do mouse ou Ctrl+Shift+V |
| "is neither a launch file in package" ou "package not found" | Rode `source ~/catkin_ws/devel/setup.bash` (ou abra um terminal novo) |
| Nó Python não abre ("cannot launch node") | `chmod +x ~/catkin_ws/src/robo-garcom/*/scripts/*.py` |
| Mudei uma mensagem em `garcom_msgs` e deu erro | Rode `catkin_make` de novo |
