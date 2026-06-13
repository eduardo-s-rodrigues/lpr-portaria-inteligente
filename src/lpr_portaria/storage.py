import csv
from datetime import datetime

CSV_PATH = "entradas.csv"


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
