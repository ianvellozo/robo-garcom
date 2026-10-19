#!/usr/bin/env python3
"""Estoque (responsável: Ian) - versão 19/10.

Lê o cardápio de /garcom/cardapio (config/cardapio.yaml) e:
- serviço /garcom/check_stock: diz se há estoque para todos os itens de um
  pedido e, com reserve = true, já dá baixa neles (reserva para o pedido);
- serviço /garcom/restock: repõe um item, por exemplo:
    rosservice call /garcom/restock "{item: 'rosquinha', quantity: 5}"
- serviço /garcom/set_stock: define a quantidade de um item (botão Estoque da tela da bancada);
- tópico /garcom/stock: publica o estoque atual sempre que ele muda;
- avisa quando um item chega no nível de estoque baixo.
"""
import threading
from collections import Counter

import rospy
from garcom_msgs.msg import StockLevels
from garcom_msgs.srv import (CheckStock, CheckStockResponse, Restock, RestockResponse,
                             SetStock, SetStockResponse)


class StockServer:
    def __init__(self):
        cardapio = rospy.get_param("/garcom/cardapio", [])
        self.low_level = int(rospy.get_param("/garcom/estoque_baixo", 2))
        self.order = [entry["item"] for entry in cardapio]           # ordem do cardápio
        self.names = {entry["item"]: entry["nome"] for entry in cardapio}
        self.stock = {entry["item"]: int(entry["estoque"]) for entry in cardapio}
        self.lock = threading.Lock()

        self.pub = rospy.Publisher("/garcom/stock", StockLevels, queue_size=1, latch=True)
        rospy.Service("/garcom/check_stock", CheckStock, self.on_check)
        rospy.Service("/garcom/restock", Restock, self.on_restock)
        rospy.Service("/garcom/set_stock", SetStock, self.on_set)

        self.publish()
        rospy.loginfo("Estoque pronto: %s", self.summary())

    def summary(self):
        return ", ".join("%s %d" % (self.names[i], self.stock[i]) for i in self.order)

    def publish(self):
        with self.lock:
            msg = StockLevels(items=list(self.order), quantities=[self.stock[i] for i in self.order])
        self.pub.publish(msg)

    def on_check(self, req):
        wanted = Counter(req.items)
        with self.lock:
            missing = [item for item, qty in wanted.items() if self.stock.get(item, 0) < qty]
            reserved = req.reserve and not missing
            if reserved:
                for item, qty in wanted.items():
                    self.stock[item] -= qty
            low = [i for i in wanted if reserved and self.stock[i] <= self.low_level]
        if reserved:
            rospy.loginfo("Reservado: %s. Estoque: %s",
                          ", ".join("%dx %s" % (q, i) for i, q in wanted.items()), self.summary())
            for item in low:
                rospy.logwarn("Estoque baixo: %s (%d restante(s))", self.names[item], self.stock[item])
            self.publish()
        return CheckStockResponse(available=not missing, missing=missing)

    def on_set(self, req):
        if req.item not in self.stock:
            return SetStockResponse(success=False, total=0, message="Item fora do cardápio: %s" % req.item)
        if req.quantity < 0:
            return SetStockResponse(success=False, total=self.stock[req.item], message="Quantidade não pode ser negativa")
        with self.lock:
            self.stock[req.item] = req.quantity
        rospy.loginfo("Estoque ajustado: %s = %d", self.names[req.item], req.quantity)
        self.publish()
        return SetStockResponse(success=True, total=req.quantity, message="ok")

    def on_restock(self, req):
        if req.item not in self.stock:
            return RestockResponse(success=False, total=0, message="Item fora do cardápio: %s" % req.item)
        if req.quantity <= 0:
            return RestockResponse(success=False, total=self.stock[req.item], message="Quantidade deve ser positiva")
        with self.lock:
            self.stock[req.item] += req.quantity
            total = self.stock[req.item]
        rospy.loginfo("Reposição: +%d %s (agora %d)", req.quantity, self.names[req.item], total)
        self.publish()
        return RestockResponse(success=True, total=total, message="ok")


def main():
    rospy.init_node("stock_server")
    StockServer()
    rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
