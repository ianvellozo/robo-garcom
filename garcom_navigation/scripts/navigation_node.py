#!/usr/bin/env python3
"""Navegacao do Robo Garcom.

Servidor da acao /garcom/go_to_point: leva o robo ate um ponto do pontos.yaml
(/garcom/points) e, ao chegar, publica o nome do ponto em /garcom/robot_at.

Dois modos (parametro ~modo):
  simulada  finge a viagem (tempo = distancia / velocidade). Serve para testar as
            telas e a missao sem robo nenhum.
  real      o robo anda de verdade (Gazebo, simulador 2D ou P3-DX):
            1. planeja a rota no mapa com A* (planejador.py);
            2. segue a rota lendo a odometria (~odom_topic) e mandando velocidade
               (~cmd_vel_topic), com aceleracao suave para nao derrubar a bandeja;
            3. olha o laser (~scan_topic): se aparece algo no caminho, desacelera e
               PARA antes de encostar. Se o obstaculo continua la, marca no mapa e
               replaneja por outro caminho (desvio). Se ele sai, segue a rota.
               Se algo aparece colado na frente, o robo da uma re curta (o laser so
               ve a frente, entao ele confere no mapa se atras esta livre).

Publica tambem:
  /garcom/nav_state  parado, andando, obstaculo, desviando, recuando ou sem_caminho (telas)
  /garcom/path       rota planejada (nav_msgs/Path, para o RViz)
  /map               mapa usado (nav_msgs/OccupancyGrid, para o RViz)
"""
import bisect
import collections
import math
import os
import sys
import threading

import actionlib
import rospy
from std_msgs.msg import String
from garcom_msgs.msg import GoToPointAction, GoToPointFeedback, GoToPointResult

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import planejador  # noqa: E402

MAPA_PADRAO = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                           "maps", "restaurante.yaml")


def normalizar(a):
    return math.atan2(math.sin(a), math.cos(a))


def limitar(v, lim):
    return max(-lim, min(lim, v))


class Base:
    """O que os dois modos tem em comum: pontos, acao e topicos de estado."""

    def __init__(self):
        self.points = rospy.get_param("/garcom/points", {})
        self.at_pub = rospy.Publisher("/garcom/robot_at", String, queue_size=10, latch=True)
        self.state_pub = rospy.Publisher("/garcom/nav_state", String, queue_size=10, latch=True)
        self.estado = None
        self.set_estado("parado")
        self.server = actionlib.SimpleActionServer(
            "/garcom/go_to_point", GoToPointAction, execute_cb=self.execute, auto_start=False)

    def set_estado(self, estado):
        if estado != self.estado:
            self.estado = estado
            self.state_pub.publish(String(data=estado))

    def execute(self, goal):
        nome = goal.point_name
        if nome not in self.points:
            rospy.logerr("Ponto desconhecido: %s", nome)
            self.server.set_aborted(GoToPointResult(success=False))
            return
        resultado = self.ir(nome, self.points[nome])
        self.set_estado("parado")
        if resultado is None:
            self.server.set_preempted(GoToPointResult(success=False))
        elif resultado:
            self.at_pub.publish(String(data=nome))
            self.server.set_succeeded(GoToPointResult(success=True))
        else:
            self.server.set_aborted(GoToPointResult(success=False))

    def feedback(self, restante):
        self.server.publish_feedback(GoToPointFeedback(distance_remaining=restante))


class NavegacaoSimulada(Base):
    """Finge a viagem: nao move robo nenhum."""

    def __init__(self):
        super().__init__()
        self.speed = float(rospy.get_param("/garcom/robot_speed_mps", 1.5))
        self.here = "base"
        self.server.start()
        rospy.loginfo("Navegacao SIMULADA pronta: %d pontos, %.1f m/s (o robo nao anda).",
                      len(self.points), self.speed)

    def ir(self, nome, alvo):
        a, b = self.points.get(self.here, alvo), alvo
        dist = math.hypot(b["x"] - a["x"], b["y"] - a["y"])
        duracao = max(0.5, dist / self.speed)
        rospy.loginfo("Indo para %s: %.1f m, %.1f s (simulado)", nome, dist, duracao)
        self.set_estado("andando")
        passos = 10
        for i in range(passos):
            if self.server.is_preempt_requested() or rospy.is_shutdown():
                return None
            self.feedback(dist * (passos - i) / passos)
            rospy.sleep(duracao / passos)
        self.here = nome
        return True


