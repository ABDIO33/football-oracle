"""
TEST IMAP ACCESS TO GMAIL
"""
import imaplib, email, re, os

os.chdir("C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor")

print("[1] Testing IMAP connection to Gmail...")
try:
    mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
    mail.login('elbazamine27@gmail.com', 'ABDO1122334455')
    print("    ✅ IMAP LOGIN SUCCESSFUL!")
    
    mail.select('INBOX')
    
    # Check total messages
    status, total = mail.search(None, 'ALL')
    if status == 'OK':
        ids = total[0].split()
        print(f"    📧 Total inbox: {len(ids)} emails")
    
    # Search for football-data.org
    status, msgs = mail.search(None, 'FROM', 'football-data.org')
    if status == 'OK':
        ids = msgs[0].split()
        print(f"    ⚽ From football-data.org: {len(ids)} emails")
        for i in ids[-10:]:
            status, data = mail.fetch(i, '(RFC822)')
            if status == 'OK':
                msg = email.message_from_bytes(data[0][1])
                subj = msg['Subject']
                print(f"      📨 {subj}")
                # Get body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == 'text/plain':
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            break
                else:
                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                
                # Find API key
                keys = re.findall(r'[A-Za-z0-9]{25,45}', body)
                if keys:
                    print(f"      🔑 KEY: {keys[0]}")
                else:
                    print(f"      📝 Body: {body[:150]}")
    
    # Search for NewsAPI
    status, msgs = mail.search(None, 'FROM', 'newsapi')
    if status == 'OK':
        ids = msgs[0].split()
        print(f"\n    📰 From NewsAPI: {len(ids)} emails")
        for i in ids[-5:]:
            status, data = mail.fetch(i, '(RFC822)')
            if status == 'OK':
                msg = email.message_from_bytes(data[0][1])
                print(f"      📨 {msg['Subject']}")
    
    # Search for API KEY
    status, msgs = mail.search(None, 'SUBJECT', 'API')
    if status == 'OK':
        ids = msgs[0].split()
        print(f"\n    🔑 With 'API' in subject: {len(ids)} emails")
        for i in ids[-5:]:
            status, data = mail.fetch(i, '(RFC822)')
            if status == 'OK':
                msg = email.message_from_bytes(data[0][1])
                print(f"      📨 {msg['Subject']}")
    
    mail.logout()
    
except Exception as e:
    print(f"    ❌ IMAP Failed: {e}")
    print("    Trying browser approach instead...")

print("\n[2] Checking existing state...")
import json
if os.path.exists('api_keys/keys_collected.json'):
    with open('api_keys/keys_collected.json') as f:
        data = json.load(f)
    print(f"    Existing registrations: {len(data)}")
    for d in data:
        print(f"    {d['service']}: {d['email']} [{d['status']}]")
else:
    print("    No existing keys file")
