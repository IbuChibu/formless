export type VoiceTurnAudio = {
  chunks: ArrayBuffer[];
  sampleRate: number;
};

export type PcmChunkListener = (chunk: ArrayBuffer) => void;

export type PcmCapture = {
  readonly sampleRate: number;
  readonly audioContext: AudioContext;
  readonly source: MediaStreamAudioSourceNode;
  setChunkListener: (listener: PcmChunkListener) => void;
  stop: () => void;
};

declare global {
  interface Window {
    webkitAudioContext?: typeof AudioContext;
  }
}

export const MICROPHONE_AUDIO_CONSTRAINTS: MediaTrackConstraints = {
  autoGainControl: true,
  channelCount: { ideal: 1 },
  echoCancellation: true,
  noiseSuppression: true,
};

export const PCM_SAMPLE_RATE = 16000;

const AUDIO_CHUNK_MS = 100;
const BYTES_PER_SAMPLE = 2;
const WAV_HEADER_BYTES = 44;
const PCM_PROCESSOR_NAME = "formless-pcm-capture";
// Centred so the Hamming transition band ends at the 8 kHz output Nyquist.
const ANTI_ALIAS_CUTOFF_HZ = 7200;
const ANTI_ALIAS_TRANSITION_HZ = 1600;

// Resampled here because some browsers reject a microphone stream in an
// AudioContext running at a different rate than the device.
export const PCM_WORKLET_SOURCE = `
function designAntiAliasFilter(inputRate) {
  if (inputRate <= ${PCM_SAMPLE_RATE}) {
    return new Float32Array([1]);
  }
  const taps =
    2 * Math.ceil((3.3 * inputRate) / ${ANTI_ALIAS_TRANSITION_HZ} / 2) + 1;
  const cutoff = ${ANTI_ALIAS_CUTOFF_HZ} / inputRate;
  const center = (taps - 1) / 2;
  const filter = new Float32Array(taps);
  let total = 0;
  for (let index = 0; index < taps; index += 1) {
    const offset = index - center;
    const sinc =
      offset === 0
        ? 2 * cutoff
        : Math.sin(2 * Math.PI * cutoff * offset) / (Math.PI * offset);
    const window = 0.54 - 0.46 * Math.cos((2 * Math.PI * index) / (taps - 1));
    filter[index] = sinc * window;
    total += filter[index];
  }
  return filter.map((coefficient) => coefficient / total);
}

class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.chunkSamples = Math.round(
      (${PCM_SAMPLE_RATE} * ${AUDIO_CHUNK_MS}) / 1000,
    );
    this.chunk = new Int16Array(this.chunkSamples);
    this.filled = 0;
    this.filter = designAntiAliasFilter(sampleRate);
    this.history = new Float32Array(this.filter.length);
    this.historyIndex = 0;
    this.inputSamplesPerOutput = sampleRate / ${PCM_SAMPLE_RATE};
    this.nextOutputPosition = 1;
    this.previousFiltered = 0;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel) {
      return true;
    }
    for (let index = 0; index < channel.length; index += 1) {
      const filtered = this.filterSample(channel[index]);
      while (this.nextOutputPosition <= 1) {
        this.writeOutput(
          this.previousFiltered +
            (filtered - this.previousFiltered) * this.nextOutputPosition,
        );
        this.nextOutputPosition += this.inputSamplesPerOutput;
      }
      this.nextOutputPosition -= 1;
      this.previousFiltered = filtered;
    }
    return true;
  }

  filterSample(input) {
    const size = this.history.length;
    this.historyIndex = (this.historyIndex + 1) % size;
    this.history[this.historyIndex] = input;
    let total = 0;
    let position = this.historyIndex;
    for (let tap = 0; tap < size; tap += 1) {
      total += this.filter[tap] * this.history[position];
      position = position === 0 ? size - 1 : position - 1;
    }
    return total;
  }

  writeOutput(value) {
    const sample = Math.max(-1, Math.min(1, value));
    this.chunk[this.filled] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    this.filled += 1;
    if (this.filled === this.chunkSamples) {
      this.port.postMessage(this.chunk.buffer, [this.chunk.buffer]);
      this.chunk = new Int16Array(this.chunkSamples);
      this.filled = 0;
    }
  }
}

registerProcessor("${PCM_PROCESSOR_NAME}", PcmCaptureProcessor);
`;

export function browserSupportsPcmCapture(): boolean {
  return Boolean(
    (window.AudioContext ?? window.webkitAudioContext) &&
      typeof window.AudioWorkletNode === "function",
  );
}

