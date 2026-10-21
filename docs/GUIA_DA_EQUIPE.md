# Guia da equipe: como começar e o que cada um faz

Este guia é para quem nunca mexeu com ROS, Linux ou Git. Siga na ordem.

**Resumo:** o sistema inteiro já roda. Cada parte do robô é um programa separado (um "nó"). Desde 21/10 a navegação também é de verdade: o robô planeja a rota com A\*, anda pelo restaurante no Gazebo (ou num simulador 2D leve) e para ou desvia quando o laser vê alguém no caminho.

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
4. O **gerente de missões** monta uma **viagem**: pega os pedidos mais urgentes que cabem na bandeja (até 8 itens e 5 mesas), soma os itens por bancada e escolhe a melhor ordem de paradas, equilibrando a mesa mais perto e o pedido mais atrasado.
5. Para cada parada, a **navegação** calcula a rota com A\* no mapa e leva o robô até lá, de olho no laser.
6. Em cada bancada, a **tela da bancada** mostra o total ("2 × Café, 3 × Suco") e como separar por mesa. O funcionário monta e aperta **Bandeja pronta**.
7. O robô entrega mesa por mesa. Se tiver mais pedidos esperando, já sai para a próxima viagem; se não, volta para a base. Cada mudança de estado do pedido sai em `/garcom/order_status`.

| Nó | Responsável | Hoje |
| --- | --- | --- |
| `order_queue` (fila e prazos) | Ian | Pronto |
| `mission_manager` (viagens e ordem das paradas) | Ian | Pronto |
| `stock_server` (estoque) | Ian | Pronto |
| `web_server` (telas da mesa e da bancada no navegador) | Ian | Pronto |
| `interface` e `station_panel` (as mesmas telas no terminal) | Ian | Pronto |
| `navigation` (A\*, controle, parada e desvio) | Ian na parcial; Ana no robô real | Pronto no Gazebo e no simulador 2D |
| Gazebo (`mundo.launch`) e `simulador_2d` | Ian na parcial; Ana no robô real | Pronto |

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

Leva de 20 a 40 minutos. No final, `rosversion -d` tem que mostrar `noetic`. O `desktop-full` já traz o Gazebo e o RViz.

## 4. Baixar o projeto e compilar

```bash
mkdir -p ~/catkin_ws/src && cd ~/catkin_ws/src && git clone https://github.com/ianvellozo/robo-garcom.git robo-garcom && cd ~/catkin_ws && catkin_make && echo "source ~/catkin_ws/devel/setup.bash" >> ~/.bashrc && source ~/.bashrc
```

No final do `catkin_make` tem que aparecer `[100%]`, sem erro em vermelho.

**Para pegar as atualizações** (faça sempre antes de começar a mexer):

```bash
cd ~/catkin_ws/src/robo-garcom && git stash && git pull && cd ~/catkin_ws && catkin_make && source devel/setup.bash
```

## 5. Rodar

Escolha um dos três. Todos sobem o sistema inteiro; para parar, aperte **Ctrl+C**.

| Comando | O que abre |
| --- | --- |
| `roslaunch garcom_bringup gazebo.launch` | **Gazebo** com o restaurante e o P3-DX, mais o **RViz** mostrando o mapa, o laser (pontinhos vermelhos) e a rota A\* (linha amarela). A primeira abertura do Gazebo pode levar 1 ou 2 minutos. |
| `roslaunch garcom_bringup sim2d.launch` | **Simulador 2D leve** (sem Gazebo) e o RViz. O robô anda de verdade, com odometria e laser. Bom para testar rápido ou em computador fraco. |
| `roslaunch garcom_bringup sim.launch` | **Sem robô**: a viagem é só um tempo de espera. Serve para mexer nas telas, na fila e no estoque. |

Os pedidos aparecem sozinhos (um a cada 20 ou 30 s) e a bandeja é confirmada sozinha. Para você fazer tudo pelas telas, acrescente `auto_orders:=false auto_pickup:=false` no fim do comando e abra no navegador:

