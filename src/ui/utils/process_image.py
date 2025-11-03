import base64


def encode_image_to_base64(image_path):
    """Convierte imagen a base64"""
    with open(image_path, "rb") as img:
        encoded_string = base64.b64encode(img.read())
    return encoded_string.decode('utf-8')