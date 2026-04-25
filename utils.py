import random

def generate_otp():
    return str(random.randint(1000, 9999))

def send_sms_otp(mobile, otp):
    print("\n" + "="*40)
    print(f"       GOVERNMENT SMS GATEWAY")
    print(f"TO: {mobile}")
    print(f"MESSAGE: {otp} is your secret login OTP.")
    print("="*40 + "\n")