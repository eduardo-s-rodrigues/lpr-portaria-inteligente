# -*- coding: utf-8 -*-
"""
Portaria Inteligente — LPR
Versão: 4.0 (carro + moto, com correção de rotação e OCR separado)

Fluxo:
1. abre câmera
2. acha contorno que parece placa (carro ou moto)
3. faz warp (retifica)
4. corrige se ficou de cabeça pra baixo
5. se for formato largo -> trata como carro
   se for quase quadrado -> trata como moto (2 linhas)
6. roda Tesseract
7. valida (Mercosul ou antiga)
8. grava CSV com timestamp
"""

import time
import platform
import re

import cv2
import pytesseract

from lpr_portaria.validacao import placa_valida
from lpr_portaria.ocr import (
    binarizar_para_ocr,
    ocr_linha_carro,
    ocr_linha_unica,
)
from lpr_portaria.camera import inicializar_camera
from lpr_portaria.warp import quatro_pontos_warp
from lpr_portaria.database import inserir_evento, criar_tabelas

# ------------------------------------------------------------
# CONFIGURAÇÕES GERAIS
# ------------------------------------------------------------
if platform.system() == "Windows":
    # ajuste se o seu estiver em outro lugar
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

DEBOUNCE_S = 2.0  # tempo mínimo entre leituras da MESMA placa


# ------------------------------------------------------------
# LOOP PRINCIPAL
# ------------------------------------------------------------
def mostrar_feed_camera(cap):
    criar_tabelas()
    ultimo_texto = ""
    ultimo_ts = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Falha ao capturar frame.")
            break

        # ---------- pré-processo pra contorno ----------
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 80, 160)
        # fecha buraquinhos
        ker = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, ker, iterations=1)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        frame_cont = frame.copy()

        melhor_roi = None
        modo_moto = False  # assume carro

        for c in contours:
            per = cv2.arcLength(c, True)
            if per < 150:
                continue
            approx = cv2.approxPolyDP(c, 0.02 * per, True)
            if len(approx) != 4:
                continue

            x, y, w, h = cv2.boundingRect(approx)
            if w < 100 or h < 25:
                continue

            aspect = w / float(h)

            # carro: bem largo
            eh_carro = 1.8 <= aspect <= 6.8
            # moto: quase quadrado (2 linhas)
            eh_moto = 0.7 <= aspect <= 1.6

            if not (eh_carro or eh_moto):
                continue

            cv2.drawContours(frame_cont, [approx], -1, (0, 255, 0), 2)

            pts = approx.reshape(4, 2)
            placa_warp = quatro_pontos_warp(frame, pts)
            if placa_warp is None:
                continue

            melhor_roi = placa_warp
            modo_moto = eh_moto
            break  # só a melhor do frame

        # ---------- se achou placa, faz OCR ----------
        if melhor_roi is not None:
            if not modo_moto:
                # ======== CARRO (1 linha) ========
                placa_bin = binarizar_para_ocr(melhor_roi)
                texto, conf = ocr_linha_carro(placa_bin)
                valido = placa_valida(texto)
                print(f"DEBUG OCR Carro: '{texto}' | Conf: {conf} | Válida: {valido}")

                if valido:
                    agora = time.time()
                    if (texto != ultimo_texto) or ((agora - ultimo_ts) > DEBOUNCE_S):
                        print(f"Placa Válida (carro): {texto}")
                        inserir_evento(texto, conf)
                        ultimo_texto = texto
                        ultimo_ts = agora

                cv2.imshow("Placa (warp)", melhor_roi)
                cv2.imshow("Placa (pre)", placa_bin)

            else:
                # ======== MOTO (2 linhas) ========
                placa_bin = binarizar_para_ocr(melhor_roi)

                h, w = placa_bin.shape[:2]
                # tira bordas pretas
                xm = int(0.08 * w)
                ym = int(0.10 * h)
                placa_bin = placa_bin[ym : h - ym, xm : w - xm]

                # corta no meio
                meio = placa_bin.shape[0] // 2
                topo = placa_bin[:meio, :]
                base = placa_bin[meio:, :]

                # lê topo (letras)
                txt_top = ocr_linha_unica(topo, "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                # lê base (números/letras)
                txt_base = ocr_linha_unica(base, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
                texto = (txt_top + txt_base).upper()
                texto = re.sub(r"[^A-Z0-9]", "", texto)

                valido = placa_valida(texto)
                print(
                    f"DEBUG OCR Moto: topo='{txt_top}' base='{txt_base}' -> '{texto}' | Válida: {valido}"
                )

                if valido:
                    agora = time.time()
                    if (texto != ultimo_texto) or ((agora - ultimo_ts) > DEBOUNCE_S):
                        print(f"Placa Válida (moto): {texto}")
                        inserir_evento(texto, conf)
                        ultimo_texto = texto
                        ultimo_ts = agora

                cv2.imshow("Moto Topo (bin)", topo)
                cv2.imshow("Moto Base (bin)", base)
                cv2.imshow("Placa (warp)", melhor_roi)

        # ---------- exibição base ----------
        cv2.imshow("Feed da Câmera", frame)
        cv2.imshow("Bordas", edges)
        cv2.imshow("Contornos", frame_cont)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


# ------------------------------------------------------------
def main():
    cap = inicializar_camera()
    if not cap:
        return
    try:
        mostrar_feed_camera(cap)
    finally:
        cap.release()
        cv2.destroyAllWindows()


# ------------------------------------------------------------
if __name__ == "__main__":
    main()
