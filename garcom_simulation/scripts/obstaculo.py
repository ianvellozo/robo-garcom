#!/usr/bin/env python3
"""Coloca um cliente em pe no caminho do robo, para testar a parada e o desvio.

  rosrun garcom_simulation obstaculo.py            na rota do robo, 1,5 m a frente dele
  rosrun garcom_simulation obstaculo.py frente 0.8 na rota do robo, 0,8 m a frente (para ele frear)
  rosrun garcom_simulation obstaculo.py 5 0        na posicao x = 5, y = 0 (metros)
  rosrun garcom_simulation obstaculo.py tirar      tira todos os clientes

Funciona no Gazebo (cria um boneco no mundo) e no simulador 2D.
"""
import math
import sys
import time

import rospy
from nav_msgs.msg import Odometry, Path
from std_msgs.msg import String

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


def ponto_na_rota(distancia=1.5):
    """Ponto da rota atual a `distancia` metros a frente do robo (ou na frente dele)."""
    try:
        odom = rospy.wait_for_message("/odom", Odometry, timeout=3.0)
    except rospy.ROSException:
        return None
    x, y = odom.pose.pose.position.x, odom.pose.pose.position.y
    q = odom.pose.pose.orientation
    yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
    try:
        rota = [(p.pose.position.x, p.pose.position.y)
                for p in rospy.wait_for_message("/garcom/path", Path, timeout=2.0).poses]
    except rospy.ROSException:
        rota = []
    if len(rota) >= 2:
        # ponto da rota mais perto do robo, depois anda `distancia` ao longo dela
        i = min(range(len(rota) - 1), key=lambda k: math.hypot(rota[k][0] - x, rota[k][1] - y)
                + math.hypot(rota[k + 1][0] - x, rota[k + 1][1] - y))
        trecho = [(x, y)] + rota[i + 1:]
        resta = distancia
        for (ax, ay), (bx, by) in zip(trecho, trecho[1:]):
            d = math.hypot(bx - ax, by - ay)
            if d >= resta:
                return ax + (bx - ax) * resta / d, ay + (by - ay) * resta / d
            resta -= d
        if math.hypot(trecho[-1][0] - x, trecho[-1][1] - y) > 0.9:
            return trecho[-1]
    return x + distancia * math.cos(yaw), y + distancia * math.sin(yaw)


def tem_gazebo():
    try:
        rospy.wait_for_service("/gazebo/spawn_sdf_model", timeout=1.5)
        return True
    except rospy.ROSException:
        return False


def main():
    rospy.init_node("obstaculo", anonymous=True)
    args = rospy.myargv(sys.argv)[1:]
    gazebo = tem_gazebo()
    pub = None if gazebo else rospy.Publisher("/garcom/sim/obstaculo", String, queue_size=5, latch=True)

    if args and args[0].lower() in ("tirar", "limpar"):
        if gazebo:
            from gazebo_msgs.srv import DeleteModel, GetWorldProperties
            nomes = rospy.ServiceProxy("/gazebo/get_world_properties", GetWorldProperties)().model_names
            apagar = rospy.ServiceProxy("/gazebo/delete_model", DeleteModel)
            for nome in nomes:
                if nome.startswith("cliente_"):
                    apagar(nome)
        else:
            pub.publish(String(data="limpar"))
            rospy.sleep(1.0)
        print("Clientes retirados.")
        return

    if len(args) >= 2 and args[0].lower() != "frente":
        x, y = float(args[0]), float(args[1])
    else:
        distancia = float(args[1]) if len(args) >= 2 else 1.5
        ponto = ponto_na_rota(distancia)
        if ponto is None:
            print("Nao achei o robo (/odom). O Gazebo ou o simulador 2D esta rodando?")
            return
        x, y = ponto

    if gazebo:
        from gazebo_msgs.srv import SpawnModel
        from geometry_msgs.msg import Pose
        pose = Pose()
        pose.position.x, pose.position.y = x, y
        pose.orientation.w = 1.0
        nome = "cliente_%d" % (int(time.time() * 10) % 100000)
        rospy.ServiceProxy("/gazebo/spawn_sdf_model", SpawnModel)(nome, SDF_CLIENTE, "", pose, "world")
    else:
        pub.publish(String(data="%.3f %.3f" % (x, y)))
        rospy.sleep(1.0)
    print("Cliente em pe em x = %.2f, y = %.2f." % (x, y))


if __name__ == "__main__":
    main()
