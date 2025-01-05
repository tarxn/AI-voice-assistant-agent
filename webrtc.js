async function startWebRTC() {
    const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(audioStream);
    const destination = audioContext.createMediaStreamDestination();

    const ws = new WebSocket('wss://dcb9-2405-201-c417-9020-406b-bc7c-b204-2d99.ngrok-free.app/call-stream');
    ws.binaryType = 'arraybuffer';

    // Send audio data to the WebSocket
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (event) => {
        const inputBuffer = event.inputBuffer.getChannelData(0);
        ws.send(inputBuffer);
    };
    source.connect(processor);
    processor.connect(audioContext.destination);

    // Receive audio from the WebSocket
    ws.onmessage = (message) => {
        const audioBuffer = message.data; // Expect raw PCM data
        playAudio(audioBuffer, audioContext);
    };

    async function playAudio(data, audioCtx) {
        const buffer = await audioCtx.decodeAudioData(data);
        const bufferSource = audioCtx.createBufferSource();
        bufferSource.buffer = buffer;
        bufferSource.connect(audioCtx.destination);
        bufferSource.start();
    }
}
startWebRTC();
