#!/usr/bin/env python3
"""Tela da bancada no terminal (responsável: Ian) - versão 21/10.

Versão de terminal da tela da bancada (a do navegador é o web_server.py).
Quando o robô chega numa bancada, a missão publica em /garcom/pickup_request
o total de itens da viagem e a divisão por mesa. Esta tela mostra a lista e
confirma a coleta em /garcom/pickup_done.

Dois modos (parâmetro ~mode):
- manual (padrão): mostra os itens e espera a pessoa apertar ENTER.
    rosrun garcom_interface station_panel.py
- auto: confirma sozinha depois de ~auto_delay_s segundos (usado no sim.launch).
"""
import queue

import rospy
from garcom_msgs.msg import PickupDone, PickupRequest


class StationPanel:
    def __init__(self):
        cardapio = rospy.get_param("/garcom/cardapio", [])
        self.names = {entry["item"]: entry["nome"] for entry in cardapio}
        self.stations = rospy.get_param("/garcom/estacoes", {})
        self.mode = rospy.get_param("~mode", "manual")
        self.delay = float(rospy.get_param("~auto_delay_s", 2.0))
        self.requests = queue.Queue()

        self.pub = rospy.Publisher("/garcom/pickup_done", PickupDone, queue_size=10)
        rospy.Subscriber("/garcom/pickup_request", PickupRequest, self.requests.put)
        rospy.loginfo("Tela da bancada pronta (modo %s).", self.mode)

    def describe(self, items, quantities):
        return ", ".join("%d x %s" % (q, self.names.get(i, i)) for i, q in zip(items, quantities))

    def show(self, req):
        print("\n************ %s - viagem %d ************" % (self.stations.get(req.station, req.station), req.trip_id))
        print("Coloque na bandeja:")
        for item, qty in zip(req.items, req.quantities):
            print("   %d x %s" % (qty, self.names.get(item, item)))
        if len(req.lines) > 1:
            print("Separado por mesa:")
            for line in req.lines:
                print("   Mesa %d (pedido %d): %s" % (line.table_id, line.order_id,
                                                      self.describe(line.items, line.quantities)))

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
            self.pub.publish(PickupDone(trip_id=req.trip_id, station=req.station))
            rospy.loginfo("Coleta confirmada: viagem %d em %s", req.trip_id, req.station)


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
