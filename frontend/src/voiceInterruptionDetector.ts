import {
  browserSupportsPcmCapture,
  MICROPHONE_AUDIO_CONSTRAINTS,
  startPcmCapture,
  type PcmCapture,
} from "./voiceAudioCapture";

export type VoiceInterruptionDetector = {
  stop: () => void;
};

export type VoiceActivityGateState = {
  calibrationStartedAt: number | null;
  sampleCount: number;
  noiseFloor: number;
  playbackLeakageCeiling: number;
  activeSince: number | null;
  activeSampleCount: number;
  speechLikeSampleCount: number;
  activeMinimumLevel: number;
  activeMaximumLevel: number;
  armed: boolean;
};

export type VoiceActivitySample = {
  level: number;
  speechLike: boolean;
};

type VoiceActivityGateResult = {
  state: VoiceActivityGateState;
  becameArmed: boolean;
  detected: boolean;
};

type VoiceInterruptionDetectorOptions = {
  onArmed: () => void;
  onVoice: (capture: PcmCapture) => void;
  onError: (message: string) => void;
};

const CALIBRATION_MS = 900;
const REQUIRED_ACTIVITY_MS = 420;
// Covers the detection window plus the soft speech onset below the threshold.
// Anything older is mostly assistant playback, which must not be transcribed.
const PRE_ROLL_MS = 1000;
const MINIMUM_ACTIVITY_LEVEL = 0.035;
const NOISE_MULTIPLIER = 2.4;
const NOISE_MARGIN = 0.018;
const PLAYBACK_LEAKAGE_MULTIPLIER = 1.4;
const MINIMUM_ACTIVE_SAMPLES = 5;
const MINIMUM_SPEECH_LIKE_SAMPLES = 3;
const MINIMUM_LEVEL_VARIATION = 0.008;

export function browserSupportsVoiceInterruption(): boolean {
  return Boolean(
    window.isSecureContext &&
      typeof navigator.mediaDevices?.getUserMedia === "function" &&
      browserSupportsPcmCapture(),
  );
}

export function initialVoiceActivityGateState(): VoiceActivityGateState {
  return {
    calibrationStartedAt: null,
    sampleCount: 0,
    noiseFloor: 0,
    playbackLeakageCeiling: 0,
    activeSince: null,
    activeSampleCount: 0,
    speechLikeSampleCount: 0,
    activeMinimumLevel: 0,
    activeMaximumLevel: 0,
    armed: false,
  };
}

