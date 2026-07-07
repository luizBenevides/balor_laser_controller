---
name: analista-automacao
description: Auxilia no desenvolvimento de fluxos de automação industrial integrando a gravadora laser Galvo (BJJCZ LMCV4), CLP e Robô Denker via Modbus TCP e PostgreSQL.
---

# Analista de Automação

Esta habilidade orienta o agente na criação, modificação e depuração de fluxos de automação no projeto de controle de marcação a laser. Ela consolida as regras de negócio e de comunicação entre a gravadora laser, o CLP (Controlador Lógico Programável), o Robô Denker e o banco de dados PostgreSQL.

## When to use this skill

- Ao implementar novos scripts de automação de fluxo (ex: `fluxo_automatico.py`).
- Ao depurar a ordem de acionamentos ou leituras de registradores Modbus do CLP e do Robô.
- Ao configurar a geração de códigos de barra dinâmicos com gravação subsequente na laser.
- Ao mapear novos status ou ações físicas de controle na máquina.

## How to use it

### 1. Diretrizes de Comunicação com Dispositivos

#### A. Gravadora Laser (BJJCZ LMCV4)
- **Conectividade**: Comunicação via USB encapsulada em [balor/sender.py](file:///C:/Users/paulo/Desktop/balor/balor/sender.py).
- **Controle Físico**: A chamada `laser.execute(command_list)` é **síncrona (bloqueante)**. Ela pausa a execução do script Python até que os motores dos espelhos galvo terminem de desenhar fisicamente toda a arte.
- **Checagem Não-Bloqueante**: Pode ser feito polling chamando `laser.is_busy()` (que lê a resposta USB e verifica o bit `0x04`).

#### B. CLP e Robô Denker (Modbus TCP)
- **CLP**: IP `192.168.1.5`, Porta `502`.
- **Robô (Denker)**: IP `192.168.1.8`, Porta `502`.
- **Lógica de Endereçamento**:
  - `addr < 10000`: Coils (Binário R/W)
  - `10000 <= addr < 30000`: Discrete Inputs (Binário R-Only, mapeado subtraindo 10000)
  - `30000 <= addr < 40000`: Input Registers (16-bit R-Only, mapeado subtraindo 30000)
  - `addr >= 40000`: Holding Registers (16-bit R/W, mapeado subtraindo 40000)
- **Fallback do Robô**: Se ler ou escrever em um Coil no Robô falhar, utilize Holding Registers ou Input Registers no mesmo endereço como fallback.

#### C. Padrão de Arte e Presets (Arte 1 - Serial Banco)
Para manter a compatibilidade e padronização das gravações geradas a partir dos seriais do banco de dados, utilize o preset `"Arte 1 (Serial Banco)"` com as seguintes especificações técnicas:
- **Tipo de Código de Barras**: `gs1_128` (EAN 128C)
- **Fonte do Serial**: `Barcode Font34` (resolvido a partir de `"Barcode Font34.ttf"` ou diretório de fontes do Windows)
- **Espaçamento de Texto (Text Space / Character Spacing)**: `0.906`
- **Dimensões Físicas**: Largura (X) de `39.620 mm` e Altura total (Y) de `15.500 mm` (sendo o texto do Serial no topo com `6.0 mm` de altura, espaçamento de `3.0 mm` e o código de barras embaixo com `6.5 mm` de altura). Ambos agrupados no mesmo objeto.
- **Ajustes de Posição**: Ângulos e coordenadas X e Y da laser ajustáveis e salvos diretamente no arquivo de presets do estúdio (`laser_presets.json`).

---

### 2. O Ciclo do Fluxo Automático

O fluxo automático opera como uma máquina de estados contínua. Ele deve seguir rigorosamente a sequência descrita abaixo:

```mermaid
sequenceDiagram
    participant DB as Banco PostgreSQL
    participant Auto as Script de Automação
    participant Robo as Robô Denker
    participant CLP as CLP Mestre
    participant Laser as Gravadora Laser

    Note over Auto: Loop de Espera
    Auto->>DB: Busca próximo serial pendente (laser_gravado = FALSE)
    DB-->>Auto: Retorna Serial da Peça
    
    Note over Auto, Robo: Aguarda posicionamento inicial
    loop Polling de Status
        Auto->>Robo: Lê status de peça no berço (memória 10100/10101)
        Robo-->>Auto: Sinaliza 'Posicionado no Berço'
    end

    Note over Auto, Laser: Fase 1: Gravação Frontal
    Auto->>Laser: Executa Gravação do Logo Frontal (bloqueante)
    Laser-->>Auto: Conclusão física da gravação

    Note over Auto, Robo: Fase 2: Giro da Peça
    Auto->>Robo: Aciona memória 101 (Gravação Traseira / Solicita Giro)
    
    loop Polling de Status
        Auto->>Robo: Lê status de peça virada
        Robo-->>Auto: Sinaliza 'Giro Concluído'
    end

    Note over Auto, Laser: Fase 3: Gravação Traseira
    Auto->>Laser: Executa Gravação de 2 Logos na Parte Traseira
    Laser-->>Auto: Conclusão física da gravação

    Note over Auto, Robo: Fase 4: Liberação
    Auto->>Robo: Escreve True na memória 102 (INSPEÇÃO OK)
    Note over Robo: Robô coleta a peça e envia para Aprovados
    
    Note over Auto, DB: Fase 5: Registro
    Auto->>DB: Executa mark_as_engraved(log_id)
    Auto->>Robo: Escreve False na memória 102 (limpa sinal)
```

---

### 3. Convenções de Código para Implementações

1. **Imports sugeridos**:
   ```python
   from pyModbusTCP.client import ModbusClient
   from db_module import DBManager
   from plc_panel import ModbusDevice
   from balor.sender import Sender
   from balor.command_list import CommandBinary
   ```
2. **Tratamento de Exceções**: A perda de conexão com o banco ou com a laser não deve parar o loop. O sistema deve registrar o log do erro e tentar se reconectar indefinidamente a cada 2 ou 5 segundos.
3. **Logs**: Cada mudança de estado da automação deve ser impressa no terminal com um prefixo identificável (ex: `[AUTO-ESTADO]`).
