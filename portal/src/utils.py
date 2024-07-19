from flask import abort, session
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import string
import secrets
import hashlib
import os

load_dotenv()


def login_required(func):
    def wrapper(*args, **kwargs):
        if not "email" in session:
            abort(401, "Unauthorized to perform action!")
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


def hash_with_pepper(credentials: str):
    peppered_cred = credentials + os.getenv("PEPPER")

    hashed_cred = hashlib.sha256(peppered_cred.encode()).hexdigest()
    return hashed_cred


def generate_verification_code():
    characters = string.ascii_letters + string.digits
    verification_code = ''.join(secrets.choice(characters) for _ in range(8))

    return verification_code


def send_verification_email(reciever_email: str, code: str):
    msg = MIMEMultipart()

    msg['From'] = os.getenv("SENDER_EMAIL")
    msg['To'] = reciever_email
    msg['Subject'] = "Verify Your Email Address for Healthcare API Service"

    content = f"""
<html lang="en">
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">

    <p><strong>Dear User,</strong></p>

    <p>Thank you for signing up for Healthcare API Service! Before you can start using our platform, we need to verify your email address to ensure the security of your account.</p>

    <p>To complete the verification process, please use the following verification code:</p>

    <p>Verification Code: <strong>{code}</strong></p>

    <p>Include this code as a parameter when sending a request to the <strong>/verify</strong> endpoint. Once verified, your email address will be confirmed, and you can proceed to use our API services.</p>

    <p>Thank you for choosing Our Healthcare API Service. We look forward to serving you!</p>

</body>
</html>

    """

    msg.attach(MIMEText(content, "html"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()

    server.login(os.getenv("SENDER_EMAIL"), os.getenv("SENDER_PASSWORD"))
    server.sendmail(os.getenv("SENDER_EMAIL"), reciever_email, msg.as_string())

    server.quit()


def send_apikey_email(reciever_email: str, api_key: str):
    msg = MIMEMultipart()

    msg['From'] = os.getenv("SENDER_EMAIL")
    msg['To'] = reciever_email
    msg['Subject'] = "API Key for Healthcare Services API"

    content = f"""
<html lang="en">
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">

    <p><strong>Dear User,</strong></p>

    <p>This is your Secret API Key for 'Healthcare API Service': <strong>{api_key}</strong></p>

    <pKeep this key secure and safe. Do not share it with anyone. If you suspect that your key has been stolen then you can get a new one by logging into your portal.</p>

    <p>Thank you for choosing Our Healthcare API Service. We look forward to serving you!</p>

</body>
</html>
    """

    msg.attach(MIMEText(content, "html"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()

    server.login(os.getenv("SENDER_EMAIL"), os.getenv("SENDER_PASSWORD"))
    server.sendmail(os.getenv("SENDER_EMAIL"), reciever_email, msg.as_string())

    server.quit()