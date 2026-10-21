# Viagem planejada pelo robo (publicada pela missao em /garcom/trip)
uint32 trip_id
string[] stops        # pontos na ordem planejada: estacoes e depois mesas
int8 current          # indice da parada atual (-1 antes de sair)
bool finished
uint32[] order_ids    # pedidos levados nesta viagem
float32 estimated_s   # tempo estimado da viagem (s)
