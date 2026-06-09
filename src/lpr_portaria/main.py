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

import csv
import time
from datetime import datetime
import platform
import re

import cv2
import numpy as np
import pytesseract

# ------------------------------------------------------------
# CONFIGURAÇÕES GERAIS
# ------------------------------------------------------------
if platform.system() == "Windows":
    # ajuste se o seu estiver em outro lugar
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

CSV_PATH = "entradas.csv"
DEBOUNCE_S = 2.0  # tempo mínimo entre leituras da MESMA placa

# ------------------------------------------------------------
# REGEX de placa
# carro Mercosul: ABC1D23
# moto Mercosul:  ABCD123 ? (aqui vamos validar igual ao carro)
# placa antiga:   ABC1234
# ------------------------------------------------------------
PADRAO_MERCOSUL = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")
PADRAO_ANTIGA = re.compile(r"^[A-Z]{3}[0-9]{4}$")


def placa_valida(txt: str) -> bool:
    txt = txt.strip().upper()
    return bool(PADRAO_MERCOSUL.match(txt) or PADRAO_ANTIGA.match(txt))


# ------------------------------------------------------------
# CSV
# ------------------------------------------------------------
def garantir_csv():
    try:
        open(CSV_PATH, "r", encoding="utf-8").close()
    except FileNotFoundError:
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "placa", "confianca"])


def log_csv(placa: str, confianca: float):
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([datetime.now().isoformat(timespec="seconds"), placa, f"{confianca:.1f}"])


# ------------------------------------------------------------
# AUX: ordenar pontos e warp
# ------------------------------------------------------------
def ordenar_pontos(pts: np.ndarray) -> np.ndarray:
    """Recebe 4 pontos (x,y) e devolve na ordem: tl, tr, br, bl."""
    pts = np.array(pts, dtype="float32")
    s = pts.sum(axis=1)  # x+y
    d = pts[:, 0] - pts[:, 1]  # x-y

    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(d)]
    bl = pts[np.argmax(d)]

    return np.array([tl, tr, br, bl], dtype="float32")


def quatro_pontos_warp(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """
    Retifica a placa e CORRIGE se estiver de cabeça pra baixo.
    """
    tl, tr, br, bl = ordenar_pontos(pts)

    # tamanhos
    wA = np.linalg.norm(br - bl)
    wB = np.linalg.norm(tr - tl)
    hA = np.linalg.norm(tr - br)
    hB = np.linalg.norm(tl - bl)
    maxW = int(max(wA, wB))
    maxH = int(max(hA, hB))
    if maxW < 10 or maxH < 10:
        return None

    # destino
    dst = np.array([[0, 0], [maxW - 1, 0], [maxW - 1, maxH - 1], [0, maxH - 1]], dtype="float32")

    M = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl]), dst)
    warp = cv2.warpPerspective(img, M, (maxW, maxH))

    # --------- correção de rotação ---------
    # idéia: placa mercosul tem faixa azul em cima (mais escura),
    # então o TOPO tende a ser mais escuro.
    h, w = warp.shape[:2]
    top_mean = np.mean(warp[0 : int(0.15 * h), :, :])
    bottom_mean = np.mean(warp[int(0.85 * h) : h, :, :])

    # se o fundo de baixo estiver mais ESCURO que o de cima, é provável que está 180°
    if bottom_mean < top_mean:
        warp = cv2.rotate(warp, cv2.ROTATE_180)

    return warp


# ------------------------------------------------------------
# PRÉ-PROCESSAMENTO COMUM
# ------------------------------------------------------------
def binarizar_para_ocr(img_bgr: np.ndarray) -> np.ndarray:
    """
    Converte BGR -> cinza -> blur -> Otsu invertido -> dilata -> aumenta -> borda
    Serve tanto pra carro quanto pra moto.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, bin_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    bin_dil = cv2.dilate(bin_inv, kernel, iterations=1)

    # sobe resolução
    big = cv2.resize(bin_dil, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

    # borda branca
    final = cv2.copyMakeBorder(big, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=[255, 255, 255])

    return final


# ------------------------------------------------------------
# OCR helpers
# ------------------------------------------------------------
def ocr_linha_unica(img_bin: np.ndarray, whitelist: str) -> str:
    """
    Lê 1 linha só, com whitelist de chars.
    """
    config = f"--oem 3 --psm 7 -c tessedit_char_whitelist={whitelist}"
    data = pytesseract.image_to_data(img_bin, config=config, output_type=pytesseract.Output.DICT)

    palavras = []
    for txt in data.get("text", []):
        if txt and txt.strip():
            palavras.append(txt.strip())
    bruto = "".join(palavras).upper()
    limpo = re.sub(r"[^A-Z0-9]", "", bruto)
    return limpo


def ocr_linha_carro(img_bin: np.ndarray):
    """
    Lê placa de carro (1 linha).
    Retorna (texto, confianca)
    """
    config = r"--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    data = pytesseract.image_to_data(img_bin, config=config, output_type=pytesseract.Output.DICT)

    palavras, confs = [], []
    for txt, conf in zip(data.get("text", []), data.get("conf", [])):
        if txt and txt.strip():
            palavras.append(txt.strip())
            try:
                c = float(conf)
                if c >= 0:
                    confs.append(c)
            except Exception:
                pass

    bruto = "".join(palavras).upper()
    limpo = re.sub(r"[^A-Z0-9]", "", bruto)
    conf_media = round(sum(confs) / len(confs), 1) if confs else 0.0
    return limpo, conf_media


# ------------------------------------------------------------
# INICIALIZAR CÂMERA
# ------------------------------------------------------------
def inicializar_camera():
    """
    Tenta abrir câmera usando vários backends no Windows.
    """
    indices = [0, 1]
    if platform.system() == "Windows":
        tentativas = [(i, cv2.CAP_MSMF) for i in indices] + [(i, cv2.CAP_DSHOW) for i in indices]
    else:
        tentativas = [(i, cv2.CAP_ANY) for i in indices]

    print("Tentando abrir câmera...")
    for idx, be in tentativas:
        nome = "MSMF" if be == cv2.CAP_MSMF else ("DSHOW" if be == cv2.CAP_DSHOW else "ANY")
        print(f"  → tentando índice {idx} backend {nome}")
        cap = cv2.VideoCapture(idx, be)
        if cap.isOpened():
            print(f"Sucesso: câmera aberta em {idx} ({nome})")
            return cap
        cap.release()

    print("Não foi possível abrir a câmera.")
    return None


# ------------------------------------------------------------
# LOOP PRINCIPAL
# ------------------------------------------------------------
def mostrar_feed_camera(cap):
    garantir_csv()
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
                        log_csv(texto, conf)
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
                        log_csv(texto, 0.0)
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
