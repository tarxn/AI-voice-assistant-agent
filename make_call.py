
import os
from twilio.rest import Client
import requests
from config import twilio_sid, twilio_no, twilio_token, ngrok_url, customer_no

account_sid = twilio_sid
auth_token = twilio_token
client = Client(account_sid, auth_token)

ai_stream_url = f"{ngrok_url}/incoming-call"
test_incoming_call = f"{ngrok_url}/calls/incoming"

call = client.calls.create(
  url= ai_stream_url,
  to= f"{customer_no}",
  from_=f"{twilio_no}",
)

response = requests.post(f"{ngrok_url}/get-callSid?sid={call.sid}")

if response.status_code == 200:
    print(response.json())
else:
    print("Failed to send CallSid:", response.text)