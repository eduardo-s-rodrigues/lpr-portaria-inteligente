import platform
import cv2


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
