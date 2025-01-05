import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_KEY")
twilio_sid = os.getenv("TWILIO_ACC_SID")
twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_no = os.getenv("TWILIO_NO")
ngrok_url = "https://a0fe-2405-201-c417-9020-3829-2aa5-886-482e.ngrok-free.app"
ngrok_auth_token = os.getenv("NGROK_AUTH_TOKEN")
# customer_no = "+918017727622"
customer_no = "+919704100431"
real_agent_no = os.getenv("REAL_AGENT_NO")

SYSTEM_MESSAGE = (
    "You are a helpful and bubbly AI assistant who loves to chat about "
    "anything the user is interested in and is prepared to offer them facts. "
    "You have a penchant for dad jokes, owl jokes, and rickrolling – subtly. "
    "Always stay positive, but work in a joke when appropriate."
)
VOICE = 'alloy'
LOG_EVENT_TYPES = [
    'error', 'response.content.done', 'rate_limits.updated',
    'response.done', 'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped', 'input_audio_buffer.speech_started',
    'session.created'
]
SHOW_TIMING_MATH = False
PORT = 8000

WEB_SR = 44100
TWILIO_SR = 8000
