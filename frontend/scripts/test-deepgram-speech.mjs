import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import ts from "typescript";

const sourceUrl = new URL(
  "../src/deepgramSpeechRecognition.ts",
  import.meta.url,
);
const source = await readFile(sourceUrl, "utf8");
const interviewSource = await readFile(
  new URL("../src/useVoiceInterview.ts", import.meta.url),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2020,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: sourceUrl.pathname,
}).outputText;
const moduleUrl = `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`;
const {
  DeepgramSpeechRecognizer,
  buildDeepgramStreamingUrl,
  boundedKeyterms,
  lowConfidenceNameWord,
  nameConfidenceConcern,
  parseDeepgramMessage,
  recognitionKeyterms,
} = await import(moduleUrl);

assert.doesNotMatch(
  interviewSource,
  /confirmationPhrases|rejectionPhrases|extractSpokenCorrection/,
  "finalized review speech must not be reduced to a frontend phrase table",
);
assert.match(
  interviewSource,
  /submitTranscriptRef\.current = \(transcript: string\)[\s\S]*current\.onSendMessage\(intent\.message\)/,
  "finalized speech must use the shared Form Agent message route",
);

class FakeSocket {
  readyState = 0;
  binaryType = "blob";
  onopen = null;
  onmessage = null;
  onerror = null;
  onclose = null;
  sent = [];
  closeCount = 0;
  url = "";
  protocols = [];

  open() {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }

  message(data) {
    this.onmessage?.({ data });
  }

  error() {
    this.onerror?.(new Event("error"));
  }

  send(data) {
    this.sent.push(data);
  }

  close() {
    this.closeCount += 1;
    this.readyState = 3;
  }
}

class FakeRecorder {
  state = "inactive";
  ondataavailable = null;
  onerror = null;
  startTimeslice = null;
  stopCount = 0;

  start(timeslice) {
    this.state = "recording";
    this.startTimeslice = timeslice;
  }

  stop() {
    this.stopCount += 1;
    this.state = "inactive";
  }
}

{
  const url = new URL(
    buildDeepgramStreamingUrl([
      "surname",
      "Secret Person",
      "postcode",
      "surname",
    ]),
  );
  assert.equal(url.origin, "wss://api.deepgram.com");
  assert.equal(url.pathname, "/v1/listen");
  assert.equal(url.searchParams.get("model"), "nova-3");
  assert.equal(url.searchParams.get("language"), "en-GB");
  assert.equal(url.searchParams.get("interim_results"), "true");
  assert.equal(url.searchParams.get("endpointing"), "700");
  assert.equal(url.searchParams.get("utterance_end_ms"), "1500");
  assert.equal(url.searchParams.get("mip_opt_out"), "true");
  assert.deepEqual(url.searchParams.getAll("keyterm"), [
    "surname",
    "postcode",
  ]);
  assert.deepEqual(boundedKeyterms(["Unknown Person"]), []);
}

