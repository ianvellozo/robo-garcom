#!/usr/bin/env python3
"""Tela da estação de coleta (responsável: Ian) - versão 19/10.

Substitui a leitura de ArUco. Quando o robô chega numa estação, a missão
publica em /garcom/pickup_request o que colocar na bandeja. Esta tela mostra
a lista e confirma a coleta em /garcom/pickup_done.

Dois modos (parâmetro ~mode):
- manual (padrão): mostra os itens e espera a pessoa apertar ENTER.
    rosrun garcom_interface station_panel.py
- auto: confirma sozinha depois de ~auto_delay_s segundos (usado no sim.launch).
Futuro: versão web num tablet ou TV na estação.
"""
import queue

import rospy
from garcom_msgs.msg import PickupDone, PickupRequest


class StationPanel:
    def __init__(self):
        cardapio = rospy.get_param("/garcom/cardapio", [])
        self.names = {entry["item"]: entry["nome"] for entry in cardapio}
        self.mode = rospy.get_param("~mode", "manual")
        self.delay = float(rospy.get_param("~auto_delay_s", 2.0))
        self.requests = queue.Queue()

        self.pub = rospy.Publisher("/garcom/pickup_done", PickupDone, queue_size=10)
        rospy.Subscriber("/garcom/pickup_request", PickupRequest, self.requests.put)
        rospy.loginfo("Tela da estação pronta (modo %s).", self.mode)

    def show(self, req):
        station = req.station.replace("estacao_", "").replace("_", " ").upper()
        print("\n************ ESTAÇÃO %s ************" % station)
        print("Pedido %d - mesa %d. Coloque na bandeja:" % (req.order_id, req.table_id))
        for item, qty in zip(req.items, req.quantities):
            print("   %d x %s" % (qty, self.names.get(item, item)))

    def run(self):
        while not rospy.is_shutdown():
            try:
                req = self.requests.get(timeout=0.5)
            except queue.Empty:
                continue
            if self.mode == "auto":
                rospy.sleep(self.delay)
            else:
                self.show(req)
                input("Aperte ENTER quando a bandeja estiver pronta... ")
            self.pub.publish(PickupDone(order_id=req.order_id, station=req.station))
            rospy.loginfo("Coleta confirmada: pedido %d em %s", req.order_id, req.station)


def main():
    rospy.init_node("station_panel")
    try:
        StationPanel().run()
    except (KeyboardInterrupt, EOFError):
        print()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
