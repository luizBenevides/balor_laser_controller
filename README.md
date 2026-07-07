# Balor - Painel de Controle Laser, CLP e Camera

Este projeto controla a gravadora laser BJJCZ/LMCV4, comunica com o CLP via Modbus TCP, busca seriais no banco PostgreSQL e executa a rotina automatica com inspecao pela camera Keyence.

Arquivo principal para operacao:

```powershell
python .\plc_panel.py
```

## 1. Requisitos da maquina

Use uma maquina Windows com:

- Windows 10 ou Windows 11.
- Python 3.13.7 ou versao compativel instalada.
- Acesso de rede ao CLP, banco PostgreSQL e camera Keyence.
- Cabo USB conectado na placa da laser BJJCZ/LMCV4.
- Driver USB correto para a placa da laser.

Este ambiente foi validado com Python 3.13.7.

## 2. Arquivos que precisam ir junto

Copie a pasta inteira do projeto para a nova maquina, mantendo a estrutura dos arquivos.

Arquivos importantes:

- `plc_panel.py`: tela principal do sistema.
- `rotina_automatica_page.py`: fluxo automatico de gravacao, giro, camera e OK/NG.
- `dashboard_page.py`: dashboard de producao.
- `balor-gui.py`: tela para ajustar arte, presets e posicoes.
- `balor-svg.py`: conversor SVG para job da laser.
- `barcode_module.py`: geracao do barcode e texto serial.
- `composer_module.py`: composicao das artes nas posicoes salvas.
- `db_module.py`: conexao com PostgreSQL.
- `balor\`: biblioteca de comunicacao com a laser.
- `assets\`: icones/imagens da dashboard.
- `laser_presets.json`: presets, parametros e posicoes das artes.
- `plc_config.json`: IPs, memorias e comandos do CLP/robo.
- `cal_0002.csv`: calibracao usada pela laser.
- `.env`: configuracao do banco.
- `requirements.txt`: dependencias Python.

Nao apague `laser_presets.json`, `plc_config.json` e `cal_0002.csv`, porque eles carregam a configuracao da maquina.

## 3. Instalacao do Python

1. Instale Python para Windows.
2. Durante a instalacao, marque a opcao `Add python.exe to PATH`.
3. Abra o PowerShell e confirme:

```powershell
python --version
pip --version
```

## 4. Criar ambiente virtual

Dentro da pasta do projeto:

```powershell
cd C:\Users\paulo\Desktop\balor
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Se o PowerShell bloquear o activate, rode uma vez:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Depois abra outro PowerShell e ative novamente:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 5. Driver USB da laser

A comunicacao com a laser usa `pyusb` e `libusb-package`.

Teste se a placa aparece:

```powershell
python .\find_laser.py
```

Se nao encontrar a placa:

1. Confira o cabo USB da laser.
2. Confira se a placa esta ligada.
3. Instale/ajuste o driver USB da placa com Zadig, usando WinUSB/libusb para o dispositivo BJJCZ.
4. Rode novamente:

```powershell
python .\find_laser.py
```

## 6. Configurar banco PostgreSQL

Crie ou edite o arquivo `.env` na raiz do projeto:

```env
DB_HOST=192.168.0.30
DB_PORT=5433
DB_NAME=log_sette
DB_USER=sette_app
DB_PASS=coloque_a_senha_aqui
```

Teste a conexao:

```powershell
python .\db_module.py
```

A rotina automatica busca seriais na tabela `logs_producao` com:

- `resultado = 'A'`
- `test_type = 'estanque'`
- `laser_gravado = FALSE`

Depois de gravar, o sistema marca:

- `laser_gravado = TRUE`
- `laser_data_gravacao = CURRENT_TIMESTAMP`

## 7. Configurar CLP e memorias

O arquivo `plc_config.json` guarda os IPs e memorias usadas pelo painel manual.

Valores atuais:

```json
{
  "ip_clp": "192.168.1.5",
  "port_clp": "502",
  "ip_robo": "192.168.1.8",
  "port_robo": "502"
}
```

Memorias principais do fluxo automatico:

| Memoria | Funcao |
| --- | --- |
| M70 | Sensor/peca no ponto |
| M90 | Status/permissivo da rotina |
| M71 | Pulso para girar a peca |
| M72 | Pulso para voltar o giro |
| M73 | NG/Reprovado |
| M74 | OK/Aprovado |

Na nova maquina, confirme se o Windows esta na mesma rede do CLP e se consegue acessar o IP `192.168.1.5`.

## 8. Configurar camera Keyence

A camera e acessada por TCP no arquivo `rotina_automatica_page.py`.

