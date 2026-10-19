#!/usr/bin/env python3
"""Fila de pedidos (responsável: Ian) - versão 19/10.

- Recebe pedidos em /garcom/orders e reserva os itens no estoque (/garcom/check_stock).
  Se faltar algum item, o pedido é recusado e nada é reservado.
- Controla o prazo máximo de entrega de cada pedido (cronômetro por pedido):
    * alerta: o pedido passou de 70% do prazo (parâmetro /garcom/warning_ratio);
    * atrasado: o pedido passou do prazo (parâmetro /garcom/deadline_s).
- Entrega ao gerenciador de missões (/garcom/next_order) o pedido com MENOS
  tempo restante. Como todos têm o mesmo prazo, hoje isso é a ordem de chegada;
  quando cada item tiver o seu prazo (09/11), um pedido urgente passa à frente.
- Publica o estado de cada pedido em /garcom/order_status.
- Registra as métricas de entrega: tempo médio e % de pedidos no prazo.
"""
import copy
import threading

import rospy
from garcom_msgs.msg import Order, OrderStatus
from garcom_msgs.srv import CheckStock, NextOrder, NextOrderResponse


class OrderQueue:
    def __init__(self):
        self.deadline_s = float(rospy.get_param("/garcom/deadline_s", 600.0))
        self.warning_ratio = float(rospy.get_param("/garcom/warning_ratio", 0.7))

        self.lock = threading.Lock()
        self.active = {}    # id -> OrderStatus de todo pedido validado e ainda não entregue
        self.waiting = []   # ids dos pedidos validados que esperam o robô
        self.delivery_times = []
        self.late_deliveries = 0

        self.status_pub = rospy.Publisher("/garcom/order_status", OrderStatus, queue_size=50)

        rospy.loginfo("Aguardando o serviço de estoque...")
        rospy.wait_for_service("/garcom/check_stock")
        self.check_stock = rospy.ServiceProxy("/garcom/check_stock", CheckStock)

        rospy.Service("/garcom/next_order", NextOrder, self.on_next_order)
        rospy.Subscriber("/garcom/orders", Order, self.on_order)
        rospy.Subscriber("/garcom/order_status", OrderStatus, self.on_status)
        rospy.Timer(rospy.Duration(1.0), self.check_deadlines)

        rospy.loginfo("Fila de pedidos pronta (prazo máximo: %.0f s, alerta em %.0f%% do prazo).",
                      self.deadline_s, 100 * self.warning_ratio)

    # ------------------------------------------------------------ prazos
    def elapsed(self, st):
        return (rospy.Time.now() - st.stamp).to_sec()

    def remaining(self, st):
        return st.deadline_s - self.elapsed(st)

    def check_deadlines(self, _event):
        """Roda a cada 1 s: marca os pedidos que entraram em alerta ou atrasaram."""
        changed = []
        with self.lock:
            for st in self.active.values():
                t = self.elapsed(st)
                if t > st.deadline_s and not st.late:
                    st.late = st.warning = True
                    changed.append(copy.deepcopy(st))
                elif t >= self.warning_ratio * st.deadline_s and not st.warning:
                    st.warning = True
                    changed.append(copy.deepcopy(st))

        for st in changed:
            if st.late:
                rospy.logwarn("ATRASADO: pedido %d da mesa %d passou do prazo de %.0f s",
                              st.id, st.table_id, st.deadline_s)
            else:
                rospy.logwarn("ALERTA: pedido %d da mesa %d já usou %.0f%% do prazo (faltam %.0f s)",
                              st.id, st.table_id, 100 * self.warning_ratio, self.remaining(st))
            self.status_pub.publish(st)

    # ----------------------------------------------------------- pedidos
    def new_status(self, order, status):
        msg = OrderStatus()
        msg.id = order.id
        msg.table_id = order.table_id
        msg.items = order.items
        msg.status = status
        msg.stamp = order.stamp
        msg.deadline_s = self.deadline_s
        return msg

    def on_order(self, order):
        rospy.loginfo("Pedido %d recebido da mesa %d: %s",
                      order.id, order.table_id, ", ".join(order.items))
        self.status_pub.publish(self.new_status(order, OrderStatus.RECEBIDO))

        try:
            resp = self.check_stock(items=order.items, reserve=True)  # reserva os itens
        except rospy.ServiceException as err:
            rospy.logerr("Falha ao consultar o estoque: %s", err)
            return

        if not resp.available:
            rospy.logwarn("Pedido %d recusado; sem estoque: %s", order.id, ", ".join(resp.missing))
            self.status_pub.publish(self.new_status(order, OrderStatus.RECUSADO))
            return

        st = self.new_status(order, OrderStatus.VALIDADO)
        with self.lock:
            self.active[st.id] = st
            self.waiting.append(st.id)
            size = len(self.waiting)
        self.status_pub.publish(st)
        rospy.loginfo("Pedido %d validado; %d pedido(s) esperando o robô", order.id, size)

    def on_status(self, msg):
        """Acompanha o que o gerenciador de missões publica (em coleta, em entrega, entregue)."""
        with self.lock:
            st = self.active.get(msg.id)
            if st is None:
                return
            st.status = max(st.status, msg.status)  # o estado só avança
            if st.status != OrderStatus.ENTREGUE:
                return
            del self.active[msg.id]
            total = self.elapsed(st)
            self.delivery_times.append(total)
            on_time = total <= st.deadline_s
            if not on_time:
                self.late_deliveries += 1
            n = len(self.delivery_times)
            avg = sum(self.delivery_times) / n
            pct = 100.0 * (n - self.late_deliveries) / n

        rospy.loginfo("Pedido %d entregue em %.1f s (%s). Métricas: %d entregue(s), média %.1f s, %.0f%% no prazo",
                      msg.id, total, "no prazo" if on_time else "ATRASADO", n, avg, pct)

    def on_next_order(self, _req):
        with self.lock:
            if not self.waiting:
                return NextOrderResponse(has_order=False)
            # menor tempo restante primeiro
            best = min(self.waiting, key=lambda oid: self.remaining(self.active[oid]))
            self.waiting.remove(best)
            order = copy.deepcopy(self.active[best])
        return NextOrderResponse(has_order=True, order=order)


def main():
    rospy.init_node("order_queue")
    OrderQueue()
    rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
