#!/usr/bin/env python3
"""Gerenciador de missões (responsável: Ian) - versão 19/10.

Pede à fila o próximo pedido (/garcom/next_order) e executa a missão:
  1. vai até a estação de cada item (ação /garcom/go_to_point);
  2. espera a confirmação do ArUco (/garcom/station_detected);
  3. leva o pedido até a mesa e volta para a base.

O estado do pedido é publicado em /garcom/order_status.
Nesta versão a navegação e a percepção ainda são simuladas pelos nós-esqueleto.
"""
import copy

import actionlib
import rospy
from std_msgs.msg import String
from garcom_msgs.msg import OrderStatus, GoToPointAction, GoToPointGoal
from garcom_msgs.srv import NextOrder


class QuietActionClient(actionlib.SimpleActionClient):
    """SimpleActionClient sem o falso erro "transition callback on a goal handle that we're not tracking".

    Quando o servidor responde muito rápido, a primeira transição do novo destino
    pode chegar antes de o actionlib registrar esse destino. Ela é ignorada e as
    transições seguintes chegam normalmente.
    """

    def _handle_transition(self, gh):
        if gh != self.gh:
            return
        super()._handle_transition(gh)


class MissionManager:
    def __init__(self):
        self.stations = rospy.get_param("~stations", {"cafe": "estacao_cafe",
                                                      "croissant": "estacao_croissant"})
        self.base = rospy.get_param("~base", "base")
        self.marker_timeout = rospy.get_param("~marker_timeout_s", 10.0)
        self.warning_ratio = float(rospy.get_param("/garcom/warning_ratio", 0.7))
        self.last_station_seen = ""

        self.status_pub = rospy.Publisher("/garcom/order_status", OrderStatus, queue_size=10)
        rospy.Subscriber("/garcom/station_detected", String, self.on_station)

        self.nav = QuietActionClient("/garcom/go_to_point", GoToPointAction)
        rospy.loginfo("Aguardando o servidor de navegação...")
        self.nav.wait_for_server()

        rospy.loginfo("Aguardando a fila de pedidos...")
        rospy.wait_for_service("/garcom/next_order")
        self.next_order = rospy.ServiceProxy("/garcom/next_order", NextOrder)
        rospy.loginfo("Gerenciador de missões pronto.")

    def on_station(self, msg):
        self.last_station_seen = msg.data

    def update(self, order, status):
        msg = copy.deepcopy(order)
        msg.status = status
        # recalcula o alerta/atraso na hora de publicar
        elapsed = (rospy.Time.now() - msg.stamp).to_sec()
        msg.late = elapsed > msg.deadline_s
        msg.warning = msg.late or elapsed >= self.warning_ratio * msg.deadline_s
        self.status_pub.publish(msg)

    def go_to(self, point):
        self.nav.send_goal(GoToPointGoal(point_name=point))
        self.nav.wait_for_result()
        result = self.nav.get_result()
        return bool(result and result.success)

    def wait_for_marker(self, station):
        deadline = rospy.Time.now() + rospy.Duration(self.marker_timeout)
        rate = rospy.Rate(10)
        while not rospy.is_shutdown() and rospy.Time.now() < deadline:
            if self.last_station_seen == station:
                return True
            rate.sleep()
        return False

    def execute(self, order):
        rospy.loginfo("Missão do pedido %d (mesa %d) iniciada", order.id, order.table_id)
        self.update(order, OrderStatus.EM_COLETA)

        for item in order.items:
            station = self.stations.get(item)
            if station is None:
                rospy.logwarn("Item '%s' sem estação cadastrada; ignorado", item)
                continue
            self.last_station_seen = ""
            if not self.go_to(station):
                rospy.logerr("Não foi possível chegar em %s", station)
                continue  # TODO(Ian, 23/11): tratamento de falhas
            if self.wait_for_marker(station):
                rospy.loginfo("Coleta de '%s' confirmada pelo ArUco em %s", item, station)
            else:
                rospy.logwarn("ArUco de %s não detectado em %.0f s", station, self.marker_timeout)

        self.update(order, OrderStatus.EM_ENTREGA)
        table = "mesa_%d" % order.table_id
        if self.go_to(table):
            self.update(order, OrderStatus.ENTREGUE)
            rospy.loginfo("Pedido %d entregue na %s", order.id, table)
        self.go_to(self.base)

    def run(self):
        rate = rospy.Rate(1.0)
        while not rospy.is_shutdown():
            try:
                resp = self.next_order()
            except rospy.ServiceException as err:
                rospy.logwarn("Fila indisponível: %s", err)
                rate.sleep()
                continue
            if resp.has_order:
                self.execute(resp.order)
            else:
                rate.sleep()


def main():
    rospy.init_node("mission_manager")
    MissionManager().run()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
