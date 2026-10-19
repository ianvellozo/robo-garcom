# Robo chegou numa estacao de coleta (publicado pela missao em /garcom/pickup_request).
# A tela da estacao mostra o que colocar na bandeja.
uint32 order_id
uint8 table_id
string station
string[] items        # itens desta estacao (ex.: cafe, suco)
uint32[] quantities   # quantidade de cada item, na mesma ordem
