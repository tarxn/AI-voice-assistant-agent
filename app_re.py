import json
import base64
import asyncio
import websockets
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect
from config import openai_key, ngrok_auth_token, real_agent_no, PORT, SHOW_TIMING_MATH, VOICE, LOG_EVENT_TYPES, SHOW_TIMING_MATH, PORT, SYSTEM_MESSAGE

from twilio.request_validator import RequestValidator
import time
import uvicorn
from pyngrok import ngrok
from openai_stream import receive_from_twilio, send_to_twilio, initialize_session, CALL_SID
from call_stream import *

OPENAI_API_KEY = str(openai_key) 

app = FastAPI()

if not OPENAI_API_KEY:
    raise ValueError('Missing the OpenAI API key. Please set it in the .env file.')

@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}

@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    response = VoiceResponse()
    # <Say> punctuation to improve text-to-speech flow
    # response.say("You are speaking with an AI voice assistant, here to assist you with your queries and concerns. If at any point you wish to speak with a human agent, simply press 0 to connect.")
    # response.pause(length=1)
    response.say("you can start talking now!")
    host = request.url.hostname
    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream')
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.api_route("/get-callSid", methods=["POST"])
async def set_call_sid(sid: str):
    """Endpoint to set the global CallSid."""
    try:
        CALL_SID = sid 
        print(f"CallSid set globally: {CALL_SID}")
        return {"callSid": CALL_SID}
    except Exception as e:
        print(f"Error setting CallSid: {e}")
        return {"error": str(e)}

@app.get("/calls", response_class=HTMLResponse)
async def serve_frontend():
    file_path = "index.html"
    return FileResponse(file_path)

# @app.websocket("/call-stream")
# async def call_stream(websocket: WebSocket):
#     # global audio_buffer_raw
#     # global audio_buffer_res
#     stream_sid = None
#     try:
#         await websocket.accept()
#         print("WebSocket connection established.")

#         while True:
#             # Receive Twilio events
#             message = await websocket.receive_text()
#             data = json.loads(message)
#             # print("output msg:", data)
#             if data['event'] == 'start':
#                 stream_sid = data['start']['streamSid']
#                 # print(f"Stream started with StreamSid: {stream_sid}")

#             elif data['event'] == 'media' and stream_sid:
#                 audio_chunk = input_stream.read(CHUNK, exception_on_overflow=False)
#                 # audio_buffer_raw.extend(audio_chunk)
               
#                 encoded_audio = process_audio_librosa(audio_chunk)
#                 # audio_buffer_res.extend(encoded_audio)

#                 # Create and send media event
#                 outbound_message = {
#                     "event": "media",
#                     "streamSid": stream_sid,
#                     "media": {
#                         "payload": encoded_audio
#                     }
#                 }
#                 await websocket.send_text(json.dumps(outbound_message))
#                 print(f"Sending outbound message: {json.dumps(outbound_message, indent=2)}")
#                 try:
#                     encoded_audio = data['media']['payload']
#                     playback_audio = process_incoming_audio(encoded_audio)
#                     play_audio_chunk(playback_audio.tobytes())
#                 except Exception as e:
#                     print(f"Error with incoming audio: {e}")

#             elif data['event'] == 'stop':
#                 print(f"Stream stopped for StreamSid: {stream_sid}")
#                 break

