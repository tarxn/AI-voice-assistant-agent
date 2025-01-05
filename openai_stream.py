from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect
import base64
import asyncio
import os
import json
from call_stream import bridge_to_human
from config import SHOW_TIMING_MATH, VOICE, LOG_EVENT_TYPES, SHOW_TIMING_MATH, PORT, OPENAI_API_KEY

CALL_SID = None

# Connection specific state
stream_sid = None
latest_media_timestamp = 0
last_assistant_item = None
mark_queue = []
response_start_timestamp_twilio = None

async def receive_from_twilio(openai_ws, websocket):
    """Receive audio data from Twilio and send it to the OpenAI Realtime API."""
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


async def send_to_twilio(openai_ws, websocket):
            """Receive events from the OpenAI Realtime API, send audio back to Twilio."""
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
                            await handle_speech_started_event(openai_ws, websocket)
            except Exception as e:
                print(f"Error in send_to_twilio: {e}")

async def handle_speech_started_event(openai_ws, websocket):
            """Handle interruption when the caller's speech starts."""
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

async def send_mark(connection, stream_sid, mark_queue):
    if stream_sid:
        mark_event = {
            "event": "mark",
            "streamSid": stream_sid,
            "mark": {"name": "responsePart"}
        }
        await connection.send_json(mark_event)
        mark_queue.append('responsePart')

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