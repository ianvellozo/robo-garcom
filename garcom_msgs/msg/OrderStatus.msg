# Estado de um pedido (publicado em /garcom/order_status)
uint8 RECEBIDO=0
uint8 VALIDADO=1
uint8 EM_COLETA=2
uint8 EM_ENTREGA=3
uint8 ENTREGUE=4
uint8 RECUSADO=5

uint32 id
uint8 table_id
string[] items
uint8 status
time stamp           # momento em que o pedido foi feito
float32 deadline_s   # prazo maximo de entrega (s)
bool warning         # passou de 70% do prazo (preenchido a partir de 19/10)
bool late            # passou do prazo (preenchido a partir de 19/10)
