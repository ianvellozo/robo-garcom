#!/usr/bin/env python3
"""Interface de pedidos - ESQUELETO (responsável: Mariana).

Publica um pedido de exemplo a cada ~period_s segundos em /garcom/orders
e mostra no terminal o estado de cada pedido (/garcom/order_status).

TODO(Mariana): substituir pela interface web, em que a mesa escolhe os itens.
"""
import math
import random

import rospy
from garcom_msgs.msg import Order, OrderStatus

STATUS_NAMES = {
    OrderStatus.RECEBIDO: "recebido",
    OrderStatus.VALIDADO: "validado",
    OrderStatus.EM_COLETA: "em coleta",
    OrderStatus.EM_ENTREGA: "em entrega",
    OrderStatus.ENTREGUE: "entregue",
    OrderStatus.RECUSADO: "recusado",
}


def on_status(msg):
    elapsed = (rospy.Time.now() - msg.stamp).to_sec()
    flag = ""
    if msg.late:
        flag = " - ATRASADO"
    elif msg.warning:
        flag = " - alerta de prazo"
    rospy.loginfo("[mesa %d] pedido %d: %s (%d s de %.0f s)%s",
                  msg.table_id, msg.id, STATUS_NAMES.get(msg.status, "?"),
                  math.ceil(elapsed), msg.deadline_s, flag)


def main():
    rospy.init_node("interface")
    menu = rospy.get_param("~menu", ["cafe", "croissant", "rosquinha"])
    tables = rospy.get_param("~tables", 4)
    period = rospy.get_param("~period_s", 20.0)

    pub = rospy.Publisher("/garcom/orders", Order, queue_size=10)
    rospy.Subscriber("/garcom/order_status", OrderStatus, on_status)

    rospy.loginfo("Aguardando a fila de pedidos...")
    while pub.get_num_connections() == 0 and not rospy.is_shutdown():
        rospy.sleep(0.2)

    next_id = 1
    rate = rospy.Rate(1.0 / period)
    while not rospy.is_shutdown():
        order = Order()
        order.id = next_id
        order.table_id = random.randint(1, tables)
        order.items = random.sample(menu, random.randint(1, 2))
        order.stamp = rospy.Time.now()
        pub.publish(order)
        rospy.loginfo("Novo pedido %d da mesa %d: %s",
                      order.id, order.table_id, ", ".join(order.items))
        next_id += 1
        rate.sleep()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