Configuracao atual:

```python
KEYENCE_IP = "192.168.1.29"
KEYENCE_PORT = 8500
KEYENCE_TIMEOUT_S = 10
KEYENCE_TRIGGER_CMD = b"TRG\r"
```

Se o IP da camera mudar, altere `KEYENCE_IP`.

Formato esperado da resposta da camera:

- `1,serial`: aprovado.
- `0,0`: reprovado.

O fluxo faz:

1. Grava Arte 1.
2. Aguarda o tempo configurado em `CAMERA_AFTER_MARK_DELAY_S`.
3. Dispara a camera.
4. Grava resultado frontal.
5. Gira a peca com M71.
6. Grava Arte 2.
7. Aguarda o tempo configurado em `CAMERA_AFTER_MARK_DELAY_S`.
8. Dispara a camera.
9. Se as duas inspecoes aprovarem, liga M74.
10. Se qualquer uma reprovar, liga M73.

## 9. Configurar presets e posicoes da laser

O arquivo `laser_presets.json` guarda:

- Preset da Arte 1.
- Preset da Arte 2.
- Preset combinado `Arte 1 + 2 (Frontal + Traseira)`.
- Potencia, velocidade, frequencia, hatch e posicoes X/Y.

Para ajustar visualmente:

```powershell
python .\balor-gui.py
```

Depois de ajustar posicoes e parametros, salve o preset pela tela.

Na rotina automatica, as artes separadas usam as posicoes salvas nos presets. Se precisar ajustar manualmente, altere `offset_x` e `offset_y` no `laser_presets.json`.

## 10. Rodar o sistema

Com o ambiente virtual ativo:

```powershell
python .\plc_panel.py
```

Passos basicos:

1. Abra o sistema.
2. Na tela `Painel Manual`, conecte o CLP.
3. Verifique se os status M70/M90 aparecem corretamente.
4. Va para `Rotina Automatica`.
5. Confirme os presets de Arte 1 e Arte 2.
6. Marque `Auto-Sync Banco` se for buscar serial no banco.
7. Use `Modo teste/default` para testar com serial fixo.
8. Marque `Liberar fluxo automatico apos ajustar artes`.
9. Clique em `Iniciar Automatico`.
10. Acompanhe a tela de log e a dashboard.

## 11. Testes rapidos antes de produzir

Teste banco:

```powershell
python .\db_module.py
```

Teste laser USB:

```powershell
python .\find_laser.py
```

Teste painel completo:

```powershell
python .\plc_panel.py
```

Teste ajuste de arte:

```powershell
python .\balor-gui.py
```

## 12. Problemas comuns

### Laser nao conecta

- Verifique cabo USB.
- Verifique driver WinUSB/libusb no Zadig.
- Rode `python .\find_laser.py`.
- Confirme se outro software nao esta usando a placa.

### CLP nao conecta

- Confira IP e porta em `plc_config.json`.
- Confirme se a maquina esta na mesma rede.
- Confirme se a porta Modbus TCP 502 esta liberada.

### Banco nao conecta

- Confira `.env`.
- Confirme IP, porta, usuario e senha.
- Confirme se o PostgreSQL aceita conexao da nova maquina.

### Camera nao responde

- Confira `KEYENCE_IP` e `KEYENCE_PORT` em `rotina_automatica_page.py`.
- Confirme se a camera esta em modo TCP/server correto.
- Confirme se o comando de trigger e `TRG\r`.
- Confira se a camera retorna `1,serial` ou `0,0`.

### Barcode nao le

- Confira foco mecanico da laser.
- Confira potencia, velocidade, frequencia e hatch no preset.
- Confira se a fumaca saiu antes da inspecao. Ajuste `CAMERA_AFTER_MARK_DELAY_S` se necessario.
- Confira posicao X/Y no `laser_presets.json`.

## 13. Dependencias opcionais

O `requirements.txt` foi montado para o sistema principal: painel, dashboard, CLP, banco, camera, geracao de barcode e laser.

Alguns scripts antigos de diagnostico podem pedir dependencias opcionais como:

- `segno`: QR Code em scripts antigos.
- `svgelements`: animacoes/testes SVG antigos.
- `dpkt`: leitura de arquivos PCAP em scripts de debug USB.

Instale somente se for usar esses scripts:

```powershell
pip install segno svgelements dpkt
```

## 14. Backup recomendado

Antes de mexer em producao, faca backup destes arquivos:

- `.env`
- `laser_presets.json`
- `plc_config.json`
- `cal_0002.csv`

Esses arquivos carregam a configuracao real da maquina.