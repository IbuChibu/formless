import {
  browserSupportsPcmCapture,
  MICROPHONE_AUDIO_CONSTRAINTS,
  startPcmCapture,
  type PcmCapture,
  type VoiceTurnAudio,
} from "./voiceAudioCapture";

export type DeepgramWord = {
  word: string;
  start: number;
  end: number;
  confidence: number;
};

export type DeepgramUtterance = {
  transcript: string;
  confidence: number;
  words: DeepgramWord[];
  provider: "deepgram";
  finalTranscriptLatencyMs: number | null;
};

export type DeepgramRecognitionCallbacks = {
  onConnected: () => void;
  onTranscript: (transcript: string) => void;
  onComplete: (utterance: DeepgramUtterance) => void;
  onNoSpeech: () => void;
  onError: (message: string) => void;
};

export type RecognitionTiming = {
  endpointingMs: number;
  utteranceEndMs: number;
  settleMs: number;
};

export type DeepgramRecognitionOptions = {
  tokenUrl: string;
  keyterms?: string[];
  choiceKeyterms?: string[];
  timing?: RecognitionTiming;
  initialCapture?: PcmCapture;
  onTurnAudio?: (audio: VoiceTurnAudio) => void;
};

export type VoiceRecognitionField = {
  id: string;
  label: string;
  question?: string;
  type: string;
  options?: string[];
};

type DeepgramResultEvent = {
  kind: "result";
  transcript: string;
  confidence: number;
  words: DeepgramWord[];
  isFinal: boolean;
  speechFinal: boolean;
  segmentKey: string;
};

export type ParsedDeepgramEvent =
  | DeepgramResultEvent
  | { kind: "utterance_end" }
  | { kind: "metadata" }
  | { kind: "error"; message: string }
  | { kind: "ignored" };

type TemporaryToken = {
  access_token: string;
  expires_in: number;
};

type WebSocketLike = {
  readyState: number;
  binaryType: BinaryType;
  onopen: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  onclose: ((event: CloseEvent) => void) | null;
  send(data: string | ArrayBufferLike | Blob | ArrayBufferView): void;
  close(code?: number, reason?: string): void;
};

export type DeepgramRecognitionDependencies = {
  fetch: typeof fetch;
  getUserMedia: (constraints: MediaStreamConstraints) => Promise<MediaStream>;
  createWebSocket: (url: string, protocols: string[]) => WebSocketLike;
  startPcmCapture: (stream: MediaStream) => Promise<PcmCapture>;
  now: () => number;
  setTimeout: typeof window.setTimeout;
  clearTimeout: typeof window.clearTimeout;
  setInterval: typeof window.setInterval;
  clearInterval: typeof window.clearInterval;
};

