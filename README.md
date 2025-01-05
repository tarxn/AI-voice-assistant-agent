# AI-Human-voice-agent
uvicorn service.main:app --host 0.0.0.0 --port 8000 --reload
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

ngrok http 8000


## Processing Twilio Audio

### From Twilio (Decoding)

1. **Base64 Decode**:
   - The incoming audio is Base64-encoded, so it must be decoded into raw bytes.

2. **Mu-Law Decode**:
   - The decoded bytes represent 8-bit Mu-Law samples, which need to be expanded back into linear PCM values (e.g., `float32` or `int16`).

3. **Optional Resampling**:
   - If your application works with a different sampling rate (e.g., 48 kHz), the audio must be resampled.

---

### To Twilio (Encoding)

1. **Optional Resampling**:
   - If your audio processing system works at a higher sampling rate (e.g., 48 kHz), the audio must be resampled to 8 kHz.

2. **Mu-Law Encode**:
   - Convert the linear PCM audio into 8-bit Mu-Law encoded samples.

3. **Base64 Encode**:
   - Encode the Mu-Law samples as a Base64 string to send to Twilio.

