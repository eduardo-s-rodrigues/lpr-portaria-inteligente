# -*- coding: utf-8 -*-
"""
Portaria Inteligente — LPR

Fluxo:
1. Abre câmera
2. Acha contorno que parece placa
3. Faz warp
4. Aplica ajustes manuais: rotação e flip
5. Roda OCR
6. Valida placa
7. Consulta acesso no SQLite
8. Registra evento no banco

Modos:
python -m lpr_portaria.main
python -m lpr_portaria.main --teste ABC1D23
"""

import platform
import re
import sys
import time
from itertools import product

import cv2
import numpy as np
import pytesseract

from lpr_portaria.acesso import verificar_acesso
from lpr_portaria.camera import inicializar_camera
from lpr_portaria.database import (
    buscar_veiculo_por_placa,
    criar_tabelas,
    garantir_colunas_eventos,
    inserir_evento,
)
from lpr_portaria.ocr import (
    binarizar_para_ocr,
    ocr_linha_carro,
    ocr_linha_unica,
)
from lpr_portaria.validacao import placa_valida
from lpr_portaria.warp import quatro_pontos_warp

# ------------------------------------------------------------
# CONFIGURAÇÕES GERAIS
# ------------------------------------------------------------
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

DEBOUNCE_S = 2.0


# ------------------------------------------------------------
# ESTADO / CONTROLES
# ------------------------------------------------------------
def criar_estado():
    return {
        "rot": 0,
        "flip_h": False,
        "flip_v": False,
        "modo": "auto",  # auto, carro, moto
        "debug": True,
        "ajuda": True,
        "ocr_ativo": True,
    }


def texto_on_off(valor: bool) -> str:
    return "ON" if valor else "OFF"


def aplicar_ajustes_roi(roi, estado):
    """
    Aplica ajustes manuais somente na placa recortada.
    Isso ajuda quando a placa aparece de lado ou espelhada.
    """
    ajustada = roi.copy()

    rot = estado["rot"] % 360

    if rot == 90:
        ajustada = cv2.rotate(ajustada, cv2.ROTATE_90_CLOCKWISE)
    elif rot == 180:
        ajustada = cv2.rotate(ajustada, cv2.ROTATE_180)
    elif rot == 270:
        ajustada = cv2.rotate(ajustada, cv2.ROTATE_90_COUNTERCLOCKWISE)

    if estado["flip_h"]:
        ajustada = cv2.flip(ajustada, 1)

    if estado["flip_v"]:
        ajustada = cv2.flip(ajustada, 0)

    return ajustada


def gerar_variantes_placa(texto: str) -> list[str]:
    texto = re.sub(r"[^A-Z0-9]", "", texto.upper())

    if len(texto) != 7:
        return [texto]

    opcoes_por_posicao = []

    for indice, char in enumerate(texto):
        opcoes = [char]

        # Posições 0, 1 e 2: letras
        if indice in (0, 1, 2):
            mapa_letras = {
                "0": ["O", "Q", "D"],
                "1": ["I"],
                "2": ["Z"],
                "5": ["S"],
                "8": ["B"],
                "U": ["Q"],  # Q às vezes é lido como U
            }

            opcoes.extend(mapa_letras.get(char, []))

        # Posições 3, 5 e 6: números
        elif indice in (3, 5, 6):
            mapa_numeros = {
                "O": ["0"],
                "Q": ["0"],
                "D": ["0"],
                "I": ["1"],
                "L": ["1"],
                "Z": ["2"],
                "S": ["5"],
                "B": ["8"],
            }

            opcoes.extend(mapa_numeros.get(char, []))

        # Posição 4: letra no padrão Mercosul
        elif indice == 4:
            mapa_letra_mercosul = {
                "0": ["C", "O", "Q"],
                "1": ["I"],
                "2": ["Z"],
                "5": ["S"],
                "8": ["B"],
            }

            opcoes.extend(mapa_letra_mercosul.get(char, []))

        opcoes_sem_repetir = []

        for opcao in opcoes:
            if opcao not in opcoes_sem_repetir:
                opcoes_sem_repetir.append(opcao)

        opcoes_por_posicao.append(opcoes_sem_repetir)

    variantes = []

    for combinacao in product(*opcoes_por_posicao):
        placa = "".join(combinacao)

        if placa not in variantes:
            variantes.append(placa)

    return variantes


