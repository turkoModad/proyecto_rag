from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


# ---- OTP ----
def hash_otp(otp: str) -> str:
    return pwd_context.hash(otp)


def verify_otp(otp: str, hashed_otp: str) -> bool:
    return pwd_context.verify(otp, hashed_otp)