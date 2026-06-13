import re

import cv2
import numpy as np
import pytesseract


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
