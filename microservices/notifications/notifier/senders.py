"""
Envoi des e-mails. Le mode est choisi par la variable EMAIL_MODE :

  mailpit    SMTP vers une fausse boite mail (developpement local)
  acs        vrais e-mails via Azure Communication Services
  simulated  aucun envoi, la notification est seulement enregistree
"""

import smtplib
from email.message import EmailMessage
from email.utils import formataddr

MODES = ('mailpit', 'acs', 'simulated')


class ConfigError(RuntimeError):
    pass


class SimulatedSender:
    mode = 'simulated'
    success_status = 'simulated'

    def send(self, email, name, message):
        pass


class SmtpSender:
    mode = 'mailpit'
    success_status = 'sent'

    def __init__(self, host, port, sender):
        self.host, self.port, self.sender = host, port, sender

    def send(self, email, name, message):
        mail = EmailMessage()
        mail['From'] = self.sender
        mail['To'] = formataddr((name, email))
        mail['Subject'] = message.subject
        mail.set_content(message.text)
        mail.add_alternative(message.html, subtype='html')
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.send_message(mail)


class AcsSender:
    mode = 'acs'
    success_status = 'sent'

    def __init__(self, connection_string, sender_address):
        from azure.communication.email import EmailClient
        self.client = EmailClient.from_connection_string(connection_string)
        self.sender_address = sender_address

    def send(self, email, name, message):
        poller = self.client.begin_send({
            'senderAddress': self.sender_address,
            'recipients': {'to': [{'address': email, 'displayName': name}]},
            'content': {
                'subject': message.subject,
                'plainText': message.text,
                'html': message.html,
            },
        })
        result = poller.result()
        status = result.get('status') if isinstance(result, dict) else getattr(result, 'status', None)
        if str(status).lower() != 'succeeded':
            raise RuntimeError(f'ACS a refuse l\'envoi (statut {status})')


def build_sender(env):
    mode = env.get('EMAIL_MODE', 'simulated').strip().lower()
    if mode == 'simulated':
        return SimulatedSender()
    if mode == 'mailpit':
        return SmtpSender(
            host=env.get('SMTP_HOST', 'localhost'),
            port=int(env.get('SMTP_PORT', '1025')),
            sender=env.get('EMAIL_FROM', 'HospiPlan <no-reply@hospiplan.local>'),
        )
    if mode == 'acs':
        conn, sender = env.get('ACS_CONNECTION_STRING'), env.get('ACS_SENDER_ADDRESS')
        if not conn or not sender:
            raise ConfigError('EMAIL_MODE=acs exige ACS_CONNECTION_STRING et ACS_SENDER_ADDRESS.')
        return AcsSender(conn, sender)
    raise ConfigError(f'EMAIL_MODE inconnu : {mode!r} (attendu : {", ".join(MODES)})')
