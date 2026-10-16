#!/usr/bin/env python3
"""Estoque - ESQUELETO (responsável: Mariana).

Serviço /garcom/check_stock: responde se todos os itens do pedido têm
estoque, com base no parâmetro ~stock (config/estoque.yaml).

TODO(Mariana): dar baixa no estoque a cada entrega e permitir reposição.
"""
import rospy
from garcom_msgs.srv import CheckStock, CheckStockResponse


def main():
    rospy.init_node("stock_server")
    stock = rospy.get_param("~stock", {})

    def handle(req):
        missing = [item for item in req.items if stock.get(item, 0) <= 0]
        return CheckStockResponse(available=not missing, missing=missing)

    rospy.Service("/garcom/check_stock", CheckStock, handle)
    rospy.loginfo("Estoque pronto: %s", stock)
    rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
