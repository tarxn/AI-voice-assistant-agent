import wave
import librosa
import os
import numpy as np
import pyaudio
from twilio.request_validator import RequestValidator
import time

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
TWILIO_SAMPLING_RATE = 8000
LAPTOP_SAMPLING_RATE = 48000

audio = pyaudio.PyAudio()
input_stream = audio.open(format=FORMAT, channels=CHANNELS, rate=LAPTOP_SAMPLING_RATE, input=True, frames_per_buffer=CHUNK)
output_stream = audio.open(format=FORMAT, channels=CHANNELS, rate=LAPTOP_SAMPLING_RATE, output=True)

# Save the resampled audio for testing
def resample_audio(audio_chunk, original_rate=48000, target_rate=8000):
    import numpy as np
    import librosa
    
    audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
    resampled_audio = librosa.resample(audio_data.astype(np.float32), orig_sr=original_rate, target_sr=target_rate)
    print("resampled_audio hg:", resampled_audio)
    return resampled_audio.astype(np.int16).tobytes()

def resample_audio_input(audio_chunk, original_rate=44100, target_rate=8000):
    """
    Resample audio to the target rate using Librosa.
    """
    audio_data = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
    resampled_audio = librosa.resample(audio_data, orig_sr=original_rate, target_sr=target_rate)
    return resampled_audio.astype(np.float32)



def save_audio(data, filename="complete_audio_stream.wav", rate=TWILIO_SAMPLING_RATE):
    try:
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.get_sample_size(FORMAT))
            wf.setframerate(rate)
            wf.writeframes(data)
        print(f"Complete audio saved successfully to {filename}")
    except Exception as e:
        print(f"Failed to save audio: {e}")


def process_audio_librosa(audio_chunk, original_rate=48000, target_rate=8000):
    """
    Full audio processing pipeline using Librosa.
    """
    # Resample audio
    resampled_audio = resample_audio_input(audio_chunk, original_rate, target_rate)

    # Apply simple noise reduction
    noise_reduced_audio = noise_reduction_librosa(resampled_audio, threshold=0.01)

    # Convert to Mu-Law
    mulaw_audio = pcm_to_mulaw(noise_reduced_audio)

    # Base64 encode for Twilio
    encoded_audio = base64.b64encode(mulaw_audio).decode("utf-8")
    return encoded_audio

def noise_reduction_librosa(audio, threshold=0.01):
    """
    Reduce noise by muting values below a threshold.
    """
    return np.where(np.abs(audio) < threshold, 0, audio)

def pcm_to_mulaw(audio, quantization_channels=256):
    """
    Convert PCM audio to Mu-Law encoded audio.
    """
    mu = quantization_channels - 1
    # Normalize audio between -1 and 1
    audio = np.clip(audio / np.max(np.abs(audio)), -1, 1)
    # Apply Mu-Law transformation
    audio_mu = np.sign(audio) * np.log1p(mu * np.abs(audio)) / np.log1p(mu)
    # Quantize to 8-bit unsigned integer
    audio_mu = ((audio_mu + 1) / 2 * mu + 0.5).astype(np.uint8)
    return audio_mu

# audio_buffer_raw = bytearray()
# audio_buffer_res = bytearray()

def resample_audio_output(audio_chunk, original_rate=8000, target_rate=48000):
    """
    Resample audio to the target rate for playback.
    """
    import numpy as np
    import librosa

    audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
    resampled_audio = librosa.resample(audio_data.astype(np.float32), orig_sr=original_rate, target_sr=target_rate)
    return resampled_audio.astype(np.int16).tobytes()


def play_audio_chunk(audio_chunk):
    """
    Play the audio chunk through the output stream.
    """
    try:
        output_stream.write(audio_chunk)
    except Exception as e:
        print(f"Error while playing audio: {e}")

import numpy as np
import base64
import librosa

def mulaw_decode(mu_law_audio, quantization_channels=256):
    """
    Decode Mu-Law encoded audio back to PCM format.
    """
    print(f"mulaw_decode input type: {type(mu_law_audio)}")
    if isinstance(mu_law_audio, bytes):
        print("Converting bytes to numpy array in mulaw_decode.")
        mu_law_audio = np.frombuffer(mu_law_audio, dtype=np.uint8)
    elif not isinstance(mu_law_audio, np.ndarray):
        raise ValueError("Input to mulaw_decode must be a numpy array or bytes")

    mu = quantization_channels - 1
    mu_law_audio = mu_law_audio.astype(np.float32)  # Convert to float32 for computation
    audio = (mu_law_audio / mu) * 2 - 1  # Normalize between -1 and 1

    # Clamp the input to the valid range
    audio = np.clip(audio, -1, 1)

    # Handle expm1 safely to avoid numerical issues
    abs_audio = np.abs(audio)
    exp_safe = np.where(
        mu * abs_audio < 700,  # Prevent overflow
        np.expm1(mu * abs_audio),
        np.exp(700)  # Approximate large values
    )

    pcm_audio = np.sign(audio) * (1 / mu) * exp_safe
    return pcm_audio



def validate_audio(audio_data):
    """
    Ensure audio data is finite. Replace NaN/Inf values with zeros.
    """
    audio_data = np.nan_to_num(audio_data, nan=0.0, posinf=0.0, neginf=0.0)
    print("audio_data xd:", audio_data)
    if not np.all(np.isfinite(audio_data)):
        raise ValueError("Audio buffer contains invalid values.")
    return audio_data


import traceback 

def process_incoming_audio(encoded_audio):
    """
    Process incoming audio from Twilio.
    """
    try:
        # Decode Base64 to bytes
        print(f"Processing incoming audio. Type: {type(encoded_audio)}")
        decoded_bytes = base64.b64decode(encoded_audio)
        print(f"Decoded bytes type: {type(decoded_bytes)}, length: {len(decoded_bytes)}")

        # Convert decoded bytes to numpy array
        mu_law_audio = np.frombuffer(decoded_bytes, dtype=np.uint8)
        print(f"Mu-Law audio before decode: Type: {type(mu_law_audio)}, Shape: {mu_law_audio.shape}")

        # Decode Mu-Law to PCM
        pcm_audio = mulaw_decode(mu_law_audio)
        print(f"Decoded PCM audio shape: {pcm_audio.shape}, dtype: {pcm_audio.dtype}")

        # Validate and sanitize audio
        pcm_audio = validate_audio(pcm_audio)

        # Resample to system playback rate (e.g., 48kHz)
        resampled_audio = resample_audio(pcm_audio, original_rate=8000, target_rate=48000)

        # Convert to int16 for playback
        return resampled_audio * 32767

    except Exception as e:
        traceback.print_exc()
        print(f"Error processing incoming audio: {e}")
        raise