export function updateVoiceActivityGate(
  previous: VoiceActivityGateState,
  level: number,
  timestamp: number,
  speechLike = true,
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
        playbackLeakageCeiling: Math.max(
          previous.playbackLeakageCeiling,
          level,
        ),
        activeSince: null,
        activeSampleCount: 0,
        speechLikeSampleCount: 0,
        activeMinimumLevel: 0,
        activeMaximumLevel: 0,
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
    previous.playbackLeakageCeiling * PLAYBACK_LEAKAGE_MULTIPLIER,
  );
  const isActive = level >= threshold;
  const activeSince = isActive
    ? (previous.activeSince ?? timestamp)
    : null;
  const activeSampleCount = isActive
    ? previous.activeSampleCount + 1
    : 0;
  const speechLikeSampleCount = isActive
    ? previous.speechLikeSampleCount + (speechLike ? 1 : 0)
    : 0;
  const activeMinimumLevel = isActive
    ? previous.activeSampleCount === 0
      ? level
      : Math.min(previous.activeMinimumLevel, level)
    : 0;
  const activeMaximumLevel = isActive
    ? Math.max(previous.activeMaximumLevel, level)
    : 0;
  const levelVariation = activeMaximumLevel - activeMinimumLevel;
  const detected =
    activeSince !== null &&
    timestamp - activeSince >= REQUIRED_ACTIVITY_MS &&
    activeSampleCount >= MINIMUM_ACTIVE_SAMPLES &&
    speechLikeSampleCount >= MINIMUM_SPEECH_LIKE_SAMPLES &&
    levelVariation >= MINIMUM_LEVEL_VARIATION;
  const noiseFloor =
    !isActive
      ? previous.noiseFloor * 0.98 + level * 0.02
      : previous.noiseFloor;
  const rejectedActivityPeak =
    !isActive && previous.activeSince !== null
      ? previous.activeMaximumLevel
      : 0;
  const playbackLeakageCeiling = !isActive
    ? Math.max(
        previous.playbackLeakageCeiling * 0.998,
        level,
        rejectedActivityPeak,
      )
    : previous.playbackLeakageCeiling;

  return {
    state: {
      calibrationStartedAt,
      sampleCount: previous.sampleCount,
      noiseFloor,
      playbackLeakageCeiling,
      activeSince,
      activeSampleCount,
      speechLikeSampleCount,
      activeMinimumLevel,
      activeMaximumLevel,
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
  let capture: PcmCapture | null = null;
  let analyserNode: AnalyserNode | null = null;

  const release = (preserveCapture = false): PcmCapture | null => {
    if (stopped) {
      return null;
    }
    stopped = true;
    if (animationFrame !== null) {
      window.cancelAnimationFrame(animationFrame);
      animationFrame = null;
    }
    if (analyserNode) {
      capture?.source.disconnect(analyserNode);
      analyserNode = null;
    }
    const releasedCapture = preserveCapture ? capture : null;
    if (!preserveCapture) {
      if (capture) {
        capture.stop();
      } else {
        stream?.getTracks().forEach((track) => track.stop());
      }
    }
    capture = null;
    stream = null;
    return releasedCapture;
  };

  const stop = () => {
    release();
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
        audio: MICROPHONE_AUDIO_CONSTRAINTS,
        video: false,
      });
      if (stopped) {
        nextStream.getTracks().forEach((track) => track.stop());
        return;
      }
      stream = nextStream;

      const nextCapture = await startPcmCapture(nextStream, PRE_ROLL_MS);
      if (stopped) {
        nextCapture.stop();
        return;
      }
      capture = nextCapture;

      const analyser = nextCapture.audioContext.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.15;
      nextCapture.source.connect(analyser);
      analyserNode = analyser;

      const samples = new Float32Array(analyser.fftSize);
      let gate = initialVoiceActivityGateState();

      const sample = (timestamp: number) => {
        if (stopped) {
          return;
        }
        analyser.getFloatTimeDomainData(samples);
        const activity = analyzeVoiceActivity(samples);
        const result = updateVoiceActivityGate(
          gate,
          activity.level,
          timestamp,
          activity.speechLike,
        );
        gate = result.state;
        if (result.becameArmed) {
          options.onArmed();
        }
        if (result.detected) {
          const recognitionCapture = release(true);
          if (recognitionCapture) {
            options.onVoice(recognitionCapture);
          }
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

export function analyzeVoiceActivity(
  samples: Float32Array,
): VoiceActivitySample {
  if (samples.length === 0) {
    return { level: 0, speechLike: false };
  }

  let mean = 0;
  for (const sample of samples) {
    mean += sample;
  }
  mean /= samples.length;

  let sumOfSquares = 0;
  let peak = 0;
  let zeroCrossings = 0;
  let previousCenteredSample = samples[0] - mean;
  for (const sample of samples) {
    const centeredSample = sample - mean;
    sumOfSquares += centeredSample * centeredSample;
    peak = Math.max(peak, Math.abs(centeredSample));
    if (
      (previousCenteredSample < 0 && centeredSample >= 0) ||
      (previousCenteredSample >= 0 && centeredSample < 0)
    ) {
      zeroCrossings += 1;
    }
    previousCenteredSample = centeredSample;
  }
  const level = Math.sqrt(sumOfSquares / samples.length);
  const peakToRms = level > 0 ? peak / level : 0;
  const zeroCrossingRate = zeroCrossings / samples.length;
  const speechLike =
    level > 0 &&
    peakToRms >= 1.15 &&
    peakToRms <= 8 &&
    zeroCrossingRate >= 0.005 &&
    zeroCrossingRate <= 0.38;

  return { level, speechLike };
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