- http://localhost:8080/mesa (cliente)
- http://localhost:8080/bancada (funcionário)

**Testar a parada e o desvio:** com o Gazebo ou o simulador 2D rodando, abra **outro terminal** e rode:

| Comando | O que acontece |
| --- | --- |
| `rosrun garcom_simulation obstaculo.py` | Aparece um cliente em pé na rota, 1,5 m à frente do robô. Ele vê pelo laser e desvia sem precisar parar. |
| `rosrun garcom_simulation obstaculo.py frente 0.8` | O cliente aparece bem perto: o robô freia na hora, depois acha outro caminho. |
| `rosrun garcom_simulation obstaculo.py 8 0` | Cliente no ponto x = 8, y = 0 (é onde o robô para para atender a mesa 9). Se o robô estiver indo para lá, ele para antes e espera. |
| `rosrun garcom_simulation obstaculo.py tirar` | Tira todos os clientes; o robô continua. |

No Gazebo também dá para pôr uma caixa na frente do robô pelo menu de cima (cubo) e arrastar.

Outros jeitos de rodar:

| Para... | Rode |
| --- | --- |
| Ver os alertas de prazo | `roslaunch garcom_bringup sim.launch deadline_s:=30 order_period_s:=5` |
| Gazebo sem RViz (mais leve) | `roslaunch garcom_bringup gazebo.launch rviz:=false` |
| Só o restaurante no Gazebo, andando pelo teclado | `roslaunch garcom_simulation mundo.launch` e, em outro terminal, `rosrun teleop_twist_keyboard teleop_twist_keyboard.py` (instale com `sudo apt install ros-noetic-teleop-twist-keyboard`) |
| Fazer os pedidos pelo terminal | `rosrun garcom_interface interface_node.py` (com `auto_orders:=false`) |
| Repor um item | `rosservice call /garcom/restock "{item: 'rosquinha', quantity: 5}"` |
| Ver o "organograma" dos nós | `rqt_graph` em outro terminal |

---

## 6. Simulação e navegação

Na Apresentação 2 (26/10), o Ian cobriu esta parte para aliviar a Ana. Daqui para frente, a Ana leva isso para o P3-DX real (veja o cronograma).

### Arquivos

| Arquivo | O que tem |
| --- | --- |
| `garcom_navigation/config/pontos.yaml` | Onde o robô **para** em cada mesa, bancada e base, e para onde fica virado |
| `garcom_simulation/config/restaurante.yaml` | Medidas do salão, das mesas, das cadeiras e das bancadas |
| `garcom_simulation/scripts/gerar_mundo.py` | Gera o mundo do Gazebo (`worlds/restaurante.world`) e o mapa (`garcom_navigation/maps/restaurante.pgm` e `.yaml`) a partir dos dois arquivos acima |
| `garcom_simulation/urdf/p3dx_garcom.urdf.xacro` | O P3-DX: rodas, roda boba, laser na frente e bandeja. Usa os plugins da aula 7 (`libgazebo_ros_diff_drive.so` e `libgazebo_ros_laser.so`) |
| `garcom_simulation/scripts/simulador_2d.py` | Simulador leve: mesmo restaurante, mesmos tópicos (`/cmd_vel`, `/odom`, `/scan`) |
| `garcom_simulation/scripts/obstaculo.py` | Põe e tira clientes em pé (Gazebo e simulador 2D) |
| `garcom_navigation/scripts/planejador.py` | Lê o mapa, calcula a margem de segurança e roda o A\* |
| `garcom_navigation/scripts/navigation_node.py` | Recebe "vá até mesa_2", segue a rota e cuida dos obstáculos |
| `garcom_navigation/config/navegacao.yaml` | Velocidade, aceleração, margem de segurança e distâncias de parada |

Cada mesa fica 75 cm à frente do ponto onde o robô para (na direção do `yaw` do ponto), com uma cadeira de cada lado. Por isso, **mudou o `pontos.yaml`, rode `rosrun garcom_simulation gerar_mundo.py`**: o mundo do Gazebo e o mapa acompanham.

