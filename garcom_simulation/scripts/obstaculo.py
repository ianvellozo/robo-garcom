#!/usr/bin/env python3
"""Coloca um cliente em pe no caminho do robo, para testar a parada e o desvio.

  rosrun garcom_simulation obstaculo.py              na rota do robo, 1,5 m a frente dele
  rosrun garcom_simulation obstaculo.py frente 0.8   na rota do robo, 0,8 m a frente (para ele frear)
  rosrun garcom_simulation obstaculo.py 5 0          na posicao x = 5, y = 0 (metros)
  rosrun garcom_simulation obstaculo.py tirar        tira todos os clientes

O cliente vai embora sozinho depois de 15 s, como uma pessoa de verdade.
Para mudar o tempo, acrescente "tempo N" (em segundos; "tempo 0" = fica ate tirar):
  rosrun garcom_simulation obstaculo.py tempo 30
  rosrun garcom_simulation obstaculo.py 5 0 tempo 0
Ctrl+C antes do tempo: o cliente sai na hora.

Funciona no Gazebo (cria um boneco no mundo) e no simulador 2D.
"""
import math
import sys
import time

import rospy
from nav_msgs.msg import Odometry, Path
from std_msgs.msg import String

TEMPO_PADRAO = 15.0
SDF_CLIENTE = """<?xml version="1.0"?>
<sdf version="1.6">
  <model name="cliente">
    <static>true</static>
    <link name="link">
      <collision name="corpo">
        <pose>0 0 0.6 0 0 0</pose>
        <geometry><cylinder><radius>0.22</radius><length>1.2</length></cylinder></geometry>
      </collision>
      <visual name="corpo">
        <pose>0 0 0.6 0 0 0</pose>
        <geometry><cylinder><radius>0.22</radius><length>1.2</length></cylinder></geometry>
        <material><ambient>0.2 0.35 0.7 1</ambient><diffuse>0.2 0.35 0.7 1</diffuse></material>
      </visual>
      <visual name="cabeca">
        <pose>0 0 1.36 0 0 0</pose>
        <geometry><sphere><radius>0.14</radius></sphere></geometry>
        <material><ambient>0.87 0.68 0.52 1</ambient><diffuse>0.87 0.68 0.52 1</diffuse></material>
      </visual>
    </link>
  </model>
</sdf>"""


def pose_robo():
    try:
        odom = rospy.wait_for_message("/odom", Odometry, timeout=3.0)
    except rospy.ROSException:
        return None
    q = odom.pose.pose.orientation
    yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
    return odom.pose.pose.position.x, odom.pose.pose.position.y, yaw


def ponto_na_rota(distancia=1.5):
    """Ponto da rota atual a `distancia` metros a frente do robo (ou na frente dele).

    Se a rota faz curva e o ponto cairia perto demais do robo, anda mais pela rota:
    o cliente nunca aparece encostado nele."""
    pose = pose_robo()
    if pose is None:
        return None
    x, y, yaw = pose
    minimo = min(0.7, 0.8 * distancia)  # do centro do robo ao centro do cliente
    try:
        rota = [(p.pose.position.x, p.pose.position.y)
                for p in rospy.wait_for_message("/garcom/path", Path, timeout=2.0).poses]
    except rospy.ROSException:
        rota = []
    if len(rota) >= 2:
        i = min(range(len(rota) - 1), key=lambda k: math.hypot(rota[k][0] - x, rota[k][1] - y)
                + math.hypot(rota[k + 1][0] - x, rota[k + 1][1] - y))
        trecho = [(x, y)] + rota[i + 1:]
        andado = 0.0
        for (ax, ay), (bx, by) in zip(trecho, trecho[1:]):
            d = math.hypot(bx - ax, by - ay)
            n = max(1, int(d / 0.05))
            for k in range(1, n + 1):
                px, py = ax + (bx - ax) * k / n, ay + (by - ay) * k / n
                if andado + d * k / n >= distancia and math.hypot(px - x, py - y) >= minimo:
                    return px, py
            andado += d
        if math.hypot(trecho[-1][0] - x, trecho[-1][1] - y) >= minimo:
            return trecho[-1]
    return x + distancia * math.cos(yaw), y + distancia * math.sin(yaw)


def tem_gazebo():
    try:
        rospy.wait_for_service("/gazebo/spawn_sdf_model", timeout=1.5)
        return True
    except rospy.ROSException:
        return False


class Clientes:
    """Poe e tira clientes no Gazebo ou no simulador 2D."""

    def __init__(self):
        self.gazebo = tem_gazebo()
        self.pub = None if self.gazebo else rospy.Publisher(
            "/garcom/sim/obstaculo", String, queue_size=5, latch=True)

    def por(self, nome, x, y):
        if self.gazebo:
            from gazebo_msgs.srv import SpawnModel
            from geometry_msgs.msg import Pose
            pose = Pose()
            pose.position.x, pose.position.y = x, y
            pose.orientation.w = 1.0
            rospy.ServiceProxy("/gazebo/spawn_sdf_model", SpawnModel)(nome, SDF_CLIENTE, "", pose, "world")
        else:
            self.pub.publish(String(data="%.3f %.3f %s" % (x, y, nome)))
            time.sleep(1.0)

    def tirar(self, nome=None):
        if self.gazebo:
            from gazebo_msgs.srv import DeleteModel, GetWorldProperties
            apagar = rospy.ServiceProxy("/gazebo/delete_model", DeleteModel)
            if nome:
                apagar(nome)
            else:
                for n in rospy.ServiceProxy("/gazebo/get_world_properties", GetWorldProperties)().model_names:
                    if n.startswith("cliente_"):
                        apagar(n)
        else:
            self.pub.publish(String(data="tirar %s" % nome if nome else "limpar"))
            time.sleep(1.0)


def main():
    # disable_signals: o Ctrl+C fica com a gente, para tirar o cliente antes de sair
    rospy.init_node("obstaculo", anonymous=True, disable_signals=True)
    args = [a.lower() for a in rospy.myargv(sys.argv)[1:]]
    tempo = TEMPO_PADRAO
    if "tempo" in args:
        k = args.index("tempo")
        tempo = float(args[k + 1]) if k + 1 < len(args) else TEMPO_PADRAO
        del args[k:k + 2]
    clientes = Clientes()

    if args and args[0] in ("tirar", "limpar"):
        clientes.tirar()
        print("Clientes retirados.")
        return

    if len(args) >= 2 and args[0] != "frente":
        x, y = float(args[0]), float(args[1])
    else:
        distancia = float(args[1]) if len(args) >= 2 else 1.5
        ponto = ponto_na_rota(distancia)
        if ponto is None:
            print("Nao achei o robo (/odom). O Gazebo ou o simulador 2D esta rodando?")
            return
        x, y = ponto

    nome = "cliente_%d" % (int(time.time() * 10) % 100000)
    clientes.por(nome, x, y)
    if tempo <= 0:
        print("Cliente em pe em x = %.2f, y = %.2f. Ele fica ate voce rodar: obstaculo.py tirar" % (x, y))
        return
    print("Cliente em pe em x = %.2f, y = %.2f. Ele vai embora em %.0f s (Ctrl+C: sai agora)." % (x, y, tempo))
    try:
        time.sleep(tempo)
    except KeyboardInterrupt:
        pass
    clientes.tirar(nome)
    print("O cliente foi embora.")


if __name__ == "__main__":
    main()
