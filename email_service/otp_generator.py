import random

def generar_otp(digitos: int = 6) -> str:
    return ''.join(str(random.randint(0, 9)) for _ in range(digitos))