### Como a navegação funciona

1. **Mapa:** quadradinhos de 5 cm, cada um livre, ocupado ou desconhecido. Para cada quadradinho o planejador calcula a distância até o móvel mais perto.
2. **Margem de segurança:** o centro do robô nunca chega a menos de 30 cm de um móvel (proibido). Entre 30 e 70 cm pode passar, mas custa mais, então o A\* prefere o meio dos corredores.
3. **A\*:** busca em 8 direções a rota de menor custo até o ponto. Depois corta os zigue-zagues em linha reta quando dá. Leva menos de 0,1 s.
4. **Controle:** o robô persegue um ponto da rota 50 cm à frente (*pure pursuit*), lendo a posição em `/odom` e mandando velocidade em `/cmd_vel`. Acelera devagar (0,4 m/s²) por causa da bandeja, chega devagar e no fim gira para ficar de frente para a mesa.
5. **Laser e obstáculos:** a cada leitura do laser, o robô confere o "corredor" que ele vai ocupar nos próximos metros da rota:
   - algo **novo** (que não está no mapa) encostando na rota mais à frente: marca no mapa e **replaneja** antes de chegar perto (desvio);
   - algo a menos de 1,2 m: **desacelera**;
   - algo a menos de 45 cm do para-choque: **para** (freio forte);
   - parado há 3 s e o obstáculo continua: marca no mapa e procura **outro caminho**;
   - sem outro caminho (por exemplo, a pessoa está no ponto da mesa): **espera** ela sair e segue.

   As marcas somem depois de 20 s ou quando o laser olha de novo e não vê mais nada lá. Pessoas ganham 15 cm a mais de margem que os móveis.
6. **Estado:** a navegação publica em `/garcom/nav_state` se está `andando`, `desviando`, `obstaculo` (parado), `sem_caminho` (esperando) ou `parado`. As telas da bancada e da mesa mostram o aviso.

### Para o P3-DX real (próximas semanas)

- O `sim.launch` já aceita os tópicos do robô real: `cmd_vel_topic:=/RosAria/cmd_vel odom_topic:=/RosAria/pose` (o laser SICK publica em `/scan`).
- **Mapa do laboratório:** fazer com o `gmapping` (`sudo apt install ros-noetic-gmapping ros-noetic-map-server`), andando com o joystick como na aula do Pioneer, e salvar com `rosrun map_server map_saver -f laboratorio`. Depois passar `mapa:=/caminho/laboratorio.yaml`.
- **Localização:** no simulador a odometria é perfeita; no robô real ela escorrega com o tempo. Falta ligar o AMCL para corrigir a posição no mapa.
- **Pontos:** medir no laboratório onde ficam a base, as bancadas e as mesas e atualizar o `pontos.yaml`.
- Se o laser estiver montado de cabeça para baixo, use `laser_invertido: true` no `navegacao.yaml`.

---

## 7. Enviar o seu código para o GitHub

Antes, mande o seu **nome de usuário do GitHub** para o Ian adicionar você como colaboradora. Você recebe um convite por e-mail; é só aceitar.

**Jeito mais fácil (pelo site):**

1. No GitHub, abra o arquivo que você mudou (ex.: `garcom_navigation/config/pontos.yaml`).
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
| Gazebo abre preto, trava ou fecha sozinho | Feche tudo e rode com o desenho por software: `LIBGL_ALWAYS_SOFTWARE=1 roslaunch garcom_bringup gazebo.launch`. Se continuar pesado, use `gui:=false` (o Gazebo roda escondido e o RViz mostra tudo) ou o `sim2d.launch` |
| Gazebo demora muito para abrir na primeira vez | É normal: ele procura modelos na internet. Espere 1 ou 2 minutos |
| "Sem odometria: confira o topico /odom" | O Gazebo (ou o simulador 2D) ainda não subiu. Espere ou confira se o robô apareceu no mundo |
| O robô fica girando ou não sai do lugar | Confira se não tem cliente de teste esquecido no caminho: `rosrun garcom_simulation obstaculo.py tirar` |
