#!/usr/bin/env python3
"""Simulador 2D leve do P3-DX no restaurante (sem Gazebo).

Faz o papel do Gazebo quando o computador e fraco ou para testar rapido:
  - recebe /cmd_vel e move o robo (tracao diferencial, com aceleracao limitada);
  - publica /odom (posicao do robo) e /scan (laser batendo nos moveis da planta);
  - publica /joint_states e a TF odom -> base_link, para o RViz desenhar o robo.

Clientes em pe (obstaculos) entram e saem pelo topico /garcom/sim/obstaculo:
  "x y" coloca um cliente nessa posicao; "limpar" tira todos.
O obstaculo.py faz isso por voce.

Se o robo encostar em alguma coisa, ele nao atravessa e o terminal avisa BATIDA.
"""
import math
import os
import sys
import threading

import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState, LaserScan
from std_msgs.msg import String

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import restaurante  # noqa: E402

try:
    import tf2_ros
    from geometry_msgs.msg import TransformStamped
except ImportError:  # sem tf2 o simulador funciona, so o RViz nao desenha o robo
    tf2_ros = None

RAIO_RODA = 0.0975


class Simulador:
    def __init__(self):
        self.planta = restaurante.carregar()
        base = rospy.get_param("/garcom/points", {}).get("base", {"x": 0.0, "y": 0.0, "yaw": 0.0})
        self.x = float(rospy.get_param("~x", base["x"]))
        self.y = float(rospy.get_param("~y", base["y"]))
        self.yaw = float(rospy.get_param("~yaw", base.get("yaw", 0.0)))
        self.raio_robo = float(rospy.get_param("~raio_robo", 0.22))
        self.raio_cliente = float(rospy.get_param("~raio_cliente", 0.22))
        self.laser_x = float(rospy.get_param("~laser_x", 0.15))
        self.n_raios = int(rospy.get_param("~raios", 181))
        self.alcance = float(rospy.get_param("~alcance_laser", 8.0))
        self.acel = float(rospy.get_param("~aceleracao_max", 1.0))
        self.acel_giro = float(rospy.get_param("~aceleracao_giro_max", 3.0))

        self.lock = threading.Lock()
        self.v = self.w = 0.0
        self.cmd = (0.0, 0.0)
        self.ultimo_cmd = rospy.get_time()
        self.clientes = []
        self.batidas = 0
        self.rodas = [0.0, 0.0]

        self.odom_pub = rospy.Publisher("/odom", Odometry, queue_size=5)
        self.scan_pub = rospy.Publisher("/scan", LaserScan, queue_size=2)
        self.joint_pub = rospy.Publisher("/joint_states", JointState, queue_size=5)
        self.tf = tf2_ros.TransformBroadcaster() if tf2_ros else None
        rospy.Subscriber("/cmd_vel", Twist, self.on_cmd, queue_size=1)
        rospy.Subscriber("/garcom/sim/obstaculo", String, self.on_obstaculo, queue_size=10)

        rospy.Timer(rospy.Duration(0.02), self.passo)        # 50 Hz
        rospy.Timer(rospy.Duration(0.1), self.publicar_laser)  # 10 Hz, como o laser do Gazebo
        rospy.loginfo("Simulador 2D pronto: robo em (%.1f, %.1f), %d moveis no salao.",
                      self.x, self.y, len(self.planta.moveis))

    def on_cmd(self, msg):
        with self.lock:
            self.cmd = (msg.linear.x, msg.angular.z)
            self.ultimo_cmd = rospy.get_time()

    def on_obstaculo(self, msg):
        texto = msg.data.strip().lower()
        with self.lock:
            if texto in ("limpar", "tirar"):
                self.clientes = []
                rospy.loginfo("Clientes retirados do salao.")
                return
            try:
                x, y = (float(v) for v in texto.replace(",", " ").split()[:2])
            except ValueError:
                rospy.logwarn("Obstaculo invalido: '%s' (use 'x y' ou 'limpar')", msg.data)
                return
            nome = "cliente_%d" % (len(self.clientes) + 1)
            self.clientes.append(restaurante.Cilindro(nome, x, y, self.raio_cliente, 1.6, tipo="cliente"))
        rospy.loginfo("Cliente em pe em (%.2f, %.2f).", x, y)

    def bate(self, x, y):
        if self.planta.ocupado(x, y, self.raio_robo):
            return True
        return any(c.contem(x, y, self.raio_robo) for c in self.clientes)

    def passo(self, evento):
        try:
            self._passo()
        except rospy.ROSException:
            pass  # o ROS esta desligando

    def _passo(self):
        dt = 0.02
        with self.lock:
            v_alvo, w_alvo = self.cmd
            if rospy.get_time() - self.ultimo_cmd > 0.5:
                v_alvo = w_alvo = 0.0  # sem comando: o robo para (como o RosAria)
            self.v += max(-self.acel * dt, min(self.acel * dt, v_alvo - self.v))
            self.w += max(-self.acel_giro * dt, min(self.acel_giro * dt, w_alvo - self.w))
            nx = self.x + self.v * math.cos(self.yaw) * dt
            ny = self.y + self.v * math.sin(self.yaw) * dt
            if abs(self.v) > 1e-4 and self.bate(nx, ny) and not self.bate(self.x, self.y):
                self.batidas += 1
                if self.batidas % 25 == 1:
                    rospy.logwarn("BATIDA! O robo encostou em algo em (%.2f, %.2f).", nx, ny)
                self.v = 0.0
            else:
                self.x, self.y = nx, ny
            self.yaw = math.atan2(math.sin(self.yaw + self.w * dt), math.cos(self.yaw + self.w * dt))
            meia = 0.165
            self.rodas[0] += (self.v - self.w * meia) / RAIO_RODA * dt
            self.rodas[1] += (self.v + self.w * meia) / RAIO_RODA * dt
            x, y, yaw, v, w = self.x, self.y, self.yaw, self.v, self.w
            rodas = list(self.rodas)

        agora = rospy.Time.now()
        odom = Odometry()
        odom.header.stamp = agora
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_link"
        odom.pose.pose.position.x, odom.pose.pose.position.y = x, y
        odom.pose.pose.orientation.z = math.sin(yaw / 2)
        odom.pose.pose.orientation.w = math.cos(yaw / 2)
        odom.twist.twist.linear.x, odom.twist.twist.angular.z = v, w
        self.odom_pub.publish(odom)

        js = JointState()
        js.header.stamp = agora
        js.name = ["right_wheel_joint", "left_wheel_joint"]
        js.position = rodas
        self.joint_pub.publish(js)

        if self.tf:
            t = TransformStamped()
            t.header.stamp = agora
            t.header.frame_id = "odom"
            t.child_frame_id = "base_link"
            t.transform.translation.x, t.transform.translation.y = x, y
            t.transform.rotation = odom.pose.pose.orientation
            self.tf.sendTransform(t)

    def publicar_laser(self, evento):
        try:
            self._publicar_laser()
        except rospy.ROSException:
            pass  # o ROS esta desligando

    def _publicar_laser(self):
        with self.lock:
            x, y, yaw = self.x, self.y, self.yaw
            clientes = list(self.clientes)
        lx = x + self.laser_x * math.cos(yaw)
        ly = y + self.laser_x * math.sin(yaw)
        moveis = self.planta.mesas + self.planta.cadeiras + self.planta.bancadas + clientes
        perto = self.planta.paredes + [m for m in moveis if math.hypot(m.x - lx, m.y - ly) < self.alcance + 1.5]
        scan = LaserScan()
        scan.header.stamp = rospy.Time.now()
        scan.header.frame_id = "laser_link"
        scan.angle_min, scan.angle_max = -math.pi / 2, math.pi / 2
        scan.angle_increment = math.pi / (self.n_raios - 1)
        scan.scan_time = 0.1
        scan.range_min, scan.range_max = 0.10, self.alcance
        ranges = []
        for k in range(self.n_raios):
            ang = yaw + scan.angle_min + k * scan.angle_increment
            dx, dy = math.cos(ang), math.sin(ang)
            melhor = math.inf
            for m in perto:
                t = m.raio(lx, ly, dx, dy)
                if t is not None and t < melhor:
                    melhor = t
            ranges.append(melhor if melhor <= self.alcance else math.inf)
        scan.ranges = ranges
        self.scan_pub.publish(scan)


def main():
    rospy.init_node("simulador_2d")
    Simulador()
    rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
