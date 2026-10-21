# Robo chegou numa estacao de coleta (publicado pela missao em /garcom/pickup_request).
# A tela da bancada mostra o total desta estacao e a divisao por mesa.
uint32 trip_id
string station
string[] items        # total de cada item nesta estacao (todos os pedidos da viagem)
uint32[] quantities   # na mesma ordem de items
PickupLine[] lines    # o mesmo total, separado por pedido/mesa
