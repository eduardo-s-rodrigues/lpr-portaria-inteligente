import cv2
import numpy as np


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