{
  const interim = parseDeepgramMessage(
    resultMessage("Ibrahim", { isFinal: false }),
  );
  assert.equal(interim.kind, "result");
  assert.equal(interim.isFinal, false);
  assert.equal(interim.speechFinal, false);

  const final = parseDeepgramMessage(
    resultMessage("Ibrahim Akhoon", {
      isFinal: true,
      speechFinal: true,
      words: [
        word("Ibrahim", 0.98),
        word("Akhoon", 0.74),
      ],
    }),
  );
  assert.equal(final.kind, "result");
  assert.equal(final.isFinal, true);
  assert.equal(final.speechFinal, true);
  assert.equal(final.words.length, 2);

  assert.deepEqual(
    parseDeepgramMessage(JSON.stringify({ type: "UtteranceEnd" })),
    { kind: "utterance_end" },
  );
  assert.equal(parseDeepgramMessage("not json").kind, "error");
  assert.equal(parseDeepgramMessage(new ArrayBuffer(4)).kind, "ignored");
  assert.equal(
    parseDeepgramMessage(
      JSON.stringify({
        type: "Results",
        channel: { alternatives: [{ transcript: "" }] },
      }),
    ).kind,
    "result",
  );
  assert.equal(
    parseDeepgramMessage(JSON.stringify({ type: "Error" })).kind,
    "error",
  );

  const uncertain = lowConfidenceNameWord({
    transcript: "Ibrahim Akhoon",
    confidence: 0.9,
    words: [word("Ibrahim", 0.98), word("Akhoon", 0.74)],
    provider: "deepgram",
    finalTranscriptLatencyMs: 420,
  });
  assert.equal(uncertain.word, "Akhoon");

  const nameField = {
    id: "surname",
    label: "Family name",
    type: "text",
  };
  const utterance = {
    transcript: "Ibrahim Akhoon",
    confidence: 0.9,
    words: [word("Ibrahim", 0.98), word("Akhoon", 0.74)],
    provider: "deepgram",
    finalTranscriptLatencyMs: 420,
  };
  assert.deepEqual(recognitionKeyterms(nameField), ["surname"]);
  assert.match(nameConfidenceConcern(nameField, utterance), /Akhoon/);
  assert.equal(
    nameConfidenceConcern(nameField, {
      transcript: "My surname is A K H O O N",
      confidence: 0.65,
      words: [
        word("My", 0.55),
        word("surname", 0.6),
        word("is", 0.58),
        word("A", 0.71),
        word("K", 0.72),
        word("H", 0.7),
        word("O", 0.73),
        word("O", 0.69),
        word("N", 0.74),
      ],
      provider: "deepgram",
      finalTranscriptLatencyMs: 420,
    }),
    null,
    "explicit spelling must remain reviewable instead of looping on confidence",
  );
  assert.equal(
    nameConfidenceConcern(
      { id: "notes", label: "Notes", type: "textarea" },
      utterance,
    ),
    null,
    "low confidence must target identity fields rather than blocking ordinary text",
  );
}

{
  const harness = createHarness();
  const events = [];
  const recognizer = new DeepgramSpeechRecognizer(
    {
      tokenUrl: "http://localhost:8000/voice/deepgram/token",
      keyterms: ["surname"],
    },
    callbacks(events),
    harness.dependencies,
  );

  await recognizer.start();
  assert.deepEqual(harness.requestedConstraints, {
    audio: {
      autoGainControl: false,
      echoCancellation: true,
      noiseSuppression: true,
    },
  });
  assert.equal(harness.fetchCount, 1);
  assert.deepEqual(harness.socket.protocols, ["bearer", "temporary-jwt"]);
  harness.socket.open();
  assert.equal(harness.recorder.startTimeslice, 250);
  assert.deepEqual(events, [{ type: "connected" }]);

  harness.socket.message(resultMessage("Ibrahim", { isFinal: false }));
  harness.socket.message(
    resultMessage("Ibrahim", {
      isFinal: true,
      words: [word("Ibrahim", 0.98)],
      start: 0,
    }),
  );
  harness.socket.message(
    resultMessage("Akhoon", {
      isFinal: true,
      speechFinal: true,
      words: [word("Akhoon", 0.96)],
      start: 1,
    }),
  );
  harness.socket.message(
    resultMessage("Akhoon", {
      isFinal: true,
      speechFinal: true,
      words: [word("Akhoon", 0.96)],
      start: 1,
    }),
  );

  assert.equal(events.filter((event) => event.type === "complete").length, 0);
  harness.socket.message(resultMessage("still speaking", { isFinal: false }));
  harness.runTimeouts();
  assert.equal(
    events.filter((event) => event.type === "complete").length,
    0,
    "a continued utterance must cancel the earlier speech-final timer",
  );

  harness.socket.message(JSON.stringify({ type: "UtteranceEnd" }));
  harness.socket.message(JSON.stringify({ type: "UtteranceEnd" }));
  const completions = events.filter((event) => event.type === "complete");
  assert.equal(completions.length, 1);
  assert.equal(completions[0].utterance.transcript, "Ibrahim Akhoon");
  assert.equal(completions[0].utterance.words.length, 2);
  assert.equal(harness.trackStops, 1);
  assert.equal(harness.recorder.stopCount, 1);
  assert.equal(harness.socket.closeCount, 1);
  assert.ok(
    harness.socket.sent.some((message) =>
      typeof message === "string" && message.includes("CloseStream"),
    ),
  );
}

