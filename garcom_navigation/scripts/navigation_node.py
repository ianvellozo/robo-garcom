#!/usr/bin/env python3
"""Navegação - ESQUELETO (responsável: Ana).

Servidor da ação /garcom/go_to_point: simula a ida até um ponto cadastrado
em config/pontos.yaml (/garcom/points) e, ao chegar, publica o nome do ponto
em /garcom/robot_at.

Este nó NÃO move o robô; ele só finge a viagem para os outros módulos
poderem ser testados. O tempo da viagem fingida é a distância em linha reta
dividida pela velocidade /garcom/robot_speed_mps.

TODO(Ana): substituir pela navegação real (mapa + AMCL + A* + controle),
publicando os comandos de velocidade no tópico ~cmd_vel_topic
(/cmd_vel no Gazebo, /RosAria/cmd_vel no P3-DX real).
"""
import math

import actionlib
import rospy
from std_msgs.msg import String
from garcom_msgs.msg import GoToPointAction, GoToPointFeedback, GoToPointResult


class NavigationStub:
    def __init__(self):
        self.points = rospy.get_param("/garcom/points", {})
        self.speed = float(rospy.get_param("/garcom/robot_speed_mps", 1.5))
        self.cmd_vel_topic = rospy.get_param("~cmd_vel_topic", "/cmd_vel")
        self.here = "base"

        self.at_pub = rospy.Publisher("/garcom/robot_at", String, queue_size=10, latch=True)
        self.server = actionlib.SimpleActionServer(
            "/garcom/go_to_point", GoToPointAction, execute_cb=self.execute, auto_start=False)
        self.server.start()
        rospy.loginfo("Navegação (simulada) pronta: %d pontos, %.1f m/s.", len(self.points), self.speed)
        rospy.loginfo("Tópico de velocidade configurado: %s", self.cmd_vel_topic)

    def distance(self, a, b):
        pa, pb = self.points[a], self.points[b]
        return math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])

    def execute(self, goal):
        if goal.point_name not in self.points:
            rospy.logerr("Ponto desconhecido: %s", goal.point_name)
            self.server.set_aborted(GoToPointResult(success=False))
            return

        dist = self.distance(self.here, goal.point_name)
        duration = max(0.5, dist / self.speed)
        rospy.loginfo("Indo para %s: %.1f m, %.1f s (simulado)", goal.point_name, dist, duration)
        steps = 10
        feedback = GoToPointFeedback()
        for i in range(steps):
            if self.server.is_preempt_requested() or rospy.is_shutdown():
                self.server.set_preempted(GoToPointResult(success=False))
                return
            feedback.distance_remaining = dist * (steps - i) / steps
            self.server.publish_feedback(feedback)
            rospy.sleep(duration / steps)

        self.here = goal.point_name
        self.at_pub.publish(String(data=goal.point_name))
        self.server.set_succeeded(GoToPointResult(success=True))


def main():
    rospy.init_node("navigation")
    NavigationStub()
    rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
