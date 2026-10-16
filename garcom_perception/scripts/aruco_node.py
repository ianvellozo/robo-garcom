#!/usr/bin/env python3
"""Percepção - ESQUELETO (responsável: Mariana).

Simula a câmera: quando o robô chega a uma estação (/garcom/robot_at),
publica em /garcom/station_detected o nome da estação, como se tivesse
lido o marcador ArUco dela.

TODO(Mariana): trocar pela detecção real (usb_cam + OpenCV/ArUco),
convertendo o ID do marcador lido no nome da estação (config/marcadores.yaml).
"""
import rospy
from std_msgs.msg import String


def main():
    rospy.init_node("perception")
    delay = rospy.get_param("~detection_delay_s", 1.0)
    pub = rospy.Publisher("/garcom/station_detected", String, queue_size=10)

    def on_robot_at(msg):
        if msg.data.startswith("estacao_"):
            rospy.sleep(delay)  # tempo para a camera "ler" o marcador
            rospy.loginfo("ArUco detectado (simulado): %s", msg.data)
            pub.publish(String(data=msg.data))

    rospy.Subscriber("/garcom/robot_at", String, on_robot_at)
    rospy.loginfo("Percepção (simulada) pronta.")
    rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
