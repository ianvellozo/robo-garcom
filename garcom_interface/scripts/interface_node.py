#!/usr/bin/env python3
"""Interface de pedidos das mesas (responsável: Ian) - versão 19/10.

Dois modos (parâmetro ~mode):
- manual (padrão): a pessoa escolhe a mesa e os itens no terminal.
    rosrun garcom_interface interface_node.py
- auto: gera pedidos aleatórios a cada ~period_s segundos (usado nos testes
  e na demonstração; é o modo que o sim.launch usa).

Publica os pedidos em /garcom/orders, mostra o estoque (/garcom/stock) no
cardápio e acompanha o andamento de cada pedido (/garcom/order_status).
Futuro: versão web, para tablet ou celular na mesa.
"""
import math
import random
import re
from collections import Counter

import rospy
from garcom_msgs.msg import Order, OrderStatus, StockLevels

STATUS_NAMES = {
    OrderStatus.RECEBIDO: "recebido",
    OrderStatus.VALIDADO: "validado",
    OrderStatus.EM_COLETA: "em coleta",
    OrderStatus.EM_ENTREGA: "em entrega",
    OrderStatus.ENTREGUE: "entregue",
    OrderStatus.RECUSADO: "recusado (falta item no estoque)",
}


class Interface:
    def __init__(self):
        cardapio = rospy.get_param("/garcom/cardapio", [])
        self.menu = [entry["item"] for entry in cardapio]
        self.names = {entry["item"]: entry["nome"] for entry in cardapio}
        self.tables = int(rospy.get_param("~tables", 4))
        self.stock = {}

        self.pub = rospy.Publisher("/garcom/orders", Order, queue_size=10)
        rospy.Subscriber("/garcom/order_status", OrderStatus, self.on_status)
        rospy.Subscriber("/garcom/stock", StockLevels, self.on_stock)

        rospy.loginfo("Aguardando a fila de pedidos...")
        while self.pub.get_num_connections() == 0 and not rospy.is_shutdown():
            rospy.sleep(0.2)

    # ------------------------------------------------------------ apoio
    def on_stock(self, msg):
        self.stock = dict(zip(msg.items, msg.quantities))

    def on_status(self, msg):
        elapsed = (rospy.Time.now() - msg.stamp).to_sec()
        flag = ""
        if msg.late:
            flag = " - ATRASADO"
        elif msg.warning:
            flag = " - alerta de prazo"
        rospy.loginfo("[mesa %d] pedido %d: %s (%d s de %.0f s)%s",
                      msg.table_id, msg.id, STATUS_NAMES.get(msg.status, "?"),
                      math.ceil(elapsed), msg.deadline_s, flag)

    def describe(self, items):
        return ", ".join("%dx %s" % (q, self.names.get(i, i)) for i, q in Counter(items).items())

    def send(self, table, items):
        # o número do pedido fica no servidor de parâmetros para não repetir
        # se a interface for reiniciada com o sistema rodando
        order_id = int(rospy.get_param("/garcom/last_order_id", 0)) + 1
        rospy.set_param("/garcom/last_order_id", order_id)
        order = Order(id=order_id, table_id=table, items=items, stamp=rospy.Time.now())
        self.pub.publish(order)
        rospy.loginfo("Novo pedido %d da mesa %d: %s", order_id, table, self.describe(items))

    # ------------------------------------------------------------ modos
    def run_auto(self):
        period = float(rospy.get_param("~period_s", 20.0))
        rate = rospy.Rate(1.0 / period)
        while not rospy.is_shutdown():
            items = random.sample(self.menu, random.randint(1, 2))
            self.send(random.randint(1, self.tables), items)
            rate.sleep()

    def print_menu(self):
        print("\n========== Robô Garçom - Cardápio ==========")
        for n, item in enumerate(self.menu, start=1):
            qty = self.stock.get(item)
            info = "" if qty is None else ("  (esgotado)" if qty <= 0 else "  (%d em estoque)" % qty)
            print("  %d) %s%s" % (n, self.names[item], info))
        print("=============================================")

    def ask_table(self):
        while not rospy.is_shutdown():
            text = input("Mesa (1-%d): " % self.tables).strip()
            if text.isdigit() and 1 <= int(text) <= self.tables:
                return int(text)
            print("Mesa inválida.")

    def ask_items(self):
        """Aceita números do cardápio, com quantidade opcional: '1 1 3' ou '2x1 3'."""
        while not rospy.is_shutdown():
            text = input("Itens (ex.: 1 1 3  ou  2x1 3): ").strip().lower()
            items, ok = [], bool(text)
            for token in re.split(r"[\s,]+", text):
                match = re.fullmatch(r"(?:(\d+)x)?(\d+)", token)
                if not match or not 1 <= int(match.group(2)) <= len(self.menu):
                    ok = False
                    break
                items += [self.menu[int(match.group(2)) - 1]] * int(match.group(1) or 1)
            if ok and items:
                return items
            print("Não entendi. Use os números do cardápio, por exemplo: 1 1 3  ou  2x1 3")

    def run_manual(self):
        rospy.sleep(0.5)  # tempo para receber o estoque
        while not rospy.is_shutdown():
            self.print_menu()
            table = self.ask_table()
            items = self.ask_items()
            self.send(table, items)
            rospy.sleep(0.5)  # espera o estoque atualizado antes de mostrar o cardápio de novo


def main():
    rospy.init_node("interface")
    ui = Interface()
    if rospy.get_param("~mode", "manual") == "auto":
        ui.run_auto()
    else:
        try:
            ui.run_manual()
        except (KeyboardInterrupt, EOFError):
            print()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