def escolher_melhor_placa(texto: str) -> str:
    variantes = gerar_variantes_placa(texto)

    # Primeiro tenta achar uma variação cadastrada no banco.
    for placa in variantes:
        if placa_valida(placa) and buscar_veiculo_por_placa(placa):
            if placa != texto:
                print(f"Correção por cadastro: {texto} -> {placa}")

            return placa

    # Se não achar no banco, usa a primeira variação válida.
    for placa in variantes:
        if placa_valida(placa):
            if placa != texto:
                print(f"Correção por padrão: {texto} -> {placa}")

            return placa

    return texto


def desenhar_interface(frame, estado):
    """
    Desenha uma mini interface no feed principal.
    """
    painel = frame.copy()

    x1, y1 = 10, 10
    x2, y2 = 720, 125

    cv2.rectangle(painel, (x1, y1), (x2, y2), (0, 0, 0), -1)
    frame = cv2.addWeighted(painel, 0.55, frame, 0.45, 0)

    linhas = [
        "LPR Portaria Inteligente",
        (
            f"ROT: {estado['rot']} | "
            f"Flip H: {texto_on_off(estado['flip_h'])} | "
            f"Flip V: {texto_on_off(estado['flip_v'])} | "
            f"Modo: {estado['modo']} | "
            f"OCR: {texto_on_off(estado['ocr_ativo'])}"
        ),
    ]

    if estado["ajuda"]:
        linhas.extend(
            [
                "Q sair | R girar placa | F flip H | V flip V",
                "M modo auto/carro/moto | D debug | O OCR on/off | H ajuda | C limpar",
            ]
        )
    else:
        linhas.append("H mostrar ajuda")

    y = 35

    for linha in linhas:
        cv2.putText(
            frame,
            linha,
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        y += 25

    return frame


def tratar_tecla(tecla, estado):
    """
    Retorna True quando deve sair do programa.
    """
    if tecla == -1:
        return False

    tecla = tecla & 0xFF

    if tecla in (ord("q"), ord("Q")):
        return True

    if tecla in (ord("r"), ord("R")):
        estado["rot"] = (estado["rot"] + 90) % 360
        print(f"Rotação da placa: {estado['rot']} graus")

    elif tecla in (ord("f"), ord("F")):
        estado["flip_h"] = not estado["flip_h"]
        print(f"Flip horizontal: {texto_on_off(estado['flip_h'])}")

    elif tecla in (ord("v"), ord("V")):
        estado["flip_v"] = not estado["flip_v"]
        print(f"Flip vertical: {texto_on_off(estado['flip_v'])}")

    elif tecla in (ord("m"), ord("M")):
        modos = ["auto", "carro", "moto"]
        atual = modos.index(estado["modo"])
        estado["modo"] = modos[(atual + 1) % len(modos)]
        print(f"Modo de leitura: {estado['modo']}")

    elif tecla in (ord("d"), ord("D")):
        estado["debug"] = not estado["debug"]
        print(f"Debug: {texto_on_off(estado['debug'])}")

    elif tecla in (ord("o"), ord("O")):
        estado["ocr_ativo"] = not estado["ocr_ativo"]
        print(f"OCR: {texto_on_off(estado['ocr_ativo'])}")

    elif tecla in (ord("h"), ord("H")):
        estado["ajuda"] = not estado["ajuda"]
        print(f"Ajuda: {texto_on_off(estado['ajuda'])}")

    elif tecla in (ord("c"), ord("C")):
        print("Limpeza manual solicitada.")
        return "limpar"

    return False


# ------------------------------------------------------------
# BANCO
# ------------------------------------------------------------
def preparar_banco():
    criar_tabelas()
    garantir_colunas_eventos()


# ------------------------------------------------------------
# MODO TESTE SEM CÂMERA
# ------------------------------------------------------------
def simular_leitura(placa: str, confianca: float = 99.0):
    preparar_banco()

    placa = placa.strip().upper()
    valido = placa_valida(placa)

    print(f"SIMULAÇÃO OCR: '{placa}' | Conf: {confianca} | Válida: {valido}")

    if not valido:
        print("Placa inválida.")
        return

    status, dados = verificar_acesso(placa)

    print(f"Placa Válida: {placa}")
    print(f"Status: {status}")

    if dados:
        print(f"Nome: {dados['nome']} | Tipo: {dados['tipo']}")

    inserir_evento(
        placa,
        confianca,
        status,
        dados["nome"] if dados else None,
        dados["tipo"] if dados else None,
    )

    print("Evento salvo no SQLite.")


# ------------------------------------------------------------
# REGISTRAR ACESSO
# ------------------------------------------------------------
def registrar_acesso(placa: str, confianca: float, origem: str):
    status, dados = verificar_acesso(placa)

    print(f"Placa Válida ({origem}): {placa}")
    print(f"Status: {status}")

    if dados:
        print(f"Nome: {dados['nome']} | Tipo: {dados['tipo']}")

    inserir_evento(
        placa,
        confianca,
        status,
        dados["nome"] if dados else None,
        dados["tipo"] if dados else None,
    )


# ------------------------------------------------------------
# PROCESSAMENTO DE CARRO
# ------------------------------------------------------------
def processar_placa_carro(roi, ultimo_texto: str, ultimo_ts: float, estado):
    roi_ajustada = aplicar_ajustes_roi(roi, estado)

    if not estado["ocr_ativo"]:
        if estado["debug"]:
            cv2.imshow("Placa ajustada", roi_ajustada)

        return ultimo_texto, ultimo_ts

    placa_bin = binarizar_para_ocr(roi_ajustada)

    texto, conf = ocr_linha_carro(placa_bin)
    valido = placa_valida(texto)

    print(f"DEBUG OCR Carro: '{texto}' | Conf: {conf} | Válida: {valido}")

    if valido:
        agora = time.time()

        if (texto != ultimo_texto) or ((agora - ultimo_ts) > DEBOUNCE_S):
            registrar_acesso(texto, conf, "carro")

            ultimo_texto = texto
            ultimo_ts = agora

    if estado["debug"]:
        cv2.imshow("Placa ajustada", roi_ajustada)
        cv2.imshow("Placa pre-processada", placa_bin)

    return ultimo_texto, ultimo_ts


# ------------------------------------------------------------
# PROCESSAMENTO DE MOTO
# ------------------------------------------------------------
def processar_placa_moto(roi, ultimo_texto: str, ultimo_ts: float, estado):
    roi_ajustada = aplicar_ajustes_roi(roi, estado)

    if estado["debug"]:
        cv2.imshow("Placa ajustada", roi_ajustada)

    if not estado["ocr_ativo"]:
        return ultimo_texto, ultimo_ts

    placa_bin = binarizar_para_ocr(roi_ajustada)

    h, w = placa_bin.shape[:2]

    # Remove bordas laterais e principalmente a faixa superior
    # onde aparece cidade/estado, exemplo: SP - ARARAQUARA.
    x1 = int(0.04 * w)
    x2 = int(0.96 * w)

    y1 = int(0.22 * h)
    y2 = int(0.96 * h)

    placa_util = placa_bin[y1:y2, x1:x2]

    h2, w2 = placa_util.shape[:2]

    # Na placa de moto, letras ficam na parte de cima
    # e números ficam na parte de baixo.
    corte = int(0.46 * h2)

    topo = placa_util[:corte, :]
    base = placa_util[corte:, :]

    # Aumenta bastante para o Tesseract enxergar melhor.
    topo = cv2.resize(topo, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
    base = cv2.resize(base, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)

    txt_top = ocr_linha_unica(topo, "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    txt_base = ocr_linha_unica(base, "0123456789")

    texto_bruto = (txt_top + txt_base).upper()
    texto_bruto = re.sub(r"[^A-Z0-9]", "", texto_bruto)

    texto = escolher_melhor_placa(texto_bruto)

    valido = placa_valida(texto)

    print(
        f"DEBUG OCR Moto: topo='{txt_top}' "
        f"base='{txt_base}' -> bruto='{texto_bruto}' "
        f"corrigido='{texto}' | Válida: {valido}"
    )

    if valido:
        agora = time.time()

        if (texto != ultimo_texto) or ((agora - ultimo_ts) > DEBOUNCE_S):
            registrar_acesso(texto, 0.0, "moto")

            ultimo_texto = texto
            ultimo_ts = agora

    if estado["debug"]:
        cv2.imshow("Moto Area Util", placa_util)
        cv2.imshow("Moto Topo", topo)
        cv2.imshow("Moto Base", base)

    return ultimo_texto, ultimo_ts


# ------------------------------------------------------------
# LOOP PRINCIPAL DA CÂMERA
# ------------------------------------------------------------
def mostrar_feed_camera(cap):
    preparar_banco()

    estado = criar_estado()

    ultimo_texto = ""
    ultimo_ts = 0.0

    while True:
        ok, frame = cap.read()

        if not ok:
            print("Falha ao capturar frame.")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 80, 160)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        frame_cont = frame.copy()
        melhor_roi = None
        modo_moto = False
        melhor_pontuacao = 0

        for c in contours:
            area = cv2.contourArea(c)

            if area < 1500:
                continue

            perimetro = cv2.arcLength(c, True)

            if perimetro < 120:
                continue

            approx = cv2.approxPolyDP(c, 0.03 * perimetro, True)

            x, y, w, h = cv2.boundingRect(c)

            if w < 80 or h < 25:
                continue

            aspect = w / float(h)

            # Regras mais flexíveis:
            # carro: placa mais larga
            # moto: placa mais quadrada/alta
            eh_carro = 1.6 <= aspect <= 7.0
            eh_moto = 0.75 <= aspect <= 2.6

            if estado["modo"] == "carro":
                eh_carro = 1.6 <= aspect <= 7.0
                eh_moto = False

            elif estado["modo"] == "moto":
                eh_carro = False
                eh_moto = 0.75 <= aspect <= 3.0

            if not (eh_carro or eh_moto):
                continue

            area_retangulo = w * h

            if area_retangulo == 0:
                continue

            preenchimento = area / area_retangulo

            if preenchimento < 0.25:
                continue

            # Pontuação: quanto maior e mais preenchido, melhor candidato.
            pontuacao = area * preenchimento

            if pontuacao <= melhor_pontuacao:
                continue

            roi_candidata = None

            # Se tiver 4 pontos, tenta corrigir perspectiva com warp.
            if len(approx) == 4:
                pontos = approx.reshape(4, 2)
                roi_candidata = quatro_pontos_warp(frame, pontos)

            # Se não tiver 4 pontos, usa recorte normal como fallback.
            if roi_candidata is None:
                margem_x = int(w * 0.08)
                margem_y = int(h * 0.15)

                x1 = max(0, x - margem_x)
                y1 = max(0, y - margem_y)
                x2 = min(frame.shape[1], x + w + margem_x)
                y2 = min(frame.shape[0], y + h + margem_y)

                roi_candidata = frame[y1:y2, x1:x2]

            if roi_candidata is None or roi_candidata.size == 0:
                continue

            melhor_pontuacao = pontuacao
            melhor_roi = roi_candidata
            modo_moto = eh_moto

            # Desenha o melhor candidato no frame de debug.
            cv2.rectangle(frame_cont, (x, y), (x + w, y + h), (0, 255, 0), 2)

            if len(approx) >= 4:
                cv2.drawContours(frame_cont, [approx], -1, (255, 0, 0), 2)

        if melhor_roi is not None:
            if modo_moto:
                ultimo_texto, ultimo_ts = processar_placa_moto(
                    melhor_roi,
                    ultimo_texto,
                    ultimo_ts,
                    estado,
                )
            else:
                ultimo_texto, ultimo_ts = processar_placa_carro(
                    melhor_roi,
                    ultimo_texto,
                    ultimo_ts,
                    estado,
                )

        frame_interface = desenhar_interface(frame.copy(), estado)

        cv2.imshow("Feed da Camera", frame_interface)

        if estado["debug"]:
            cv2.imshow("Bordas", edges)
            cv2.imshow("Contornos", frame_cont)

        tecla = cv2.waitKey(1)
        acao = tratar_tecla(tecla, estado)

        if acao is True:
            break

        if acao == "limpar":
            ultimo_texto = ""
            ultimo_ts = 0.0
            print("Última leitura limpa.")


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--teste":
        placa_teste = sys.argv[2]
        simular_leitura(placa_teste)
        return

    cap = inicializar_camera()

    if cap is None:
        return

    try:
        mostrar_feed_camera(cap)
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