{
  const harness = createHarness();
  const events = [];
  const recognizer = new DeepgramSpeechRecognizer(
    { tokenUrl: "/voice/deepgram/token" },
    callbacks(events),
    harness.dependencies,
  );
  await recognizer.start();
  harness.socket.open();
  recognizer.cancel();
  recognizer.cancel();
  assert.equal(harness.trackStops, 1);
  assert.equal(harness.recorder.stopCount, 1);
  assert.equal(harness.socket.closeCount, 1);
  assert.equal(events.some((event) => event.type === "complete"), false);
  assert.equal(events.some((event) => event.type === "error"), false);
}

{
  const harness = createHarness();
  const events = [];
  const recognizer = new DeepgramSpeechRecognizer(
    { tokenUrl: "/voice/deepgram/token" },
    callbacks(events),
    harness.dependencies,
  );
  await recognizer.start();
  harness.socket.open();
  harness.socket.message(
    resultMessage("sixteen October", {
      isFinal: true,
      words: [word("sixteen", 0.95), word("October", 0.97)],
    }),
  );
  recognizer.stop();
  assert.ok(
    harness.socket.sent.some((message) =>
      typeof message === "string" && message.includes("Finalize"),
    ),
  );
  harness.runTimeouts();
  assert.equal(
    events.filter((event) => event.type === "complete").length,
    1,
    "manual stop must finalize and dispatch the completed transcript once",
  );
  assert.equal(harness.trackStops, 1);
  assert.equal(harness.socket.closeCount, 1);
}

{
  const harness = createHarness();
  const events = [];
  const recognizer = new DeepgramSpeechRecognizer(
    { tokenUrl: "/voice/deepgram/token" },
    callbacks(events),
    harness.dependencies,
  );
  await recognizer.start();
  harness.socket.open();
  harness.socket.error();
  assert.equal(events.at(-1).type, "error");
  assert.match(events.at(-1).message, /could not continue/);
  assert.equal(harness.trackStops, 1);
  assert.equal(harness.socket.closeCount, 1);
}

