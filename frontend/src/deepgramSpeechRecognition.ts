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
  onError: (message: string) => void;
};

export type DeepgramRecognitionOptions = {
  tokenUrl: string;
  keyterms?: string[];
};

export type VoiceRecognitionField = {
  id: string;
  label: string;
  question?: string;
  type: string;
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

type MediaRecorderLike = {
  state: RecordingState;
  ondataavailable: ((event: BlobEvent) => void) | null;
  onerror: ((event: ErrorEvent) => void) | null;
  start(timeslice?: number): void;
  stop(): void;
};

export type DeepgramRecognitionDependencies = {
  fetch: typeof fetch;
  getUserMedia: (constraints: MediaStreamConstraints) => Promise<MediaStream>;
  createWebSocket: (url: string, protocols: string[]) => WebSocketLike;
  createMediaRecorder: (
    stream: MediaStream,
    options: MediaRecorderOptions,
  ) => MediaRecorderLike;
  isMediaTypeSupported: (mimeType: string) => boolean;
  now: () => number;
  setTimeout: typeof window.setTimeout;
  clearTimeout: typeof window.clearTimeout;
  setInterval: typeof window.setInterval;
  clearInterval: typeof window.clearInterval;
};

const DEEPGRAM_SOCKET_OPEN = 1;
const AUDIO_TIMESLICE_MS = 250;
const SPEECH_FINAL_SETTLE_MS = 850;
const MANUAL_FINALIZE_TIMEOUT_MS = 1800;
const CONNECTION_TIMEOUT_MS = 10000;
const KEEP_ALIVE_MS = 8000;
const ENGLISH_LOCALE = "en-GB";
const ALLOWED_KEYTERMS = new Set([
  "address",
  "date of birth",
  "forename",
  "postcode",
  "reference number",
  "surname",
]);
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
const AUDIO_TYPES = [
  "audio/webm;codecs=opus",
  "audio/ogg;codecs=opus",
];

export const NAME_CONFIDENCE_THRESHOLD = 0.82;

export class DeepgramSpeechRecognizer {
  private readonly callbacks: DeepgramRecognitionCallbacks;
  private readonly options: DeepgramRecognitionOptions;
  private readonly dependencies: DeepgramRecognitionDependencies;
  private stream: MediaStream | null = null;
  private socket: WebSocketLike | null = null;
  private recorder: MediaRecorderLike | null = null;
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
      this.stream = await this.dependencies.getUserMedia({
        audio: {
          autoGainControl: false,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      if (this.cancelled) {
        this.releaseMedia();
        return;
      }

      const token = await requestTemporaryToken(
        this.options.tokenUrl,
        this.dependencies.fetch,
      );
      if (this.cancelled) {
        this.releaseMedia();
        return;
      }

      const mimeType = selectAudioType(
        this.dependencies.isMediaTypeSupported,
      );
      const socket = this.dependencies.createWebSocket(
        buildDeepgramStreamingUrl(this.options.keyterms),
        ["bearer", token.access_token],
      );
      socket.binaryType = "arraybuffer";
      this.socket = socket;
      this.bindSocket(socket, mimeType);
      this.connectionTimer = this.dependencies.setTimeout(() => {
        this.fail(
          "Deepgram voice input did not connect in time. Try again or keep typing.",
        );
      }, CONNECTION_TIMEOUT_MS);
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
    this.stopRecorderAndMedia();
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
    this.stopRecorderAndMedia();
    this.closeSocket();
    this.clearTurnData();
  }

  private bindSocket(socket: WebSocketLike, mimeType: string): void {
    socket.onopen = () => {
      if (this.cancelled || socket !== this.socket || !this.stream) {
        return;
      }
      this.clearConnectionTimer();
      try {
        const recorder = this.dependencies.createMediaRecorder(
          this.stream,
          { mimeType },
        );
        recorder.ondataavailable = (event) => {
          if (
            event.data.size > 0 &&
            this.socket === socket &&
            socket.readyState === DEEPGRAM_SOCKET_OPEN
          ) {
            socket.send(event.data);
          }
        };
        recorder.onerror = () => {
          this.fail("Microphone audio could not be streamed. Keep typing instead.");
        };
        this.recorder = recorder;
        recorder.start(AUDIO_TIMESLICE_MS);
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
      }, SPEECH_FINAL_SETTLE_MS);
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

    this.clearTimers();
    this.stopRecorderAndMedia();
    this.closeSocket();
    if (!transcript) {
      this.callbacks.onError(
        "I didn't hear any speech. Try again when you are ready, or type your answer.",
      );
      return;
    }
    this.callbacks.onTranscript(transcript);
    this.callbacks.onComplete({
      transcript,
      confidence,
      words: [...this.finalWords],
      provider: "deepgram",
      finalTranscriptLatencyMs: latency,
    });
  }

  private fail(message: string): void {
    if (this.cancelled || this.completed) {
      return;
    }
    this.completed = true;
    this.clearTimers();
    this.stopRecorderAndMedia();
    this.closeSocket();
    this.callbacks.onError(message);
  }

  private completeTranscript(): string {
    return this.finalSegments.join(" ").replace(/\s+/g, " ").trim();
  }

  private stopRecorderAndMedia(): void {
    if (this.recorder?.state === "recording") {
      try {
        this.recorder.stop();
      } catch {
        // Resource release below remains authoritative.
      }
    }
    this.recorder = null;
    this.releaseMedia();
  }

  private releaseMedia(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
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
      typeof window.MediaRecorder === "function",
  );
}

export function buildDeepgramStreamingUrl(keyterms: string[] = []): string {
  const parameters = new URLSearchParams({
    model: "nova-3",
    language: ENGLISH_LOCALE,
    smart_format: "true",
    punctuate: "true",
    interim_results: "true",
    endpointing: "700",
    utterance_end_ms: "1500",
    vad_events: "true",
    mip_opt_out: "true",
  });
  boundedKeyterms(keyterms).forEach((keyterm) => {
    parameters.append("keyterm", keyterm);
  });
  return `wss://api.deepgram.com/v1/listen?${parameters.toString()}`;
}

export function boundedKeyterms(keyterms: string[]): string[] {
  return [...new Set(keyterms.map((value) => value.trim().toLocaleLowerCase()))]
    .filter((value) => ALLOWED_KEYTERMS.has(value))
    .slice(0, 4);
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

export function recognitionKeyterms(
  field: VoiceRecognitionField | null,
): string[] {
  if (!field) {
    return [];
  }
  const metadata = fieldMetadata(field);
  return boundedKeyterms([
    /\bsurname\b/.test(metadata) ? "surname" : "",
    /\bforename\b/.test(metadata) ? "forename" : "",
    /\bdate\s+of\s+birth\b/.test(metadata) ? "date of birth" : "",
    /\bpostcode\b/.test(metadata) ? "postcode" : "",
    /\baddress\b/.test(metadata) ? "address" : "",
    /\breference\s+number\b/.test(metadata) ? "reference number" : "",
  ]);
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
    createMediaRecorder: (stream, options) =>
      new MediaRecorder(stream, options),
    isMediaTypeSupported: (mimeType) =>
      MediaRecorder.isTypeSupported(mimeType),
    now: () => window.performance.now(),
    setTimeout: window.setTimeout.bind(window),
    clearTimeout: window.clearTimeout.bind(window),
    setInterval: window.setInterval.bind(window),
    clearInterval: window.clearInterval.bind(window),
  };
}

function selectAudioType(
  isSupported: (mimeType: string) => boolean,
): string {
  const selected = AUDIO_TYPES.find(isSupported);
  if (!selected) {
    throw new Error(
      "This browser does not provide a supported streaming audio format.",
    );
  }
  return selected;
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