const DEEPGRAM_SOCKET_OPEN = 1;
const MAX_BUFFERED_AUDIO_CHUNKS = 120;
const MANUAL_FINALIZE_TIMEOUT_MS = 1800;
const CONNECTION_TIMEOUT_MS = 10000;
const KEEP_ALIVE_MS = 8000;
const ENGLISH_LOCALE = "en-GB";
const CHOICE_RECOGNITION_TIMING: RecognitionTiming = {
  endpointingMs: 500,
  utteranceEndMs: 1200,
  settleMs: 600,
};
const DEFAULT_RECOGNITION_TIMING: RecognitionTiming = {
  endpointingMs: 1000,
  utteranceEndMs: 2000,
  settleMs: 1000,
};
const LONG_ANSWER_RECOGNITION_TIMING: RecognitionTiming = {
  endpointingMs: 1500,
  utteranceEndMs: 2500,
  settleMs: 1200,
};
const CHOICE_FIELD_TYPES = new Set(["checkbox", "dropdown", "radio"]);
const ADDRESS_FIELD_METADATA = /\b(?:address|postcode|street)\b/;
const CONTROL_KEYTERMS = [
  "skip",
  "repeat",
  "go back",
  "I don't know",
  "that's correct",
];
const ALLOWED_KEYTERMS = new Map(
  CONTROL_KEYTERMS.map((value) => [value.toLocaleLowerCase(), value]),
);
const PLACEHOLDER_OPTION = /^(?:choose|none|please select|select|select one)$/i;
const SAFE_OPTION_KEYTERM = /^[\p{L}\p{N}][\p{L}\p{N}\s'()&+,.\-/]*$/u;
// With the five control words, this caps a connection at 40 keyterms.
const MAX_OPTION_KEYTERMS = 35;
// Deepgram rejects a connection above 500 keyterm tokens, so long option labels
// must not be able to end a voice turn. This allows 1.6 characters per token.
const MAX_TOTAL_KEYTERM_CHARACTERS = 800;
const MAX_OPTION_KEYTERM_CHARACTERS = 64;
const MAX_OPTION_KEYTERM_WORDS = 8;
const NAME_FRAMING_WORDS = new Set([
  "forename",
  "full",
  "is",
  "legal",
  "my",
  "name",
  "surname",
]);
const EXPLICIT_LETTER_SPELLING =
  /(?<![\p{L}])(?:[\p{L}](?:\s*[.\-]\s*|\s+)){2,}[\p{L}](?:\.)?(?![\p{L}])/u;

export const NAME_CONFIDENCE_THRESHOLD = 0.82;

export class DeepgramSpeechRecognizer {
  private readonly callbacks: DeepgramRecognitionCallbacks;
  private readonly options: DeepgramRecognitionOptions;
  private readonly dependencies: DeepgramRecognitionDependencies;
  private stream: MediaStream | null = null;
  private socket: WebSocketLike | null = null;
  private capture: PcmCapture | null = null;
  private settleTimer: number | null = null;
  private finalizeTimer: number | null = null;
  private keepAliveTimer: number | null = null;
  private connectionTimer: number | null = null;
  private cancelled = false;
  private completed = false;
  private finalSegments: string[] = [];
  private finalWords: DeepgramWord[] = [];
  private segmentKeys = new Set<string>();
  private confidences: number[] = [];
  private speechFinalAt: number | null = null;
  private bufferedAudio: ArrayBuffer[] = [];
  private turnAudio: ArrayBuffer[] = [];
  private turnSampleRate = 0;

  constructor(
    options: DeepgramRecognitionOptions,
    callbacks: DeepgramRecognitionCallbacks,
    dependencies: DeepgramRecognitionDependencies = browserDependencies(),
  ) {
    this.options = options;
    this.callbacks = callbacks;
    this.dependencies = dependencies;
  }

  async start(): Promise<void> {
    this.cancelled = false;
    try {
      const capture = await this.openCapture();
      if (!capture) {
        return;
      }
      this.capture = capture;
      this.turnSampleRate = capture.sampleRate;
      capture.setChunkListener((chunk) => this.handleAudioChunk(chunk));

      const token = await requestTemporaryToken(
        this.options.tokenUrl,
        this.dependencies.fetch,
      );
      if (this.cancelled || this.completed) {
        this.releaseMedia();
        return;
      }

      const socket = this.dependencies.createWebSocket(
        buildDeepgramStreamingUrl(
          capture.sampleRate,
          this.options.keyterms,
          this.options.choiceKeyterms,
          this.options.timing,
        ),
        ["bearer", token.access_token],
      );
      socket.binaryType = "arraybuffer";
      this.socket = socket;
      this.bindSocket(socket);
    } catch (error) {
      if (!this.cancelled) {
        this.fail(recognitionStartError(error));
      }
    }
  }

  stop(): void {
    if (this.cancelled || this.completed) {
      return;
    }
    this.releaseMedia();
    if (this.socket?.readyState === DEEPGRAM_SOCKET_OPEN) {
      this.socket.send(JSON.stringify({ type: "Finalize" }));
      this.clearFinalizeTimer();
      this.finalizeTimer = this.dependencies.setTimeout(() => {
        this.finish();
      }, MANUAL_FINALIZE_TIMEOUT_MS);
      return;
    }
    this.finish();
  }

  cancel(): void {
    if (this.cancelled) {
      return;
    }
    this.cancelled = true;
    this.completed = true;
    this.clearTimers();
    this.releaseMedia();
    this.closeSocket();
    this.clearTurnData();
  }

  private async openCapture(): Promise<PcmCapture | null> {
    if (this.options.initialCapture) {
      this.startConnectionTimer();
      return this.options.initialCapture;
    }
    this.stream = await this.dependencies.getUserMedia({
      audio: MICROPHONE_AUDIO_CONSTRAINTS,
    });
    if (this.cancelled) {
      this.releaseMedia();
      return null;
    }
    // Armed after the permission prompt, which can legitimately take longer.
    this.startConnectionTimer();
    const capture = await this.dependencies.startPcmCapture(this.stream);
    if (this.cancelled || this.completed) {
      capture.stop();
      return null;
    }
    return capture;
  }

  private startConnectionTimer(): void {
    this.connectionTimer = this.dependencies.setTimeout(() => {
      this.fail(
        "Deepgram voice input did not connect in time. Try again or keep typing.",
      );
    }, CONNECTION_TIMEOUT_MS);
  }

  private handleAudioChunk(chunk: ArrayBuffer): void {
    if (this.cancelled || this.completed) {
      return;
    }
    if (this.options.onTurnAudio) {
      this.turnAudio.push(chunk);
    }
    const socket = this.socket;
    if (socket?.readyState === DEEPGRAM_SOCKET_OPEN) {
      socket.send(chunk);
      return;
    }
    this.bufferedAudio.push(chunk);
    if (this.bufferedAudio.length > MAX_BUFFERED_AUDIO_CHUNKS) {
      this.fail(
        "Deepgram voice input took too long to connect. Try again or keep typing.",
      );
    }
  }

  private bindSocket(socket: WebSocketLike): void {
    socket.onopen = () => {
      if (this.cancelled || socket !== this.socket || !this.capture) {
        return;
      }
      this.clearConnectionTimer();
      try {
        this.bufferedAudio.forEach((chunk) => socket.send(chunk));
        this.bufferedAudio = [];
        this.keepAliveTimer = this.dependencies.setInterval(() => {
          if (socket.readyState === DEEPGRAM_SOCKET_OPEN) {
            socket.send(JSON.stringify({ type: "KeepAlive" }));
          }
        }, KEEP_ALIVE_MS);
        this.callbacks.onConnected();
      } catch {
        this.fail(
          "This browser could not start compatible microphone capture. Keep typing instead.",
        );
      }
    };
    socket.onmessage = (event) => {
      if (this.cancelled || this.completed || socket !== this.socket) {
        return;
      }
      const parsed = parseDeepgramMessage(event.data);
      this.handleProviderEvent(parsed);
    };
    socket.onerror = () => {
      if (!this.cancelled && !this.completed) {
        this.fail(
          "Deepgram voice input could not continue. Try again or keep typing.",
        );
      }
    };
    socket.onclose = () => {
      if (!this.cancelled && !this.completed) {
        this.fail(
          "Deepgram voice input disconnected. Your form is unchanged; try again or keep typing.",
        );
      }
    };
  }

  private handleProviderEvent(event: ParsedDeepgramEvent): void {
    if (event.kind === "error") {
      this.fail(event.message);
      return;
    }
    if (event.kind === "utterance_end") {
      this.finish();
      return;
    }
    if (event.kind !== "result" || !event.transcript) {
      return;
    }

    this.clearSettleTimer();
    if (event.isFinal && !this.segmentKeys.has(event.segmentKey)) {
      this.segmentKeys.add(event.segmentKey);
      this.finalSegments.push(event.transcript);
      this.finalWords.push(...event.words);
      if (event.confidence >= 0) {
        this.confidences.push(event.confidence);
      }
    }

    const visibleTranscript = event.isFinal
      ? this.completeTranscript()
      : joinTranscript(this.completeTranscript(), event.transcript);
    this.callbacks.onTranscript(visibleTranscript);

    if (event.speechFinal) {
      this.speechFinalAt = this.dependencies.now();
      this.settleTimer = this.dependencies.setTimeout(() => {
        this.finish();
      }, (this.options.timing ?? DEFAULT_RECOGNITION_TIMING).settleMs);
    }
  }

  private finish(): void {
    if (this.cancelled || this.completed) {
      return;
    }
    this.completed = true;
    const transcript = this.completeTranscript();
    const latency =
      this.speechFinalAt === null
        ? null
        : Math.max(0, this.dependencies.now() - this.speechFinalAt);
    const confidence =
      this.confidences.length === 0
        ? 0
        : this.confidences.reduce((sum, value) => sum + value, 0) /
          this.confidences.length;
    const utterance: DeepgramUtterance = {
      transcript,
      confidence,
      words: [...this.finalWords],
      provider: "deepgram",
      finalTranscriptLatencyMs: latency,
    };
    const turnAudio: VoiceTurnAudio = {
      chunks: this.turnAudio,
      sampleRate: this.turnSampleRate,
    };

    this.clearTimers();
    this.releaseMedia();
    this.closeSocket();
    this.clearTurnData();
    if (turnAudio.chunks.length > 0) {
      this.options.onTurnAudio?.(turnAudio);
    }
    if (!transcript) {
      this.callbacks.onNoSpeech();
      return;
    }
    this.callbacks.onTranscript(transcript);
    this.callbacks.onComplete(utterance);
  }

  private fail(message: string): void {
    if (this.cancelled || this.completed) {
      return;
    }
    this.completed = true;
    this.clearTimers();
    this.releaseMedia();
    this.closeSocket();
    this.clearTurnData();
    this.callbacks.onError(message);
  }

  private completeTranscript(): string {
    return this.finalSegments.join(" ").replace(/\s+/g, " ").trim();
  }

  private releaseMedia(): void {
    if (this.capture) {
      this.capture.stop();
    } else {
      this.stream?.getTracks().forEach((track) => track.stop());
    }
    this.capture = null;
    this.stream = null;
  }

  private closeSocket(): void {
    const socket = this.socket;
    this.socket = null;
    if (!socket) {
      return;
    }
    socket.onopen = null;
    socket.onmessage = null;
    socket.onerror = null;
    socket.onclose = null;
    if (socket.readyState === DEEPGRAM_SOCKET_OPEN) {
      try {
        socket.send(JSON.stringify({ type: "CloseStream" }));
      } catch {
        // Closing the browser socket still releases the session.
      }
    }
    try {
      socket.close(1000, "Voice turn complete");
    } catch {
      // A browser may reject close while the handshake is still pending.
    }
  }

  private clearSettleTimer(): void {
    if (this.settleTimer !== null) {
      this.dependencies.clearTimeout(this.settleTimer);
      this.settleTimer = null;
    }
  }

  private clearFinalizeTimer(): void {
    if (this.finalizeTimer !== null) {
      this.dependencies.clearTimeout(this.finalizeTimer);
      this.finalizeTimer = null;
    }
  }

  private clearConnectionTimer(): void {
    if (this.connectionTimer !== null) {
      this.dependencies.clearTimeout(this.connectionTimer);
      this.connectionTimer = null;
    }
  }

  private clearTimers(): void {
    this.clearSettleTimer();
    this.clearFinalizeTimer();
    this.clearConnectionTimer();
    if (this.keepAliveTimer !== null) {
      this.dependencies.clearInterval(this.keepAliveTimer);
      this.keepAliveTimer = null;
    }
  }

  private clearTurnData(): void {
    this.bufferedAudio = [];
    this.turnAudio = [];
    this.finalSegments = [];
    this.finalWords = [];
    this.segmentKeys.clear();
    this.confidences = [];
    this.speechFinalAt = null;
  }
}

export function browserSupportsDeepgramSpeech(): boolean {
  return Boolean(
    window.isSecureContext &&
      typeof navigator.mediaDevices?.getUserMedia === "function" &&
      typeof window.WebSocket === "function" &&
      browserSupportsPcmCapture(),
  );
}

export function buildDeepgramStreamingUrl(
  sampleRate: number,
  keyterms: string[] = [],
  choiceKeyterms: string[] = [],
  timing: RecognitionTiming = DEFAULT_RECOGNITION_TIMING,
): string {
  const parameters = new URLSearchParams({
    model: "nova-3",
    language: ENGLISH_LOCALE,
    encoding: "linear16",
    sample_rate: String(sampleRate),
    smart_format: "true",
    punctuate: "true",
    interim_results: "true",
    endpointing: String(timing.endpointingMs),
    utterance_end_ms: String(timing.utteranceEndMs),
    vad_events: "true",
    mip_opt_out: "true",
  });
  combinedKeyterms(keyterms, choiceKeyterms).forEach((keyterm) => {
    parameters.append("keyterm", keyterm);
  });
  return `wss://api.deepgram.com/v1/listen?${parameters.toString()}`;
}

export function boundedKeyterms(keyterms: string[]): string[] {
  return [...new Set(keyterms.map((value) => value.trim().toLocaleLowerCase()))]
    .flatMap((value) => ALLOWED_KEYTERMS.get(value) ?? []);
}

function combinedKeyterms(
  keyterms: string[],
  choiceKeyterms: string[],
): string[] {
  // An option may repeat a control word; the option's own casing wins.
  const combined = new Map<string, string>();
  [
    ...boundedKeyterms(keyterms),
    ...boundedChoiceKeyterms(choiceKeyterms),
  ].forEach((value) => {
    combined.set(value.toLocaleLowerCase(), value);
  });
  let remainingCharacters = MAX_TOTAL_KEYTERM_CHARACTERS;
  return [...combined.values()].filter((value) => {
    if (value.length > remainingCharacters) {
      return false;
    }
    remainingCharacters -= value.length;
    return true;
  });
}

export function boundedChoiceKeyterms(options: string[] = []): string[] {
  const normalized = options
    .map((value) => value.trim().replace(/\s+/g, " "))
    .filter(
      (value) =>
        value.length > 1 &&
        value.length <= MAX_OPTION_KEYTERM_CHARACTERS &&
        !PLACEHOLDER_OPTION.test(value) &&
        SAFE_OPTION_KEYTERM.test(value) &&
        value.split(/\s+/).length <= MAX_OPTION_KEYTERM_WORDS,
    );
  return [...new Map(normalized.map((value) => [value.toLocaleLowerCase(), value])).values()]
    .slice(0, MAX_OPTION_KEYTERMS);
}

export function parseDeepgramMessage(data: unknown): ParsedDeepgramEvent {
  if (typeof data !== "string") {
    return { kind: "ignored" };
  }
  let payload: unknown;
  try {
    payload = JSON.parse(data);
  } catch {
    return { kind: "error", message: "Deepgram returned an invalid transcript event." };
  }
  if (!isRecord(payload) || typeof payload.type !== "string") {
    return { kind: "error", message: "Deepgram returned an invalid transcript event." };
  }
  if (payload.type === "UtteranceEnd") {
    return { kind: "utterance_end" };
  }
  if (payload.type === "Metadata") {
    return { kind: "metadata" };
  }
  if (payload.type === "Error") {
    return {
      kind: "error",
      message: "Deepgram could not process this voice turn. Try again or keep typing.",
    };
  }
  if (payload.type !== "Results") {
    return { kind: "ignored" };
  }

  const channel = payload.channel;
  if (!isRecord(channel) || !Array.isArray(channel.alternatives)) {
    return { kind: "error", message: "Deepgram returned an invalid transcript event." };
  }
  const alternative = channel.alternatives[0];
  if (!isRecord(alternative) || typeof alternative.transcript !== "string") {
    return { kind: "error", message: "Deepgram returned an invalid transcript event." };
  }
  const confidence = finiteNumber(alternative.confidence, 0);
  const words = Array.isArray(alternative.words)
    ? alternative.words.flatMap(parseWord)
    : [];
  const start = finiteNumber(payload.start, 0);
  const duration = finiteNumber(payload.duration, 0);
  const transcript = alternative.transcript.trim();
  return {
    kind: "result",
    transcript,
    confidence,
    words,
    isFinal: payload.is_final === true,
    speechFinal: payload.speech_final === true,
    segmentKey: `${start}:${duration}:${transcript}`,
  };
}

export function lowConfidenceNameWord(
  utterance: DeepgramUtterance,
  threshold = NAME_CONFIDENCE_THRESHOLD,
): DeepgramWord | null {
  const spokenWords = utterance.words.filter((word) => {
    const normalized = word.word
      .toLocaleLowerCase()
      .replace(/[^\p{L}]/gu, "");
    return normalized && !NAME_FRAMING_WORDS.has(normalized);
  });
  if (spokenWords.length === 0) {
    return utterance.confidence < threshold
      ? {
          word: utterance.transcript,
          start: 0,
          end: 0,
          confidence: utterance.confidence,
        }
      : null;
  }
  return (
    spokenWords.find((word) => word.confidence < threshold) ?? null
  );
}

export function isNameFieldMetadata(
  field: VoiceRecognitionField | null,
): boolean {
  if (!field || !["text", "textarea"].includes(field.type)) {
    return false;
  }
  const metadata = fieldMetadata(field);
  return /\b(?:name|surname|forename)\b/.test(metadata);
}

export function recognitionKeyterms(): string[] {
  return boundedKeyterms(CONTROL_KEYTERMS);
}

export function recognitionTiming(
  field: VoiceRecognitionField | null,
  hasPendingProposal = false,
): RecognitionTiming {
  if (hasPendingProposal) {
    return CHOICE_RECOGNITION_TIMING;
  }
  if (!field) {
    return DEFAULT_RECOGNITION_TIMING;
  }
  if (CHOICE_FIELD_TYPES.has(field.type) || (field.options?.length ?? 0) > 0) {
    return CHOICE_RECOGNITION_TIMING;
  }
  if (
    field.type === "textarea" ||
    isNameFieldMetadata(field) ||
    ADDRESS_FIELD_METADATA.test(fieldMetadata(field))
  ) {
    return LONG_ANSWER_RECOGNITION_TIMING;
  }
  return DEFAULT_RECOGNITION_TIMING;
}

export function recognitionChoiceKeyterms(
  field: VoiceRecognitionField | null,
): string[] {
  return field ? boundedChoiceKeyterms(field.options) : [];
}

export function nameConfidenceConcern(
  field: VoiceRecognitionField | null,
  utterance: DeepgramUtterance,
): string | null {
  if (!isNameFieldMetadata(field)) {
    return null;
  }
  if (EXPLICIT_LETTER_SPELLING.test(utterance.transcript)) {
    return null;
  }
  const uncertainWord = lowConfidenceNameWord(utterance);
  if (!uncertainWord) {
    return null;
  }
  const visibleWord = uncertainWord.word.trim() || "part of the name";
  return (
    `I’m not sure I heard “${visibleWord}” correctly. ` +
    "Please repeat just that part, spell it letter by letter, or edit the visible transcript."
  );
}

async function requestTemporaryToken(
  tokenUrl: string,
  fetcher: typeof fetch,
): Promise<TemporaryToken> {
  const response = await fetcher(tokenUrl, { method: "POST" });
  if (!response.ok) {
    let detail = "";
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      // Use the bounded provider-neutral fallback below.
    }
    throw new Error(
      detail ||
        "Deepgram voice input could not start. Try again or keep typing.",
    );
  }
  const payload = (await response.json()) as Partial<TemporaryToken>;
  if (
    typeof payload.access_token !== "string" ||
    !payload.access_token ||
    typeof payload.expires_in !== "number" ||
    !Number.isInteger(payload.expires_in) ||
    payload.expires_in <= 0
  ) {
    throw new Error(
      "The voice service returned an invalid temporary credential. Keep typing instead.",
    );
  }
  return {
    access_token: payload.access_token,
    expires_in: payload.expires_in,
  };
}

