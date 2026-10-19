# Guia da equipe: como começar e o que cada um faz

Este guia é para quem nunca mexeu com ROS, Linux ou Git. Siga na ordem.

**Resumo:** o sistema inteiro já roda. Cada parte do robô é um programa separado (um "nó"). Só a **navegação** ainda é um esqueleto que finge a viagem; o trabalho da Ana é trocar o "fingir" pelo robô andando de verdade, sem mudar os nomes dos canais de comunicação.

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

1. Na **tela da mesa** (no navegador), o cliente escolhe os itens. O pedido sai em `/garcom/orders`.
2. A **fila** pede ao **estoque** para reservar os itens. Se faltar algum, o pedido é recusado.
3. A fila controla o **prazo máximo de entrega**: avisa quando o pedido passa de 70% do prazo e marca como atrasado se passar do prazo.
4. O **gerente de missões** pega o pedido mais urgente, separa os itens por estação e manda a **navegação** ir até cada estação.
5. Na estação, a **tela da bancada** mostra o que colocar na bandeja ("2 × Café, 1 × Suco"). O funcionário monta e aperta **Bandeja pronta**.
6. O gerente manda a navegação ir até a mesa e depois voltar para a base. Cada mudança de estado do pedido sai em `/garcom/order_status`.

| Nó | Responsável | Hoje |
| --- | --- | --- |
| `order_queue` (fila e prazos) | Ian | Pronto |
| `mission_manager` (missões) | Ian | Pronto |
| `stock_server` (estoque) | Ian | Pronto |
| `web_server` (telas da mesa e da bancada no navegador) | Ian | Pronto |
| `interface` e `station_panel` (as mesmas telas no terminal) | Ian | Pronto |
| `navigation` | Ana | **Esqueleto:** finge a viagem em 3 s |

A leitura de marcadores ArUco foi retirada do projeto, com o aval do professor, depois que a Mariana saiu da disciplina. A tela da estação ocupa esse lugar.

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

**Para pegar as atualizações** (faça sempre antes de começar a mexer):

```bash
cd ~/catkin_ws/src/robo-garcom && git stash && git pull && cd ~/catkin_ws && catkin_make
```

## 5. Rodar

```bash
roslaunch garcom_bringup sim.launch
```

Os pedidos começam a aparecer no terminal. Para ver o "organograma" dos nós, abra **outro terminal** do Ubuntu e rode `rqt_graph`. Para parar, aperte **Ctrl+C**.

Outros jeitos de rodar:

| Para... | Rode |
| --- | --- |
| Usar as telas no navegador | `roslaunch garcom_bringup sim.launch auto_orders:=false auto_pickup:=false` e abra http://localhost:8080/mesa?mesa=2 e http://localhost:8080/bancada |
| Ver os alertas de prazo | `roslaunch garcom_bringup sim.launch deadline_s:=30 order_period_s:=5` |
| Fazer os pedidos você mesmo | `roslaunch garcom_bringup sim.launch auto_orders:=false` e, em outro terminal, `rosrun garcom_interface interface_node.py` |
| Confirmar a coleta você mesmo | `roslaunch garcom_bringup sim.launch auto_pickup:=false` e, em outro terminal, `rosrun garcom_interface station_panel.py` |
| Repor um item | `rosservice call /garcom/restock "{item: 'rosquinha', quantity: 5}"` |

O cardápio (itens, estação de cada item e estoque inicial) fica em `garcom_stock/config/cardapio.yaml`.

---

## 6. Parte da Ana: simulação e navegação

**Arquivos:** `garcom_simulation/` (mundo e robô no Gazebo) e `garcom_navigation/scripts/navigation_node.py`.

A regra é uma só: **troque o "finge a viagem" pelo robô andando de verdade, mas mantenha os mesmos nomes de tópicos e ações.** Assim o resto do sistema continua funcionando sem ninguém mexer no código do outro. O arquivo tem um comentário `TODO` mostrando onde mexer.

**O que o nó de navegação precisa fazer (o "contrato"):**

| Recebe | Envia |
| --- | --- |
| Ação `/garcom/go_to_point` com o nome do ponto (`base`, `estacao_cafe`, `mesa_2`...) | Resultado `success = True` quando chegar |
| Coordenadas de cada ponto em `config/pontos.yaml` | `/garcom/robot_at` (texto com o nome do ponto) ao chegar |
| | `/cmd_vel` (velocidade) para mover o robô |

**Ordem sugerida, do mais fácil ao mais difícil.** Para a apresentação de 26/10, o mínimo é chegar ao passo 3:

1. **P3-DX no Gazebo andando pelo teclado.** A aula 7 (`Gazebo.pdf`) traz o modelo do P3DX (`pioneer3dx.xacro` e `pioneer3dx.gazebo`, com laser e o plugin de tração diferencial). Teste com `rosrun teleop_twist_keyboard teleop_twist_keyboard.py` (instale com `sudo apt install ros-noetic-teleop-twist-keyboard`) ou com `rostopic pub /cmd_vel ...`, como na aula.
2. **Restaurante no Gazebo:** paredes, a base, duas estações e quatro mesas (podem ser caixas simples). Salve em `garcom_simulation/worlds/` e crie um launch em `garcom_simulation/launch/` que abre o mundo com o robô. O Ian vai ajudar nesta parte.
3. **Ir até um ponto:** no `navigation_node.py`, troque o "finge 3 s" por um controle que lê a posição do robô em `/odom` e publica em `/cmd_vel` até chegar nas coordenadas do `pontos.yaml`. Depois atualize as coordenadas do `pontos.yaml` para o mundo do Gazebo.
4. **Mapa e A\*:** gere o mapa com o `gmapping` e use o `move_base` com o planejador global em modo A\* (`global_planner` com `use_dijkstra: false`).

**Testar sozinha:** com o seu launch rodando, mande o robô para um ponto:

```bash
rostopic pub -1 /garcom/go_to_point/goal garcom_msgs/GoToPointActionGoal "goal: {point_name: 'mesa_2'}"
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

Cada um mexe só nos próprios arquivos, assim ninguém atrapalha o outro.

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
| Erro com mensagens (`garcom_msgs`) depois de atualizar | Rode `catkin_make` de novo |
| "Address already in use" (porta 8080) | Já tem outro `roslaunch` rodando. Feche o outro, ou use `web_port:=8081` e abra http://localhost:8081 |
| A tela diz "Sem conexão com o robô" | O `roslaunch` não está rodando ou foi fechado |