class NavegacaoReal(Base):
    """Planeja com A*, segue a rota com a odometria e para/desvia com o laser."""

    def __init__(self):
        super().__init__()
        from geometry_msgs.msg import PoseStamped, Twist
        from nav_msgs.msg import OccupancyGrid, Odometry, Path
        from sensor_msgs.msg import LaserScan
        self.Twist, self.Path, self.PoseStamped = Twist, Path, PoseStamped

        p = lambda nome, padrao: rospy.get_param("~" + nome, padrao)  # noqa: E731
        self.v_max = float(p("velocidade_max", 0.45))       # m/s
        self.w_max = float(p("velocidade_giro", 1.0))       # rad/s
        self.acel = float(p("aceleracao", 0.4))             # m/s^2 (suave por causa da bandeja)
        self.freio = float(p("freio", 0.8))                 # m/s^2 numa parada normal
        self.freio_forte = float(p("freio_emergencia", 1.5))
        self.acel_giro = float(p("aceleracao_giro", 2.0))   # rad/s^2
        self.olhar_a_frente = float(p("olhar_a_frente", 0.5))  # m (pure pursuit)
        self.tolerancia = float(p("tolerancia", 0.08))      # m
        self.tolerancia_giro = float(p("tolerancia_giro", 0.06))  # rad
        self.frente = float(p("frente_do_robo", 0.25))      # do centro ate o para-choque (m)
        self.meia_largura = float(p("largura_checagem", 0.27))  # meia largura do corredor checado (m)
        self.d_parada = float(p("distancia_parada", 0.45))  # para quando o obstaculo fica a isso do para-choque
        self.d_reduzir = float(p("distancia_reduzir", 1.2))  # comeca a desacelerar a esta distancia
        self.espera = float(p("espera_obstaculo_s", 3.0))   # espera antes de desviar
        self.validade = float(p("validade_obstaculo_s", 20.0))
        self.d_re = float(p("distancia_re", 0.40))          # algo mais perto que isso do centro: da re
        self.re_max = float(p("re_max", 0.40))              # quanto da re no maximo (m)
        self.v_re = float(p("velocidade_re", 0.12))         # velocidade da re (m/s)
        self.laser_x = float(p("laser_x", 0.15))            # laser a frente do centro (m)
        self.laser_invertido = bool(p("laser_invertido", False))
        mapa_path = p("mapa", MAPA_PADRAO)

        t0 = rospy.get_time()
        self.mapa = planejador.Mapa(mapa_path)
        self.plan = planejador.Planejador(
            self.mapa, raio_robo=float(p("raio_robo", 0.30)),
            raio_conforto=float(p("raio_conforto", 0.70)), peso=float(p("peso_conforto", 3.0)),
            margem_pessoas=float(p("margem_pessoas", 0.15)))
        rospy.loginfo("Mapa %s: %d x %d (%.0f cm), preparado em %.2f s",
                      os.path.basename(mapa_path), self.mapa.largura, self.mapa.altura,
                      self.mapa.res * 100, rospy.get_time() - t0)

        self.lock = threading.Lock()
        self.pose = None   # (x, y, yaw)
        self.historico = collections.deque(maxlen=200)  # (t, x, y, yaw) dos ultimos segundos
        self.scan = None
        self.v = self.w = 0.0

        self.cmd_pub = rospy.Publisher(p("cmd_vel_topic", "/cmd_vel"), Twist, queue_size=1)
        self.path_pub = rospy.Publisher("/garcom/path", Path, queue_size=1, latch=True)
        self.map_pub = rospy.Publisher("/map", OccupancyGrid, queue_size=1, latch=True)
        rospy.Subscriber(p("odom_topic", "/odom"), Odometry, self.on_odom, queue_size=1)
        rospy.Subscriber(p("scan_topic", "/scan"), LaserScan, self.on_scan, queue_size=1)
        self.publicar_mapa(OccupancyGrid)
        self.server.start()
        rospy.loginfo("Navegacao REAL pronta: A* + laser, ate %.2f m/s, para a %.2f m de obstaculos.",
                      self.v_max, self.d_parada)

    # ------------------------------------------------------------ entradas
    def on_odom(self, msg):
        q = msg.pose.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        pose = (msg.pose.pose.position.x, msg.pose.pose.position.y, yaw)
        with self.lock:
            self.pose = pose
            self.historico.append((msg.header.stamp.to_sec(),) + pose)

    def on_scan(self, msg):
        with self.lock:
            self.scan = msg

    def pose_em(self, t):
        """Pose do robo no instante t (a leitura do laser e de alguns ms atras: se o robo
        estiver girando, usar a pose de agora entortaria o mapa do laser)."""
        with self.lock:
            hist = list(self.historico)
        if not hist or t <= 0:
            return None
        tempos = [h[0] for h in hist]
        k = bisect.bisect_left(tempos, t)
        if k == 0:
            return hist[0][1:] if tempos[0] - t < 0.2 else None
        if k == len(hist):
            return hist[-1][1:] if t - tempos[-1] < 0.2 else None
        (t0, x0, y0, a0), (t1, x1, y1, a1) = hist[k - 1], hist[k]
        f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
        return (x0 + f * (x1 - x0), y0 + f * (y1 - y0), a0 + f * normalizar(a1 - a0))

    def pontos_laser(self, x, y, yaw):
        """Leituras do laser como pontos no mapa (x, y) e no robo (frente, lado)."""
        with self.lock:
            scan = self.scan
        if scan is None:
            return []
        pose_scan = self.pose_em(scan.header.stamp.to_sec())
        if pose_scan is not None:
            x, y, yaw = pose_scan
        pts = []
        c, s = math.cos(yaw), math.sin(yaw)
        a = scan.angle_min
        sinal = -1.0 if self.laser_invertido else 1.0
        for r in scan.ranges:
            if scan.range_min < r < scan.range_max and r < 4.0:
                ang = sinal * a
                fx = self.laser_x + r * math.cos(ang)
                fy = r * math.sin(ang)
                pts.append((x + c * fx - s * fy, y + s * fx + c * fy, fx, fy))
            a += scan.angle_increment
        return pts

    # --------------------------------------------------------------- saidas
    def publicar_mapa(self, OccupancyGrid):
        msg = OccupancyGrid()
        msg.header.frame_id = "map"
        msg.header.stamp = rospy.Time.now()
        msg.info.resolution = self.mapa.res
        msg.info.width, msg.info.height = self.mapa.largura, self.mapa.altura
        msg.info.origin.position.x, msg.info.origin.position.y = self.mapa.x0, self.mapa.y0
        msg.info.origin.orientation.w = 1.0
        msg.data = self.mapa.dados_occupancy_grid()
        self.map_pub.publish(msg)

    def publicar_rota(self, rota):
        msg = self.Path()
        msg.header.frame_id = "map"
        msg.header.stamp = rospy.Time.now()
        for x, y in rota:
            ps = self.PoseStamped()
            ps.header = msg.header
            ps.pose.position.x, ps.pose.position.y = x, y
            ps.pose.orientation.w = 1.0
            msg.poses.append(ps)
        self.path_pub.publish(msg)

    def comandar(self, v_alvo, w_alvo, dt, freio=None):
        """Manda velocidade respeitando a aceleracao maxima (movimento suave)."""
        if v_alvo >= self.v:
            a = self.acel
        else:
            a = freio if freio is not None else self.freio
        self.v += limitar(v_alvo - self.v, a * dt)
        giro = self.acel_giro if abs(w_alvo) > abs(self.w) else 2 * self.acel_giro
        self.w += limitar(w_alvo - self.w, giro * dt)
        cmd = self.Twist()
        cmd.linear.x, cmd.angular.z = self.v, self.w
        self.cmd_pub.publish(cmd)

    def parar_ja(self):
        self.v = self.w = 0.0
        self.cmd_pub.publish(self.Twist())

    # --------------------------------------------------------- geometria
    @staticmethod
    def projetar(rota, x, y, inicio):
        """Segmento da rota mais perto do robo (procura so para frente)."""
        melhor, melhor_d = inicio, float("inf")
        for i in range(inicio, len(rota) - 1):
            (ax, ay), (bx, by) = rota[i], rota[i + 1]
            dx, dy = bx - ax, by - ay
            l2 = dx * dx + dy * dy or 1e-9
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / l2))
            d = math.hypot(ax + t * dx - x, ay + t * dy - y)
            if d < melhor_d - 1e-6:
                melhor, melhor_d = i, d
            elif d > melhor_d + 1.0:
                break
        return melhor

    @staticmethod
    def a_frente(rota, i, x, y, limite):
        """Pedaco da rota a partir do robo: lista de pontos com ate `limite` metros."""
        trecho, total = [(x, y)], 0.0
        for px, py in rota[i + 1:]:
            ax, ay = trecho[-1]
            d = math.hypot(px - ax, py - ay)
            if total + d >= limite:
                f = (limite - total) / d if d > 0 else 0
                trecho.append((ax + f * (px - ax), ay + f * (py - ay)))
                return trecho, limite
            trecho.append((px, py))
            total += d
        return trecho, total

    @staticmethod
    def distancia_ao_trecho(trecho, px, py):
        """(distancia lateral, distancia ao longo do trecho) do ponto ate o trecho."""
        melhor, ao_longo, acumulado = float("inf"), 0.0, 0.0
        for (ax, ay), (bx, by) in zip(trecho, trecho[1:]):
            dx, dy = bx - ax, by - ay
            l = math.hypot(dx, dy)
            if l < 1e-9:
                continue
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (l * l)))
            d = math.hypot(ax + t * dx - px, ay + t * dy - py)
            if d < melhor:
                melhor, ao_longo = d, acumulado + t * l
            acumulado += l
        return melhor, ao_longo

    def obstaculo_no_caminho(self, rota, i, x, y, pts, restante):
        """Distancia (ao longo da rota, a partir do para-choque) ate o primeiro obstaculo
        dentro do corredor que o robo vai ocupar. None se o caminho esta livre."""
        alcance = min(self.frente + self.d_reduzir, restante + 0.05)
        trecho, _ = self.a_frente(rota, i, x, y, alcance)
        if len(trecho) < 2:
            return None
        mais_perto = None
        for mx, my, fx, fy in pts:
            # algo que nao esta no mapa colado no para-choque: para ja
            # (so na frente: o que esta do lado nao impede o robo de seguir)
            if 0.0 < fx < self.frente + 0.12 and abs(fy) < self.meia_largura and \
                    self.plan.distancia_estatica(mx, my) > 0.12:
                return 0.0
            if fx <= 0.0 or math.hypot(fx, fy) > alcance + self.meia_largura:
                continue
            lateral, ao_longo = self.distancia_ao_trecho(trecho, mx, my)
            if lateral < self.meia_largura:
                d = max(0.0, ao_longo - self.frente)
                if mais_perto is None or d < mais_perto:
                    mais_perto = d
        return mais_perto

    def colado(self, pts):
        """Distancia (do centro do robo) da coisa mais perto que nao esta no mapa, na frente."""
        d = float("inf")
        for mx, my, fx, fy in pts:
            if fx > -0.05 and self.plan.distancia_estatica(mx, my) > 0.12:
                d = min(d, math.hypot(fx, fy))
        return d

    def dar_re(self, taxa, dt):
        """Re curta e devagar para longe de algo colado na frente. Devolve quanto recuou (m)."""
        with self.lock:
            x0, y0, yaw = self.pose
        # o laser so enxerga a frente: confere no mapa se atras esta livre
        # (para se for chegar perto de um movel ou de alguem visto antes)
        c, s_ = math.cos(yaw), math.sin(yaw)
        livre = 0.0
        ant_est = self.plan.distancia_estatica(x0, y0)
        ant_din = self.plan.distancia_dinamica(x0, y0)
        while livre + 0.05 <= self.re_max + 1e-9:
            bx, by = x0 - (livre + 0.05) * c, y0 - (livre + 0.05) * s_
            d_est, d_din = self.plan.distancia_estatica(bx, by), self.plan.distancia_dinamica(bx, by)
            if (d_est < 0.32 and d_est < ant_est) or (d_din < 0.32 and d_din < ant_din):
                break
            ant_est, ant_din = d_est, d_din
            livre += 0.05
        if livre < 0.1:
            rospy.logwarn("Algo colado na frente e sem espaco atras: esperando.")
            return 0.0
        rospy.logwarn("Obstaculo colado na frente: dando re de %.0f cm.", livre * 100)
        self.set_estado("recuando")
        andou = 0.0
        fim = rospy.get_time() + livre / self.v_re + 3.0
        while not rospy.is_shutdown() and rospy.get_time() < fim and not self.server.is_preempt_requested():
            with self.lock:
                x, y, _ = self.pose
            andou = math.hypot(x - x0, y - y0)
            if andou >= livre - 0.02:
                break
            self.comandar(-min(self.v_re, max(0.05, 1.5 * (livre - andou))), 0.0, dt)
            taxa.sleep()
        while abs(self.v) > 0.01 and not rospy.is_shutdown():
            self.comandar(0.0, 0.0, dt)
            taxa.sleep()
        self.parar_ja()
        return andou

    def limpar_marcas_vistas(self, x, y, yaw):
        """Apaga obstaculos marcados que o laser agora enxerga atraves (a pessoa saiu)."""
        if not self.plan.marcas:
            return
        with self.lock:
            scan = self.scan
        if scan is None or not scan.ranges:
            return
        pose_scan = self.pose_em(scan.header.stamp.to_sec())
        if pose_scan is not None:
            x, y, yaw = pose_scan
        lx, ly = x + self.laser_x * math.cos(yaw), y + self.laser_x * math.sin(yaw)
        sinal = -1.0 if self.laser_invertido else 1.0
        n = len(scan.ranges)
        sumiram = []
        for k in list(self.plan.marcas):
            mx, my = self.mapa.centro(k)
            dist = math.hypot(mx - lx, my - ly)
            if dist > 3.0 or dist < 0.2:
                continue
            ang = sinal * normalizar(math.atan2(my - ly, mx - lx) - yaw)
            idx = int(round((ang - scan.angle_min) / scan.angle_increment))
            if not 0 <= idx < n:
                continue  # fora do campo de visao do laser
            vizinhos = [scan.ranges[j] for j in range(max(0, idx - 1), min(n, idx + 2))]
            if all(r > dist + 0.25 for r in vizinhos):  # o feixe passou do ponto: nao tem nada la
                sumiram.append(k)
        if sumiram:
            self.plan.esquecer(sumiram)

    def pontos_novos(self, pts, alcance=2.5):
        """Pontos do laser que NAO estao no mapa (pessoa, cadeira fora do lugar...)."""
        return [(mx, my) for mx, my, fx, fy in pts
                if math.hypot(fx, fy) < alcance and self.plan.distancia_estatica(mx, my) > 0.12]

    def rota_ameacada(self, rota, i, x, y, novos):
        """Ponto de um obstaculo novo que encosta na rota dos proximos 3 m (ou None)."""
        trecho, _ = self.a_frente(rota, i, x, y, 3.0)
        for mx, my in novos:
            if self.plan.distancia_obstaculo(mx, my) <= 0.06:
                continue  # ja estava marcado: a rota atual ja considera
            lateral, _ = self.distancia_ao_trecho(trecho, mx, my)
            if lateral < self.plan.raio_robo + self.plan.margem:
                return mx, my
        return None

    # ---------------------------------------------------------------- acao
    def esperar_pose(self, timeout):
        fim = rospy.get_time() + timeout
        while not rospy.is_shutdown() and rospy.get_time() < fim:
            with self.lock:
                if self.pose is not None:
                    return self.pose
            rospy.sleep(0.1)
        return None

    def planejar(self, x, y, gx, gy):
        t0 = rospy.get_time()
        rota = self.plan.planejar((x, y), (gx, gy))
        if rota:
            rospy.loginfo("Rota A*: %d pontos, %.1f m (calculada em %.2f s)",
                          len(rota), planejador.comprimento(rota), rospy.get_time() - t0)
            self.publicar_rota(rota)
        return rota

    def ir(self, nome, alvo):
        gx, gy, gyaw = alvo["x"], alvo["y"], alvo.get("yaw")
        pose = self.esperar_pose(5.0)
        if pose is None:
            rospy.logerr("Sem odometria: confira o topico %s", rospy.get_param("~odom_topic", "/odom"))
            return False
        x, y, _ = pose
        rospy.loginfo("Indo para %s (%.2f, %.2f)", nome, gx, gy)
        self.plan.esquecer_vencidos(rospy.get_time())
        rota = self.planejar(x, y, gx, gy)
        taxa = rospy.Rate(20)
        dt = 0.05
        inicio_sem_rota = rospy.get_time()
        while rota is None:
            self.set_estado("sem_caminho")
            if self.server.is_preempt_requested() or rospy.is_shutdown():
                return None
            if rospy.get_time() - inicio_sem_rota > 60:
                rospy.logerr("Nao achei caminho ate %s.", nome)
                return False
            rospy.sleep(2.0)
            self.plan.esquecer_vencidos(rospy.get_time())
            x, y, yaw = self.esperar_pose(1.0) or (x, y, 0)
            if self.colado(self.pontos_laser(x, y, yaw)) < self.d_re:
                self.dar_re(taxa, dt)
                x, y, yaw = self.esperar_pose(1.0) or (x, y, yaw)
            self.limpar_marcas_vistas(x, y, yaw)
            rota = self.planejar(x, y, gx, gy)

        self.set_estado("andando")
        desviando = False
        i = 0
        bloqueado_desde = None
        ultimo_replan = ultimo_olhar = ultimo_feedback = ultima_re = 0.0
        res = 0
        progresso_t, progresso_d = rospy.get_time(), float("inf")
        limite_t = rospy.get_time() + max(120.0, 4 * planejador.comprimento(rota) / self.v_max + 60)

        while not rospy.is_shutdown():
            if self.server.is_preempt_requested():
                self.parar_ja()
                return None
            agora = rospy.get_time()
            if agora > limite_t:
                self.parar_ja()
                rospy.logerr("Demorou demais para chegar em %s.", nome)
                return False
            with self.lock:
                x, y, yaw = self.pose
            dist_alvo = math.hypot(gx - x, gy - y)
            if dist_alvo < self.tolerancia:
                break

            i = self.projetar(rota, x, y, i)
            trecho, restante = self.a_frente(rota, i, x, y, 1e9)
            if agora - ultimo_feedback > 0.5:
                self.feedback(restante)
                ultimo_feedback = agora

            # --- para onde ir (pure pursuit): um ponto da rota a alguns cm a frente
            alvo_l, _ = self.a_frente(rota, i, x, y, self.olhar_a_frente)
            ax, ay = alvo_l[-1]
            erro = normalizar(math.atan2(ay - y, ax - x) - yaw)
            if abs(erro) > 0.7:
                v_alvo, w_alvo = 0.0, limitar(1.5 * erro, self.w_max)  # gira no lugar
            else:
                v_alvo = self.v_max * max(0.25, math.cos(erro))
                d_l = max(math.hypot(ax - x, ay - y), 0.05)
                w_alvo = limitar(2.0 * v_alvo * math.sin(erro) / d_l + 0.8 * erro, self.w_max)
                v_alvo = min(v_alvo, max(0.08, 0.8 * restante))  # chega devagar

            pts = self.pontos_laser(x, y, yaw)

            # --- desvio antecipado: algo novo na rota mais a frente -> replaneja ja
            if v_alvo > 0 and agora - ultimo_olhar > 0.5 and agora - ultimo_replan > 1.5:
                ultimo_olhar = agora
                novos = self.pontos_novos(pts, 3.0)
                ameaca = self.rota_ameacada(rota, i, x, y, novos) if novos else None
                if ameaca:
                    self.plan.esquecer_vencidos(agora)
                    self.limpar_marcas_vistas(x, y, yaw)
                    self.plan.marcar(novos, agora, self.validade)
                    ultimo_replan = agora
                    nova = self.planejar(x, y, gx, gy)
                    if nova:
                        rospy.loginfo("Obstaculo novo na rota em (%.2f, %.2f): desviando.", *ameaca)
                        rota, i, desviando = nova, 0, True
                        self.set_estado("desviando")
                        continue

            # --- seguranca: obstaculo perto no caminho -> desacelera ou para
            obst = self.obstaculo_no_caminho(rota, i, x, y, pts, restante) if v_alvo > 0 else None
            perto = self.colado(pts)
            parar = obst is not None and obst < (self.d_parada + (0.1 if bloqueado_desde else 0.0))
            if v_alvo == 0 and perto < self.d_re:
                parar = True  # girar no lugar com alguem encostado pode bater: espera ou da re
            if parar:
                if bloqueado_desde is None:
                    bloqueado_desde = agora
                    rospy.logwarn("Obstaculo a %.2f m no caminho: parando.",
                                  obst if obst is not None else max(0.0, perto - self.frente))
                    self.set_estado("obstaculo")
                self.comandar(0.0, 0.0, dt, freio=self.freio_forte)
                # algo colado no robo: re curta para ganhar espaco (no maximo 4 vezes por destino)
                if perto < self.d_re and agora - bloqueado_desde > 1.0 and agora - ultima_re > 3.0 and res < 4:
                    res += 1
                    recuou = self.dar_re(taxa, dt)
                    ultima_re = rospy.get_time()
                    if recuou > 0:
                        # depois da re, ja tenta outro caminho
                        bloqueado_desde, ultimo_replan = ultima_re - self.espera, 0.0
                        self.set_estado("obstaculo")
                    continue
                if agora - bloqueado_desde > self.espera and agora - ultimo_replan > 2.0:
                    ultimo_replan = agora
                    self.plan.esquecer_vencidos(agora)
                    self.limpar_marcas_vistas(x, y, yaw)
                    self.plan.marcar(self.pontos_novos(pts), agora, self.validade)
                    nova = self.planejar(x, y, gx, gy)
                    if nova:
                        rospy.loginfo("Obstaculo continua no caminho: desviando por outra rota.")
                        rota, i, desviando, bloqueado_desde = nova, 0, True, None
                        self.set_estado("desviando")
                    else:
                        if self.estado != "sem_caminho":
                            rospy.logwarn("Sem outro caminho por enquanto; esperando o obstaculo sair.")
                        self.set_estado("sem_caminho")
                taxa.sleep()
                continue

            if bloqueado_desde is not None:
                rospy.loginfo("Caminho livre de novo: seguindo.")
                bloqueado_desde = None
            self.set_estado("desviando" if desviando else "andando")
            if obst is not None and obst < self.d_reduzir:
                f = (obst - self.d_parada) / max(self.d_reduzir - self.d_parada, 1e-3)
                v_alvo *= max(0.3, min(1.0, f))
            self.comandar(v_alvo, w_alvo, dt)

            # --- travou sem motivo? replaneja
            if restante < progresso_d - 0.1:
                progresso_t, progresso_d = agora, restante
            elif agora - progresso_t > 20.0 and agora - ultimo_replan > 5.0:
                rospy.logwarn("Sem progresso ha 20 s: replanejando.")
                ultimo_replan = progresso_t = agora
                rota = self.planejar(x, y, gx, gy) or rota
                i = 0
            taxa.sleep()

        # chegou: para e vira para a mesa/bancada
        while abs(self.v) > 0.01 and not rospy.is_shutdown():
            self.comandar(0.0, 0.0, dt)
            taxa.sleep()
        if gyaw is not None:
            fim_giro = rospy.get_time() + 15.0
            while not rospy.is_shutdown() and rospy.get_time() < fim_giro:
                if self.server.is_preempt_requested():
                    self.parar_ja()
                    return None
                with self.lock:
                    yaw = self.pose[2]
                erro = normalizar(gyaw - yaw)
                if abs(erro) < self.tolerancia_giro:
                    break
                w = limitar(2.0 * erro, 0.8)
                if abs(w) < 0.15:
                    w = math.copysign(0.15, w)
                self.comandar(0.0, w, dt)
                taxa.sleep()
        self.parar_ja()
        rospy.loginfo("Cheguei em %s.", nome)
        return True


def main():
    rospy.init_node("navigation")
    modo = rospy.get_param("~modo", "simulada")
    if modo == "real":
        nav = NavegacaoReal()
    else:
        nav = NavegacaoSimulada()
    rospy.on_shutdown(lambda: getattr(nav, "parar_ja", lambda: None)())
    rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