function browserDependencies(): DeepgramRecognitionDependencies {
  return {
    fetch: window.fetch.bind(window),
    getUserMedia: (constraints) =>
      navigator.mediaDevices.getUserMedia(constraints),
    createWebSocket: (url, protocols) => new WebSocket(url, protocols),
    startPcmCapture: (stream) => startPcmCapture(stream),
    now: () => window.performance.now(),
    setTimeout: window.setTimeout.bind(window),
    clearTimeout: window.clearTimeout.bind(window),
    setInterval: window.setInterval.bind(window),
    clearInterval: window.clearInterval.bind(window),
  };
}

function recognitionStartError(error: unknown): string {
  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError") {
      return "Microphone access was denied. Allow it for this site, or keep typing.";
    }
    if (error.name === "NotFoundError") {
      return "No working microphone was found. Check your microphone or keep typing.";
    }
  }
  return error instanceof Error
    ? error.message
    : "Deepgram voice input could not start. Try again or keep typing.";
}

function parseWord(value: unknown): DeepgramWord[] {
  if (!isRecord(value) || typeof value.word !== "string") {
    return [];
  }
  return [
    {
      word: value.word,
      start: finiteNumber(value.start, 0),
      end: finiteNumber(value.end, 0),
      confidence: finiteNumber(value.confidence, 0),
    },
  ];
}

function finiteNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : fallback;
}

function joinTranscript(first: string, second: string): string {
  return [first, second].filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function fieldMetadata(field: VoiceRecognitionField): string {
  return [field.id, field.label, field.question ?? ""]
    .join(" ")
    .toLocaleLowerCase();
}