#     except Exception as e:
#         print(f"Error during WebSocket communication: {e}")
#     finally:
#         try:
#             if input_stream.is_active():
#                 input_stream.stop_stream()
#             if output_stream.is_active():
#                 output_stream.stop_stream()
#         except Exception as e:
#             print(f"Error stopping streams: {e}")
#         finally:
#             input_stream.close()
#             output_stream.close()
#             audio.terminate()
#             await websocket.close()
#             print("WebSocket connection and streams closed.")
#             #  save_audio(audio_buffer_res, filename="complete_audio_stream_res.wav", rate=TWILIO_SAMPLING_RATE)


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI."""
    print("Client connected")
    await websocket.accept()

    async with websockets.connect(
        'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
    ) as openai_ws:
        await initialize_session(openai_ws)

        # Connection specific state
        stream_sid = None
        latest_media_timestamp = 0
        last_assistant_item = None
        mark_queue = []
        response_start_timestamp_twilio = None
        
        async def receive_from_twilio():
            """Receive audio data from Twilio and send it to the OpenAI Realtime API."""
            nonlocal stream_sid, latest_media_timestamp
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    print("input message: ", data)
                    if data['event']== 'dtmf' : 
                        print("dtmf data", data)
                    if data['event'] == 'media' and openai_ws.open:
                        latest_media_timestamp = int(data['media']['timestamp'])
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data['media']['payload']
                        }
                        await openai_ws.send(json.dumps(audio_append))
                    elif data['event'] == 'start':
                        stream_sid = data['start']['streamSid']
                        print(f"Incoming stream has started {stream_sid}")
                        response_start_timestamp_twilio = None
                        latest_media_timestamp = 0
                        last_assistant_item = None
                    elif data['event'] == 'mark':
                        if mark_queue:
                            mark_queue.pop(0)
                        # pass
                    elif data['event'] == 'dtmf':
                        print("DTMF event detected:", data)  # Debugging
                        if "digit" in data['dtmf'] and data['dtmf']['digit'] == '0':
                            print("User pressed 0 to talk to a human.")
                            if CALL_SID:
                                await bridge_to_human(CALL_SID)
                                break
            except WebSocketDisconnect:
                print("Client disconnected.")
                if openai_ws.open:
                    await openai_ws.close()

        async def bridge_to_human(stream_sid):
            print(f"Redirecting to TwiML function for bridging...{stream_sid}")

            from twilio.rest import Client
            try:
                # Close the AI WebSocket connection
                if openai_ws.open:
                    print("Closing the AI WebSocket...")
                    await openai_ws.close()

                account_sid = "AC72ec7a32ee399c84e26f9bd55aefc2c5"
                auth_token = "223dcceed21ed24600dada97cd92aba5"
                client = Client(account_sid, auth_token)
                # client.calls(stream_sid).update(
                #     twiml='''
                #     <Response>
                #         <Say>Connecting you to a human agent. Please hold.</Say>
                #         <Connect>
                #             <Stream url="wss://e1ed-2405-201-c417-9020-c19f-9786-96c4-4b91.ngrok-free.app/call-stream"/>
                #         </Connect>
                #     </Response>
                #     '''
                # )
                client.calls(stream_sid).update(
                    twiml='''
                    <Response>
                            <Say>Connecting you to a human agent. Please hold.</Say>
                            <Dial>
                                <Number>
                                    +918897314158
                                </Number>
                            </Dial>
                    </Response>
                    '''
                )
                print(f"Call bridged to human for stream SID: {stream_sid}")
            except Exception as e:
                print(f"Error during bridging: {e}")


        async def send_to_twilio():
            """Receive events from the OpenAI Realtime API, send audio back to Twilio."""
            nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    print("output dataxd:", response)
                    if response['type'] in LOG_EVENT_TYPES:
                        print(f"Received event: {response['type']}", response)

                    if response.get('type') == 'response.audio.delta' and 'delta' in response:
                        audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                        audio_delta = {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": audio_payload
                            }
                        }
                        await websocket.send_json(audio_delta)

                        if response_start_timestamp_twilio is None:
                            response_start_timestamp_twilio = latest_media_timestamp
                            if SHOW_TIMING_MATH:
                                print(f"Setting start timestamp for new response: {response_start_timestamp_twilio}ms")

                        # Update last_assistant_item safely
                        if response.get('item_id'):
                            last_assistant_item = response['item_id']

                        await send_mark(websocket, stream_sid)

                    # Trigger an interruption. Your use case might work better using `input_audio_buffer.speech_stopped`, or combining the two.
                    if response.get('type') == 'input_audio_buffer.speech_started':
                        print("Speech started detected.")
                        if last_assistant_item:
                            print(f"Interrupting response with id: {last_assistant_item}")
                            await handle_speech_started_event()
            except Exception as e:
                print(f"Error in send_to_twilio: {e}")

        async def handle_speech_started_event():
            """Handle interruption when the caller's speech starts."""
            nonlocal response_start_timestamp_twilio, last_assistant_item
            print("Handling speech started event.")
            if mark_queue and response_start_timestamp_twilio is not None:
                elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
                if SHOW_TIMING_MATH:
                    print(f"Calculating elapsed time for truncation: {latest_media_timestamp} - {response_start_timestamp_twilio} = {elapsed_time}ms")

                if last_assistant_item:
                    if SHOW_TIMING_MATH:
                        print(f"Truncating item with ID: {last_assistant_item}, Truncated at: {elapsed_time}ms")

                    truncate_event = {
                        "type": "conversation.item.truncate",
                        "item_id": last_assistant_item,
                        "content_index": 0,
                        "audio_end_ms": elapsed_time
                    }
                    await openai_ws.send(json.dumps(truncate_event))

                await websocket.send_json({
                    "event": "clear",
                    "streamSid": stream_sid
                })

                mark_queue.clear()
                last_assistant_item = None
                response_start_timestamp_twilio = None

        async def send_mark(connection, stream_sid):
            if stream_sid:
                mark_event = {
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": "responsePart"}
                }
                await connection.send_json(mark_event)
                mark_queue.append('responsePart')

        await asyncio.gather(receive_from_twilio(), send_to_twilio())


async def initialize_session(openai_ws):
    """Control initial session with OpenAI."""
    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": SYSTEM_MESSAGE,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
        }
    }
    print('Sending session update:', json.dumps(session_update))
    await openai_ws.send(json.dumps(session_update))


async def start_ngrok():
    print("Starting Ngrok...")
    ngrok.set_auth_token(f"{ngrok_auth_token}")
    public_url = ngrok.connect(PORT)
    print(f"Ngrok Tunnel URL: {public_url}")
    return public_url

async def run_uvicorn():
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(start_ngrok(), run_uvicorn())

if __name__ == "__main__":
    asyncio.run(main())