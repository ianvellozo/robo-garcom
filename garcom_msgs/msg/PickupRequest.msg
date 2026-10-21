# Pedido de coleta numa bancada (publicado pela missao em /garcom/pickup_request).
# A tela da bancada mostra o total desta comanda e a divisao por mesa.
# Se entrar pedido novo enquanto o robo esta nas bancadas, a mesma bancada pode
# receber mais de uma comanda na mesma viagem (extra = true).
uint32 ticket_id      # numero da comanda (unico); a confirmacao volta com ele
uint32 trip_id
string station
bool extra            # true: mais itens para uma bancada que ja montou bandeja nesta viagem
string[] items        # total de cada item nesta comanda
uint32[] quantities   # na mesma ordem de items
PickupLine[] lines    # o mesmo total, separado por pedido/mesa
