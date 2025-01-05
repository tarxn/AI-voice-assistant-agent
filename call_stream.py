from scipy.signal import resample
import numpy as np
import audioop
import base64
import pyaudio
import samplerate
import librosa

def resample_audio(data, input_rate, output_rate):
    ratio = output_rate / input_rate
    return samplerate.resample(data, ratio, 'sinc_best').astype(np.int16)

def twilio_audio_encoded_chunk(audio_chunk, input_sample_rate=44100, output_sample_rate=8000):

    audio_data = np.frombuffer(audio_chunk, dtype=np.int16)

    num_output_samples = int(len(audio_data) * (output_sample_rate / input_sample_rate))

    resampled_data = resample(audio_data, num_output_samples).astype(np.int16)

    mulaw_encoded_data = audioop.lin2ulaw(resampled_data.tobytes(), 2)  

    base64_encoded_data = base64.b64encode(mulaw_encoded_data).decode('utf-8')

    return base64_encoded_data

def web_audio_decoded_chunk(audio_chunk, input_sample_rate=8000, output_sample_rate=44100):
    mu_law_audio = base64.b64decode(audio_chunk)
    print(f"[DEBUG] Decoded Base64 audio: {len(mu_law_audio)} bytes")

    linear_audio = np.frombuffer(audioop.ulaw2lin(mu_law_audio, 2), dtype=np.int16)
    print(f"[DEBUG] Converted Mu-Law to Linear PCM: {len(linear_audio)} samples")
    
    linear_audio = linear_audio.astype(np.float32) / np.iinfo(np.int16).max 
    
    if input_sample_rate != output_sample_rate:
        try:
            linear_audio_resampled = librosa.resample(linear_audio, orig_sr=input_sample_rate, target_sr=output_sample_rate)
            print(f"[DEBUG] Resampled audio to {output_sample_rate} Hz: {len(linear_audio_resampled)} samples")
        except Exception as e:
            raise ValueError(f"Error resampling audio with librosa: {e}")
    else:
        linear_audio_resampled = linear_audio
    
    linear_audio_resampled = (linear_audio_resampled * np.iinfo(np.int16).max).astype(np.int16)
    
    return linear_audio_resampled

# Corrected function for playback
def playback_audio(linear_pcm_data, sample_rate, channels=1, sample_width=2):
    p = pyaudio.PyAudio()
    try:
        stream = p.open(format=p.get_format_from_width(sample_width),
                        channels=channels,
                        rate=sample_rate,
                        output=True)

        stream.write(linear_pcm_data.tobytes())
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

def normalize_audio(audio):
    audio = np.array(audio, dtype=np.int16)
    max_amplitude = np.max(np.abs(audio))
    if max_amplitude > 0:
        scale_factor = 32767 / max_amplitude
        audio = (audio * scale_factor).astype(np.int16)
    return audio