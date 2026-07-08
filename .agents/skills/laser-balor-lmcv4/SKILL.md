---
name: laser-balor-lmcv4
description: Guia focado na gravadora laser BJJCZ/LMCV4 deste repositorio Balor. Use quando Codex precisar alterar, depurar ou explicar a integracao sem SDK/EZCAD, comunicacao USB/libusb, geracao de jobs SVG/binario, presets, calibracao, parametros de marcacao, hatch, barcode/serial, preview ou execucao fisica da laser.
---

# Laser Balor LMCV4

Use esta skill para trabalhar apenas na camada da laser deste repositorio. Ela complementa a skill de automacao geral: aqui o foco e a placa BJJCZ/LMCV4, o pipeline de arte para job binario e a execucao USB sem SDK oficial.

## Modelo mental

- Nao ha SDK EzCAD no fluxo principal. O repositorio fala direto com a placa BJJCZ/LMCV4 via USB usando `pyusb` e `libusb-package`.
- A placa esperada e `VID=0x9588` e `PID=0x9899`.
- A comunicacao fisica fica em `balor/sender.py` e `balor/BJJCZ_LMCV4_FIBER_M.py`.
- A arte vira SVG vetorial, depois vira lista binaria de comandos da placa por `balor-svg.py`.
- A execucao real usa `balor.sender.Sender().open(...)` e `machine.execute(command_list=commands, loop_count=1)`.
- `machine.execute(...)` e bloqueante: quando retorna, a marcacao fisica terminou.

## Arquivos principais

- `balor/sender.py`: classe `Sender`, abertura USB, inicializacao da placa, envio de lista, abort/close, status.
- `balor/BJJCZ_LMCV4_FIBER_M.py`: baixo nivel USB, endpoints, VID/PID, claim interface, sequencias da placa.
- `balor/command_list.py`: operacoes de lista, serializacao em comandos de 12 bytes, `CommandBinary`.
- `balor-svg.py`: converte SVG em job binario; aplica settings de caneta, hatch, delays, escala, offset e calibracao.
- `barcode_module.py`: gera SVG do barcode/serial em vetor.
- `composer_module.py`: aplica posicao/escala/rotacao no SVG antes do `balor-svg.py`.
- `preview_module.py` e `balor-gui.py`: ajuste visual, preview e salvamento de presets.
- `laser_presets.json`: fonte da verdade para parametros e posicoes das artes.
- `cal_0002.csv`: arquivo de calibracao usado na conversao quando existe.
- `rotina_automatica_page.py`: gera jobs automaticos e executa a laser durante o ciclo.

## Fluxo de geracao no automatico

Em `rotina_automatica_page.py`, siga o padrao de `build_laser_job`:

1. Ler preset em `laser_presets.json`.
2. Gerar SVG bruto com `barcode_module.BarcodeGenerator.generate_code128_svg(...)`.
3. Aplicar posicao/escala com `composer_module.SceneComposer.compose_workspace(...)`.
4. Gerar CSV temporario de settings: cor, frequencia, potencia, velocidade, angulo hatch, espacamento hatch.
5. Chamar `balor-svg.py mark -f <svg> -o <job.bin> -s <settings.csv>`.
6. Usar `--xoff 0.0 --yoff 0.0 --xscale 1.0 --yscale 1.0` quando a posicao ja foi aplicada pelo composer.
7. Adicionar `-c cal_0002.csv` se o arquivo existir.
8. Ler `job.bin` como `balor.command_list.CommandBinary`.
9. Executar via `execute_laser_job`.

Evite aplicar posicao duas vezes. Se `compose_workspace` ja usou `offset_x` e `offset_y`, mantenha `balor-svg.py` com offsets zero.

## Execucao USB segura

Use este formato:

```python
import balor.sender

machine = balor.sender.Sender()
try:
    if not machine.open(machine_index=0):
        raise RuntimeError("Nao foi possivel abrir a placa laser.")
    machine.execute(command_list=commands, loop_count=1)
finally:
    machine.close()
```

Nao deixe conexao USB aberta depois de erro. Sempre fechar no `finally`.

## Parametros que impactam qualidade

- `power`: potencia percentual enviada para a placa.
- `speed`: velocidade de marcacao em mm/s.
- `freq`: frequencia/Q-switch em kHz.
- `hatch_enable`, `hatch_spacing`, `hatch_angle`: preenchimento por linhas.
- `--laser-on-delay`, `--laser-off-delay`, `--mark-end-delay`, `--polygon-delay`: delays estilo EzCAD.
- `--hatch-power-scale`: multiplica potencia somente do hatch/fill.
- `--hatch-speed-scale`: multiplica velocidade somente do hatch/fill.
- `--hatch-serpentine`: mantem desenho de hatch em serpentina para reduzir pulos.
- `text_space`, `text_font`, `barcode_w_scale`, `barcode_h`, `text_scale`: geometria do barcode/serial antes da conversao.

Quando a gravacao estiver forte demais ou falhando, ajuste em etapas pequenas. Nao mude posicao, potencia, hatch e escala ao mesmo tempo.

## Diferenca para EzCAD

Mesmo com numeros iguais no painel do EzCAD, o resultado pode mudar porque EzCAD tambem aplica:

- correcao/calibracao da lente;
- delays de laser e poligono;
- escala real do campo;
- modo e ordem de hatch;
- frequencia/pulse width conforme fonte;
- interpretacao de potencia pela placa;
- quantidade e ordem dos vetores gerados.

No nosso fluxo, essas camadas ficam espalhadas entre `laser_presets.json`, `balor-svg.py`, `barcode_module.py`, `composer_module.py` e `cal_0002.csv`.

## Regras ao editar

- Preserve `laser_presets.json` como fonte de parametros de producao.
- Preserve `cal_0002.csv` se existir; nao remova a calibracao sem motivo claro.
- Para posicao de arte no automatico, ajuste `offset_x` e `offset_y` do preset correto.
- Para tamanho do barcode, ajuste primeiro `barcode_w_scale` e `barcode_h`.
- Para forca/profundidade, ajuste primeiro `power`, `speed`, `freq`, `hatch_spacing` ou escalas de hatch.
- Para problemas de leitura de barcode, compare dimensao fisica, foco, contraste, fumaca, hatch e largura das barras.
- Nunca assuma que parametros do EzCAD sao equivalentes 1:1 sem validar no material real.

## Diagnostico rapido

- Placa nao aparece: rodar `python .\find_laser.py`; verificar cabo, energia e driver WinUSB/libusb no Zadig.
- Erro de USB claim/interface: verificar se outro software esta usando a placa e se o driver correto esta instalado.
- Job deslocado: verificar se posicao foi aplicada no composer e se `--xoff/--yoff` nao duplicaram offset.
- Job muito demorado para gerar: investigar quantidade de paths/hatch em `balor-svg.py` e complexidade do SVG.
- Gravacao sai muito forte: reduzir power, aumentar speed, aumentar hatch_spacing ou reduzir `--hatch-power-scale`.
- Gravacao sai falhada: verificar foco, velocidade alta demais, potencia baixa demais, delays e estabilidade USB.

## Referencias adicionais

Leia `references/laser_pipeline.md` quando precisar de detalhes mais profundos sobre o pipeline SVG para binario, estrutura de job e pontos de depuracao.