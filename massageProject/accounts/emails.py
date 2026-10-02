from massageProject.main_app.email_context import build_email


def send_otp_email(email, code):
    build_email('otp_email', email, {'code': code}).send()