{
  const harness = createHarness();
  const events = [];
  const recognizer = new DeepgramSpeechRecognizer(
    { tokenUrl: "/voice/deepgram/token" },
    callbacks(events),
    harness.dependencies,
  );
  await recognizer.start();
  harness.socket.open();
  harness.socket.message(
    resultMessage("", { isFinal: true, speechFinal: true }),
  );
  harness.socket.message(JSON.stringify({ type: "UtteranceEnd" }));
  assert.equal(events.at(-1).type, "error");
  assert.match(events.at(-1).message, /didn't hear any speech/);
  assert.equal(events.some((event) => event.type === "complete"), false);
}

{
  const harness = createHarness({ tokenStatus: 503 });
  const events = [];
  const recognizer = new DeepgramSpeechRecognizer(
    { tokenUrl: "/voice/deepgram/token" },
    callbacks(events),
    harness.dependencies,
  );
  await recognizer.start();
  assert.equal(events.at(-1).type, "error");
  assert.match(events.at(-1).message, /not configured/);
  assert.equal(harness.trackStops, 1);

  const retryHarness = createHarness();
  const retryEvents = [];
  const retry = new DeepgramSpeechRecognizer(
    { tokenUrl: "/voice/deepgram/token" },
    callbacks(retryEvents),
    retryHarness.dependencies,
  );
  await retry.start();
  retryHarness.socket.open();
  assert.deepEqual(retryEvents, [{ type: "connected" }]);
  retry.cancel();
}

{
  const harness = createHarness();
  const events = [];
  const recognizer = new DeepgramSpeechRecognizer(
    { tokenUrl: "/voice/deepgram/token" },
    callbacks(events),
    harness.dependencies,
  );
  await recognizer.start();
  harness.runTimeouts();
  assert.equal(events.at(-1).type, "error");
  assert.match(events.at(-1).message, /did not connect in time/);
  assert.equal(harness.trackStops, 1);
  assert.equal(harness.socket.closeCount, 1);
}

{
  const harness = createHarness({ permissionError: true });
  const events = [];
  const recognizer = new DeepgramSpeechRecognizer(
    { tokenUrl: "/voice/deepgram/token" },
    callbacks(events),
    harness.dependencies,
  );
  await recognizer.start();
  assert.equal(events.length, 1);
  assert.equal(events[0].type, "error");
  assert.match(events[0].message, /Microphone access was denied/);
  assert.equal(harness.fetchCount, 0);
}

console.log("Deepgram streaming speech checks passed");

function callbacks(events) {
  return {
    onConnected: () => events.push({ type: "connected" }),
    onTranscript: (transcript) =>
      events.push({ type: "transcript", transcript }),
    onComplete: (utterance) =>
      events.push({ type: "complete", utterance }),
    onError: (message) => events.push({ type: "error", message }),
  };
}

function resultMessage(
  transcript,
  {
    isFinal = false,
    speechFinal = false,
    words = [],
    start = 0,
  } = {},
) {
  return JSON.stringify({
    type: "Results",
    start,
    duration: 1,
    is_final: isFinal,
    speech_final: speechFinal,
    channel: {
      alternatives: [
        {
          transcript,
          confidence: 0.94,
          words,
        },
      ],
    },
  });
}

function word(value, confidence) {
  return { word: value, start: 0, end: 0.5, confidence };
}

function createHarness({ tokenStatus = 200, permissionError = false } = {}) {
  let trackStops = 0;
  let fetchCount = 0;
  let requestedConstraints = null;
  let nextTimer = 1;
  const timeouts = new Map();
  const intervals = new Map();
  const stream = {
    getTracks: () => [
      {
        stop: () => {
          trackStops += 1;
        },
      },
    ],
  };
  const socket = new FakeSocket();
  const recorder = new FakeRecorder();
  const dependencies = {
    fetch: async () => {
      fetchCount += 1;
      return new Response(
        JSON.stringify(
          tokenStatus === 200
            ? { access_token: "temporary-jwt", expires_in: 30 }
            : { detail: "Deepgram voice input is not configured. Keep typing." },
        ),
        {
          status: tokenStatus,
          headers: { "content-type": "application/json" },
        },
      );
    },
    getUserMedia: async (constraints) => {
      requestedConstraints = constraints;
      if (permissionError) {
        throw new DOMException("denied", "NotAllowedError");
      }
      return stream;
    },
    createWebSocket: (url, protocols) => {
      socket.url = url;
      socket.protocols = protocols;
      return socket;
    },
    createMediaRecorder: () => recorder,
    isMediaTypeSupported: (mimeType) => mimeType.includes("webm"),
    now: () => 2000,
    setTimeout: (callback) => {
      const id = nextTimer++;
      timeouts.set(id, callback);
      return id;
    },
    clearTimeout: (id) => timeouts.delete(id),
    setInterval: (callback) => {
      const id = nextTimer++;
      intervals.set(id, callback);
      return id;
    },
    clearInterval: (id) => intervals.delete(id),
  };
  return {
    dependencies,
    socket,
    recorder,
    get fetchCount() {
      return fetchCount;
    },
    get requestedConstraints() {
      return requestedConstraints;
    },
    get trackStops() {
      return trackStops;
    },
    runTimeouts: () => {
      const callbacks = [...timeouts.values()];
      timeouts.clear();
      callbacks.forEach((callback) => callback());
    },
  };
}
