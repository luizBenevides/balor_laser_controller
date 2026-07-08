# Pipeline da Laser no Repositorio

## Entrada de arte

As fontes comuns sao:

- SVG aberto/gerado no `balor-gui.py`.
- Barcode/serial gerado por `barcode_module.py`.
- Composicao final por `composer_module.py`.

O `barcode_module.py` gera paths SVG para barras, guards e texto convertido em vetores. Isso evita depender de texto nativo na conversao da laser.

## Posicionamento

O repositorio usa dois caminhos historicos para posicionamento:

1. Antigo: passar `--xoff`, `--yoff`, `--xscale`, `--yscale` para `balor-svg.py`.
2. Atual no automatico: aplicar `offset_x`, `offset_y` e escala com `SceneComposer.compose_workspace`, depois chamar `balor-svg.py` com offsets e escala em zero/um.

Preferir o caminho atual no automatico para manter Arte 1 e Arte 2 alinhadas com o preview/preset.

## Conversao SVG para job

`balor-svg.py`:

- carrega paths com `svgpathtools`;
- separa pontos por segmentos;
- gera movimentos travel/mark;
- renderiza fill/hatch quando o path esta preenchido;
- aplica settings por cor/caneta;
- serializa comandos em lista binaria;
- salva `.bin` para execucao posterior.

Settings CSV usado no automatico:

```text
000000 <freq> <power> <speed> <hatch_angle> <hatch_spacing> None 1
```

`hatch_spacing` esta em microns no settings e e convertido para mm dentro do `balor-svg.py`.

## Execucao binaria

`rotina_automatica_page.py` le o `.bin` com:

```python
with open(job_file, "rb") as f:
    return balor.command_list.CommandBinary(f.read())
```

Depois executa com:

```python
machine.execute(command_list=commands, loop_count=1)
```

A chamada e bloqueante. Use isso como fim real da gravacao antes de camera, giro ou liberacao.

## USB e placa

A camada USB usa:

- `pyusb`;
- `libusb-package` como backend libusb;
- VID `0x9588`;
- PID `0x9899`;
- endpoint host-to-machine e machine-to-host definidos em `balor/BJJCZ_LMCV4_FIBER_M.py`.

No Windows, problemas comuns sao driver errado, placa ocupada pelo EzCAD/outro software ou falha ao reclamar interface 0.

## Calibracao

Se `cal_0002.csv` existe, a rotina adiciona `-c cal_0002.csv` na chamada do `balor-svg.py`.

Nao remover a calibracao durante depuracao de potencia ou barcode. Sem calibracao, posicao e escala podem mudar e confundir o teste.

## Ajuste de qualidade do barcode

Ordem recomendada:

1. Confirmar foco mecanico e distancia da lente.
2. Confirmar dimensao fisica com regua.
3. Ajustar `barcode_w_scale` e `barcode_h` para bater largura/altura.
4. Ajustar `power`, `speed`, `freq` para contraste sem profundidade excessiva.
5. Ajustar `hatch_spacing` e escalas de hatch.
6. Conferir se fumaca nao esta afetando inspecao/camera.
7. Comparar com peca gravada no EzCAD, mas sem assumir equivalencia direta de parametros.

## Comandos uteis

Testar deteccao USB:

```powershell
python .\find_laser.py
```

Abrir editor visual de arte/preset:

```powershell
python .\balor-gui.py
```

Abrir painel completo:

```powershell
python .\plc_panel.py
```