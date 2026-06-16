import socket
from pyModbusTCP.client import ModbusClient

IP_ROBO = "192.168.1.8"
PORTS = [502, 503, 2000, 5000, 8000]

def check_port(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect((ip, port))
        print(f"PORTA {port}: ABERTA!")
        s.close()
        return True
    except:
        print(f"PORTA {port}: FECHADA")
        return False

print(f"--- Diagnosticando Robo em {IP_ROBO} ---")
for p in PORTS:
    if check_port(IP_ROBO, p):
        # Se a porta estiver aberta, tenta um Modbus basico
        client = ModbusClient(host=IP_ROBO, port=p, auto_open=True, timeout=2.0)
        # Testar diferentes Unit IDs (0, 1, 2, 255)
        for uid in [1, 255, 0]:
            client.unit_id = uid
            if client.open():
                print(f"  CONEXAO MODBUS SUCESSO na porta {p} com Unit ID {uid}!")
                res = client.read_coils(0, 1)
                print(f"  Leitura teste: {res}")
                client.close()
                break
            else:
                print(f"  Falha Modbus na porta {p} com Unit ID {uid}")
