import qrcode
import os

def generate_qr(data: str, filename: str):
    folder = "qrcodes"
    os.makedirs(folder, exist_ok=True)

    file_path = os.path.join(folder, f"{filename}.png")

    img = qrcode.make(data)
    img.save(file_path)

    return file_path