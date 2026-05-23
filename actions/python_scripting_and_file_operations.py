import os
import email
from email import policy
from imaplib import IMAP4_SSL

def python_scripting_and_file_operations():
    try:
        # Set up the IMAP server connection
        imap_server = "imap.example.com"
        username = "your_email@example.com"
        password = "your_password"

        mail = IMAP4_SSL(imap_server)
        mail.login(username, password)
        mail.select("inbox")

        # Search for unread emails
        status, data = mail.search(None, 'UNSEEN')
        if not data[0]:
            return "No unread emails found."

        latest_email_id = data[0].split()[-1]
        _, email_data = mail.fetch(latest_email_id, "(RFC822)")
        raw_email = email_data[0][1]

        # Parse the email
        msg = email.message_from_bytes(raw_email, policy=policy.default)

        # Extract the subject and sender
        subject = msg["Subject"]
        from_address = msg["From"]

        # Close the connection
        mail.close()
        mail.logout()

        return f"Latest unread email: Subject - {subject}, From - {from_address}"

    except Exception as e:
        return str(e)

# Main entry point
if __name__ == "__main__":
    result = python_scripting_and_file_operations()
    print(result)