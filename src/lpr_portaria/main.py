# -*- coding: utf-8 -*-
"""
Portaria Inteligente — LPR
Versão: 4.0 modularizada

Fluxo:
1. Abre câmera
2. Acha contorno que parece placa (carro ou moto)
3. Faz warp (retifica)
4. Se for formato largo -> trata como carro
   Se for quase quadrado -> trata como moto (2 linhas)
5. Roda Tesseract
6. Valida placa
7. Consulta acesso no SQLite
8. Registra evento no banco

Também possui modo teste sem câmera:

python -m lpr_portaria.main --teste ABC1D23
"""

import platform
import re
import sys
import time

import cv2
import pytesseract

from lpr_portaria.acesso import verificar_acesso
from lpr_portaria.camera import inicializar_camera
from lpr_portaria.database import criar_tabelas, garantir_colunas_eventos, inserir_evento
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
def processar_placa_carro(roi, ultimo_texto: str, ultimo_ts: float):
    placa_bin = binarizar_para_ocr(roi)

    texto, conf = ocr_linha_carro(placa_bin)
    valido = placa_valida(texto)

    print(f"DEBUG OCR Carro: '{texto}' | Conf: {conf} | Válida: {valido}")

    if valido:
        agora = time.time()

        if (texto != ultimo_texto) or ((agora - ultimo_ts) > DEBOUNCE_S):
            registrar_acesso(texto, conf, "carro")

            ultimo_texto = texto
            ultimo_ts = agora

    cv2.imshow("Placa (warp)", roi)
    cv2.imshow("Placa (pre)", placa_bin)

    return ultimo_texto, ultimo_ts


# ------------------------------------------------------------
# PROCESSAMENTO DE MOTO
# ------------------------------------------------------------
def processar_placa_moto(roi, ultimo_texto: str, ultimo_ts: float):
    placa_bin = binarizar_para_ocr(roi)

    h, w = placa_bin.shape[:2]

    xm = int(0.08 * w)
    ym = int(0.10 * h)

    placa_bin = placa_bin[ym : h - ym, xm : w - xm]

    meio = placa_bin.shape[0] // 2

    topo = placa_bin[:meio, :]
    base = placa_bin[meio:, :]

    txt_top = ocr_linha_unica(topo, "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    txt_base = ocr_linha_unica(base, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

    texto = (txt_top + txt_base).upper()
    texto = re.sub(r"[^A-Z0-9]", "", texto)

    valido = placa_valida(texto)

    print(f"DEBUG OCR Moto: topo='{txt_top}' base='{txt_base}' -> '{texto}' | Válida: {valido}")

    if valido:
        agora = time.time()

        if (texto != ultimo_texto) or ((agora - ultimo_ts) > DEBOUNCE_S):
            registrar_acesso(texto, 0.0, "moto")

            ultimo_texto = texto
            ultimo_ts = agora

    cv2.imshow("Moto Topo (bin)", topo)
    cv2.imshow("Moto Base (bin)", base)
    cv2.imshow("Placa (warp)", roi)

    return ultimo_texto, ultimo_ts


# ------------------------------------------------------------
# LOOP PRINCIPAL DA CÂMERA
# ------------------------------------------------------------
def mostrar_feed_camera(cap):
    preparar_banco()

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

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        frame_cont = frame.copy()
        melhor_roi = None
        modo_moto = False

        for c in contours:
            perimetro = cv2.arcLength(c, True)

            if perimetro < 150:
                continue

            approx = cv2.approxPolyDP(c, 0.02 * perimetro, True)

            if len(approx) != 4:
                continue

            _x, _y, w, h = cv2.boundingRect(approx)

            if w < 100 or h < 25:
                continue

            aspect = w / float(h)

            eh_carro = 1.8 <= aspect <= 6.8
            eh_moto = 0.7 <= aspect <= 1.6

            if not (eh_carro or eh_moto):
                continue

            cv2.drawContours(frame_cont, [approx], -1, (0, 255, 0), 2)

            pontos = approx.reshape(4, 2)
            placa_warp = quatro_pontos_warp(frame, pontos)

            if placa_warp is None:
                continue

            melhor_roi = placa_warp
            modo_moto = eh_moto

            break

        if melhor_roi is not None:
            if modo_moto:
                ultimo_texto, ultimo_ts = processar_placa_moto(
                    melhor_roi,
                    ultimo_texto,
                    ultimo_ts,
                )
            else:
                ultimo_texto, ultimo_ts = processar_placa_carro(
                    melhor_roi,
                    ultimo_texto,
                    ultimo_ts,
                )

        cv2.imshow("Feed da Câmera", frame)
        cv2.imshow("Bordas", edges)
        cv2.imshow("Contornos", frame_cont)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


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