// Audio keeps flowing through one live capture for the whole handover, so
// moving from the interruption detector to recognition cannot open a new gap.
export async function startPcmCapture(
  stream: MediaStream,
  preRollMs = 0,
): Promise<PcmCapture> {
  const AudioContextConstructor =
    window.AudioContext ?? window.webkitAudioContext;
  if (!AudioContextConstructor) {
    throw new Error(
      "This browser could not start compatible microphone capture. Keep typing instead.",
    );
  }
  const audioContext = new AudioContextConstructor();
  try {
    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }
    await loadPcmWorklet(audioContext);
    const source = audioContext.createMediaStreamSource(stream);
    const processor = new window.AudioWorkletNode(
      audioContext,
      PCM_PROCESSOR_NAME,
      { channelCount: 1, channelCountMode: "explicit" },
    );
    source.connect(processor);
    // The processor writes no output; this connection only keeps it pulled.
    processor.connect(audioContext.destination);
    return createPcmCapture(stream, audioContext, source, processor, preRollMs);
  } catch {
    void audioContext.close().catch(() => undefined);
    throw new Error(
      "This browser could not start compatible microphone capture. Keep typing instead.",
    );
  }
}

// The WAV body is the same PCM sent to Deepgram, so a saved turn can be replayed.
export function encodeWav(audio: VoiceTurnAudio): Blob {
  const dataBytes = audio.chunks.reduce(
    (total, chunk) => total + chunk.byteLength,
    0,
  );
  const header = new DataView(new ArrayBuffer(WAV_HEADER_BYTES));
  const writeText = (offset: number, text: string) => {
    for (let index = 0; index < text.length; index += 1) {
      header.setUint8(offset + index, text.charCodeAt(index));
    }
  };
  writeText(0, "RIFF");
  header.setUint32(4, WAV_HEADER_BYTES - 8 + dataBytes, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  header.setUint32(16, 16, true);
  header.setUint16(20, 1, true);
  header.setUint16(22, 1, true);
  header.setUint32(24, audio.sampleRate, true);
  header.setUint32(28, audio.sampleRate * BYTES_PER_SAMPLE, true);
  header.setUint16(32, BYTES_PER_SAMPLE, true);
  header.setUint16(34, BYTES_PER_SAMPLE * 8, true);
  writeText(36, "data");
  header.setUint32(40, dataBytes, true);
  return new Blob([header.buffer, ...audio.chunks], { type: "audio/wav" });
}

export function downloadVoiceTurnAudio(audio: VoiceTurnAudio): void {
  const url = URL.createObjectURL(encodeWav(audio));
  const link = document.createElement("a");
  link.href = url;
  link.download = `voice-turn-${new Date().toISOString().replace(/[:.]/g, "-")}.wav`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function loadPcmWorklet(audioContext: AudioContext): Promise<void> {
  const url = URL.createObjectURL(
    new Blob([PCM_WORKLET_SOURCE], { type: "text/javascript" }),
  );
  try {
    await audioContext.audioWorklet.addModule(url);
  } finally {
    URL.revokeObjectURL(url);
  }
}

function createPcmCapture(
  stream: MediaStream,
  audioContext: AudioContext,
  source: MediaStreamAudioSourceNode,
  processor: AudioWorkletNode,
  preRollMs: number,
): PcmCapture {
  const preRollBytes =
    Math.round((PCM_SAMPLE_RATE * preRollMs) / 1000) * BYTES_PER_SAMPLE;
  let ring: ArrayBuffer[] = [];
  let ringBytes = 0;
  let listener: PcmChunkListener | null = null;
  let stopped = false;

  processor.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
    if (listener) {
      listener(event.data);
      return;
    }
    ring.push(event.data);
    ringBytes += event.data.byteLength;
    while (ring.length > 1 && ringBytes - ring[0].byteLength >= preRollBytes) {
      ringBytes -= ring[0].byteLength;
      ring.shift();
    }
  };

  return {
    sampleRate: PCM_SAMPLE_RATE,
    audioContext,
    source,
    setChunkListener: (nextListener) => {
      listener = nextListener;
      const preRoll = ring;
      ring = [];
      ringBytes = 0;
      preRoll.forEach((chunk) => nextListener(chunk));
    },
    stop: () => {
      if (stopped) {
        return;
      }
      stopped = true;
      listener = null;
      ring = [];
      ringBytes = 0;
      processor.port.onmessage = null;
      source.disconnect();
      processor.disconnect();
      stream.getTracks().forEach((track) => track.stop());
      if (audioContext.state !== "closed") {
        void audioContext.close().catch(() => undefined);
      }
    },
  };
}
