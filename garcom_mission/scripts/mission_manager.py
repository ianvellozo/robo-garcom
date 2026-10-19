#!/usr/bin/env python3
"""Gerenciador de missões (responsável: Ian) - versão 19/10.

Pede à fila o próximo pedido (/garcom/next_order) e executa a missão:
  1. separa os itens por estação de coleta (cardápio em /garcom/cardapio);
  2. vai até cada estação (ação /garcom/go_to_point);
  3. na estação, publica o que colocar na bandeja (/garcom/pickup_request) e
     espera a confirmação da tela da estação (/garcom/pickup_done);
  4. leva o pedido até a mesa e volta para a base.

O estado do pedido é publicado em /garcom/order_status.
"""
import copy
import threading
from collections import Counter, OrderedDict

import actionlib
import rospy
from garcom_msgs.msg import (GoToPointAction, GoToPointGoal, OrderStatus,
                             PickupDone, PickupRequest)
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
        cardapio = rospy.get_param("/garcom/cardapio", [])
        self.station_of = {entry["item"]: entry["estacao"] for entry in cardapio}
        self.base = rospy.get_param("~base", "base")
        self.pickup_timeout = float(rospy.get_param("~pickup_timeout_s", 60.0))
        self.warning_ratio = float(rospy.get_param("/garcom/warning_ratio", 0.7))

        self.confirmed = set()   # (order_id, estação) já confirmados pela tela da estação
        self.confirm_lock = threading.Condition()

        self.status_pub = rospy.Publisher("/garcom/order_status", OrderStatus, queue_size=10)
        self.pickup_pub = rospy.Publisher("/garcom/pickup_request", PickupRequest, queue_size=10)
        rospy.Subscriber("/garcom/pickup_done", PickupDone, self.on_pickup_done)

        self.nav = QuietActionClient("/garcom/go_to_point", GoToPointAction)
        rospy.loginfo("Aguardando o servidor de navegação...")
        self.nav.wait_for_server()

        rospy.loginfo("Aguardando a fila de pedidos...")
        rospy.wait_for_service("/garcom/next_order")
        self.next_order = rospy.ServiceProxy("/garcom/next_order", NextOrder)
        rospy.loginfo("Gerenciador de missões pronto.")

    # ------------------------------------------------------------ apoio
    def on_pickup_done(self, msg):
        with self.confirm_lock:
            self.confirmed.add((msg.order_id, msg.station))
            self.confirm_lock.notify_all()

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

    def plan_stops(self, items):
        """Agrupa os itens por estação, na ordem em que aparecem: {estação: Counter(item: qtd)}."""
        stops = OrderedDict()
        for item in items:
            station = self.station_of.get(item)
            if station is None:
                rospy.logwarn("Item '%s' não está no cardápio; ignorado", item)
                continue
            stops.setdefault(station, Counter())[item] += 1
        return stops

    def collect(self, order, station, counts):
        """Pede a coleta na estação e espera a confirmação."""
        key = (order.id, station)
        req = PickupRequest(order_id=order.id, table_id=order.table_id, station=station,
                            items=list(counts.keys()), quantities=list(counts.values()))
        self.pickup_pub.publish(req)

        deadline = rospy.Time.now() + rospy.Duration(self.pickup_timeout)
        with self.confirm_lock:
            while key not in self.confirmed and not rospy.is_shutdown():
                left = (deadline - rospy.Time.now()).to_sec()
                if left <= 0:
                    break
                self.confirm_lock.wait(min(left, 0.5))
            ok = key in self.confirmed
            self.confirmed.discard(key)
        return ok

    # ----------------------------------------------------------- missão
    def execute(self, order):
        rospy.loginfo("Missão do pedido %d (mesa %d) iniciada", order.id, order.table_id)
        self.update(order, OrderStatus.EM_COLETA)

        for station, counts in self.plan_stops(order.items).items():
            if not self.go_to(station):
                rospy.logerr("Não foi possível chegar em %s", station)
                continue  # TODO(Ian, 23/11): tratamento de falhas
            text = ", ".join("%dx %s" % (q, i) for i, q in counts.items())
            if self.collect(order, station, counts):
                rospy.loginfo("Coleta confirmada em %s: %s", station, text)
            else:
                rospy.logwarn("Coleta em %s não confirmada em %.0f s; seguindo assim mesmo",
                              station, self.pickup_timeout)

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
