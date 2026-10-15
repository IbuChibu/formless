export type VoiceInterruptionDetector = {
  stop: () => void;
};

export type VoiceActivityGateState = {
  calibrationStartedAt: number | null;
  sampleCount: number;
  noiseFloor: number;
  activeSince: number | null;
  armed: boolean;
};

type VoiceActivityGateResult = {
  state: VoiceActivityGateState;
  becameArmed: boolean;
  detected: boolean;
};

type VoiceInterruptionDetectorOptions = {
  onArmed: () => void;
  onVoice: () => void;
  onError: (message: string) => void;
};

const CALIBRATION_MS = 700;
const REQUIRED_ACTIVITY_MS = 180;
const MINIMUM_ACTIVITY_LEVEL = 0.028;
const NOISE_MULTIPLIER = 2.4;
const NOISE_MARGIN = 0.014;

declare global {
  interface Window {
    webkitAudioContext?: typeof AudioContext;
  }
}

export function browserSupportsVoiceInterruption(): boolean {
  const AudioContextConstructor =
    window.AudioContext ?? window.webkitAudioContext;
  return Boolean(
    window.isSecureContext &&
      typeof navigator.mediaDevices?.getUserMedia === "function" &&
      AudioContextConstructor,
  );
}

export function initialVoiceActivityGateState(): VoiceActivityGateState {
  return {
    calibrationStartedAt: null,
    sampleCount: 0,
    noiseFloor: 0,
    activeSince: null,
    armed: false,
  };
}

export function updateVoiceActivityGate(
  previous: VoiceActivityGateState,
  level: number,
  timestamp: number,
): VoiceActivityGateResult {
  const calibrationStartedAt =
    previous.calibrationStartedAt ?? timestamp;
  const isCalibrating =
    timestamp - calibrationStartedAt < CALIBRATION_MS;

  if (isCalibrating) {
    const sampleCount = previous.sampleCount + 1;
    const noiseFloor =
      previous.sampleCount === 0
        ? level
        : previous.noiseFloor +
          (level - previous.noiseFloor) / sampleCount;
    return {
      state: {
        calibrationStartedAt,
        sampleCount,
        noiseFloor,
        activeSince: null,
        armed: false,
      },
      becameArmed: false,
      detected: false,
    };
  }

  const threshold = Math.max(
    MINIMUM_ACTIVITY_LEVEL,
    previous.noiseFloor * NOISE_MULTIPLIER,
    previous.noiseFloor + NOISE_MARGIN,
  );
  const activeSince =
    level >= threshold ? (previous.activeSince ?? timestamp) : null;
  const detected =
    activeSince !== null && timestamp - activeSince >= REQUIRED_ACTIVITY_MS;
  const noiseFloor =
    level < threshold
      ? previous.noiseFloor * 0.98 + level * 0.02
      : previous.noiseFloor;

  return {
    state: {
      calibrationStartedAt,
      sampleCount: previous.sampleCount,
      noiseFloor,
      activeSince,
      armed: true,
    },
    becameArmed: !previous.armed,
    detected,
  };
}

export function startVoiceInterruptionDetector(
  options: VoiceInterruptionDetectorOptions,
): VoiceInterruptionDetector {
  let stopped = false;
  let animationFrame: number | null = null;
  let stream: MediaStream | null = null;
  let audioContext: AudioContext | null = null;
  let source: MediaStreamAudioSourceNode | null = null;

  const stop = () => {
    if (stopped) {
      return;
    }
    stopped = true;
    if (animationFrame !== null) {
      window.cancelAnimationFrame(animationFrame);
      animationFrame = null;
    }
    source?.disconnect();
    source = null;
    stream?.getTracks().forEach((track) => track.stop());
    stream = null;
    if (audioContext && audioContext.state !== "closed") {
      void audioContext.close().catch(() => undefined);
    }
    audioContext = null;
  };

  const fail = (error: unknown) => {
    if (stopped) {
      return;
    }
    const message = interruptionErrorMessage(error);
    stop();
    options.onError(message);
  };

  const start = async () => {
    if (!browserSupportsVoiceInterruption()) {
      fail(
        new Error(
          "Hands-free interruption is unavailable in this browser. Use Answer now or type your reply.",
        ),
      );
      return;
    }

    try {
      const nextStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          autoGainControl: true,
          echoCancellation: true,
          noiseSuppression: true,
        },
        video: false,
      });
      if (stopped) {
        nextStream.getTracks().forEach((track) => track.stop());
        return;
      }
      stream = nextStream;

      const AudioContextConstructor =
        window.AudioContext ?? window.webkitAudioContext;
      if (!AudioContextConstructor) {
        throw new Error(
          "Hands-free interruption is unavailable in this browser. Use Answer now or type your reply.",
        );
      }
      audioContext = new AudioContextConstructor();
      if (audioContext.state === "suspended") {
        await audioContext.resume();
      }
      if (stopped) {
        stop();
        return;
      }

      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.15;
      source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);

      const samples = new Float32Array(analyser.fftSize);
      let gate = initialVoiceActivityGateState();

      const sample = (timestamp: number) => {
        if (stopped) {
          return;
        }
        analyser.getFloatTimeDomainData(samples);
        const result = updateVoiceActivityGate(
          gate,
          rootMeanSquare(samples),
          timestamp,
        );
        gate = result.state;
        if (result.becameArmed) {
          options.onArmed();
        }
        if (result.detected) {
          stop();
          options.onVoice();
          return;
        }
        animationFrame = window.requestAnimationFrame(sample);
      };

      animationFrame = window.requestAnimationFrame(sample);
    } catch (error) {
      fail(error);
    }
  };

  void start();
  return { stop };
}

function rootMeanSquare(samples: Float32Array): number {
  let sumOfSquares = 0;
  for (const sample of samples) {
    sumOfSquares += sample * sample;
  }
  return Math.sqrt(sumOfSquares / samples.length);
}

function interruptionErrorMessage(error: unknown): string {
  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError" || error.name === "SecurityError") {
      return "Hands-free interruption is off because microphone access was not allowed. Use Answer now or type your reply.";
    }
    if (error.name === "NotFoundError") {
      return "Hands-free interruption could not find a microphone. Use Answer now or type your reply.";
    }
    if (error.name === "NotReadableError") {
      return "Hands-free interruption could not use the microphone right now. Use Answer now or type your reply.";
    }
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Hands-free interruption could not start. Use Answer now or type your reply.";
}
