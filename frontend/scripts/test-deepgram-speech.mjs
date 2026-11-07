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
const captureUrl = new URL("../src/voiceAudioCapture.ts", import.meta.url);
const captureModuleUrl = compileToDataUrl(
  await readFile(captureUrl, "utf8"),
  captureUrl,
);
const { MICROPHONE_AUDIO_CONSTRAINTS } = await import(captureModuleUrl);
const moduleUrl = compileToDataUrl(source, sourceUrl, {
  "./voiceAudioCapture": captureModuleUrl,
});
const {
  DeepgramSpeechRecognizer,
  buildDeepgramStreamingUrl,
  boundedChoiceKeyterms,
  boundedKeyterms,
  lowConfidenceNameWord,
  nameConfidenceConcern,
  parseDeepgramMessage,
  recognitionChoiceKeyterms,
  recognitionKeyterms,
  recognitionTiming,
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

class FakeCapture {
  sampleRate = 16000;
  listener = null;
  stopCount = 0;

  constructor(onStop, preRoll = []) {
    this.onStop = onStop;
    this.preRoll = preRoll;
  }

  setChunkListener(listener) {
    this.listener = listener;
    this.preRoll.forEach((chunk) => listener(chunk));
    this.preRoll = [];
  }

  stop() {
    this.stopCount += 1;
    this.onStop();
  }

  emit(chunk) {
    this.listener?.(chunk);
  }
}

{
  const url = new URL(
    buildDeepgramStreamingUrl(16000, [
      "skip",
      "Secret Person",
      "repeat",
      "skip",
    ]),
  );
  assert.equal(url.origin, "wss://api.deepgram.com");
  assert.equal(url.pathname, "/v1/listen");
  assert.equal(url.searchParams.get("model"), "nova-3");
  assert.equal(url.searchParams.get("language"), "en-GB");
  assert.equal(url.searchParams.get("interim_results"), "true");
  assert.equal(url.searchParams.get("encoding"), "linear16");
  assert.equal(url.searchParams.get("sample_rate"), "16000");
  assert.equal(url.searchParams.get("endpointing"), "1000");
  assert.equal(url.searchParams.get("utterance_end_ms"), "2000");
  assert.equal(url.searchParams.get("mip_opt_out"), "true");
  assert.deepEqual(url.searchParams.getAll("keyterm"), ["skip", "repeat"]);
  assert.deepEqual(boundedKeyterms(["Unknown Person"]), []);
  assert.deepEqual(
    boundedChoiceKeyterms([
      "Sole tenant",
      "Owner-occupier",
      "Please select",
      "person@example.com",
      "Sole tenant",
    ]),
    ["Sole tenant", "Owner-occupier"],
  );
  const choiceUrl = new URL(
    buildDeepgramStreamingUrl(
      16000,
      ["skip"],
      ["Sole tenant", "Owner-occupier", "person@example.com"],
    ),
  );
  assert.deepEqual(choiceUrl.searchParams.getAll("keyterm"), [
    "skip",
    "Sole tenant",
    "Owner-occupier",
  ]);
}

{
  const controlWords = [
    "skip",
    "repeat",
    "go back",
    "I don't know",
    "that's correct",
  ];
  assert.deepEqual(recognitionKeyterms(), controlWords);
  assert.deepEqual(boundedKeyterms(["I DON'T KNOW", "Go Back"]), [
    "I don't know",
    "go back",
  ]);
  assert.deepEqual(
    boundedKeyterms(["surname", "postcode", "date of birth", "yes", "no"]),
    [],
    "field labels and bare yes/no must not be boosted as control words",
  );

  const yesNoField = {
    id: "agree",
    label: "Do you agree?",
    type: "dropdown",
    options: ["Yes", "No"],
  };
  const optionUrl = new URL(
    buildDeepgramStreamingUrl(
      16000,
      recognitionKeyterms(),
      [...recognitionChoiceKeyterms(yesNoField), "Skip"],
    ),
  );
  assert.deepEqual(
    optionUrl.searchParams.getAll("keyterm"),
    ["Skip", "repeat", "go back", "I don't know", "that's correct", "Yes", "No"],
    "options stay boosted and must not send a control word twice",
  );

  const manyOptions = Array.from(
    { length: 200 },
    (_, index) => `Option ${index}`,
  );
  const cappedTerms = new URL(
    buildDeepgramStreamingUrl(16000, controlWords, manyOptions),
  ).searchParams.getAll("keyterm");
  assert.equal(cappedTerms.length, 40);
  assert.ok(controlWords.every((term) => cappedTerms.includes(term)));

  const longOptions = Array.from(
    { length: 200 },
    (_, index) => `Very long option label number ${index} with extra words`,
  );
  const budgetedTerms = new URL(
    buildDeepgramStreamingUrl(16000, controlWords, longOptions),
  ).searchParams.getAll("keyterm");
  assert.ok(
    budgetedTerms.join("").length <= 800,
    "long labels must stay well under Deepgram's 500 keyterm token limit",
  );
  assert.ok(controlWords.every((term) => budgetedTerms.includes(term)));
}

{
  const choice = { endpointingMs: 500, utteranceEndMs: 1200, settleMs: 600 };
  const standard = { endpointingMs: 1000, utteranceEndMs: 2000, settleMs: 1000 };
  const long = { endpointingMs: 1500, utteranceEndMs: 2500, settleMs: 1200 };
  for (const [field, expected] of [
    [{ id: "agree", label: "I agree", type: "checkbox" }, choice],
    [{ id: "home", label: "Housing", type: "dropdown", options: ["Owner"] }, choice],
    [{ id: "title", label: "Title", type: "radio" }, choice],
    [{ id: "name_of_pet", label: "Pet", type: "text", options: ["Cat"] }, choice],
    [{ id: "job", label: "Occupation", type: "text" }, standard],
    [{ id: "dob", label: "Date of birth", type: "text" }, standard],
    [{ id: "count", label: "People", type: "number" }, standard],
    [null, standard],
    [{ id: "surname", label: "Family name", type: "text" }, long],
    [{ id: "home", label: "Home address", type: "text" }, long],
    [{ id: "pc", label: "Where", question: "What is your postcode?", type: "text" }, long],
    [{ id: "notes", label: "Notes", type: "textarea" }, long],
  ]) {
    assert.deepEqual(recognitionTiming(field), expected, JSON.stringify(field));
    assert.deepEqual(
      recognitionTiming(field, true),
      choice,
      "a pending proposal must use short timing for every field type",
    );
  }

  const url = new URL(buildDeepgramStreamingUrl(16000, [], [], long));
  assert.equal(url.searchParams.get("endpointing"), "1500");
  assert.equal(url.searchParams.get("utterance_end_ms"), "2500");

  const harness = createHarness();
  const recognizer = new DeepgramSpeechRecognizer(
    { tokenUrl: "/voice/deepgram/token", timing: long },
    callbacks([]),
    harness.dependencies,
  );
  await recognizer.start();
  assert.equal(
    new URL(harness.socket.url).searchParams.get("endpointing"),
    "1500",
  );
  harness.socket.open();
  harness.socket.message(
    resultMessage("Akhoon", { isFinal: true, speechFinal: true }),
  );
  assert.ok(
    harness.timeoutDelays.includes(1200),
    "the settle delay must come from the active field's timing",
  );
  recognizer.cancel();
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
  assert.deepEqual(
    recognitionChoiceKeyterms({
      id: "housing",
      label: "Housing arrangement",
      type: "dropdown",
      options: ["Sole tenant", "Owner-occupier"],
    }),
    ["Sole tenant", "Owner-occupier"],
  );
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
      keyterms: ["skip"],
    },
    callbacks(events),
    harness.dependencies,
  );

  await recognizer.start();
  assert.deepEqual(harness.requestedConstraints, {
    audio: MICROPHONE_AUDIO_CONSTRAINTS,
  });
  assert.deepEqual(MICROPHONE_AUDIO_CONSTRAINTS, {
    autoGainControl: true,
    channelCount: { ideal: 1 },
    echoCancellation: true,
    noiseSuppression: true,
  });
  assert.equal(harness.fetchCount, 1);
  assert.deepEqual(harness.socket.protocols, ["bearer", "temporary-jwt"]);
  assert.ok(
    harness.capture.listener,
    "capture must begin before the Deepgram socket opens",
  );
  const bufferedAudio = new ArrayBuffer(8);
  harness.capture.emit(bufferedAudio);
  assert.equal(harness.socket.sent.length, 0);
  harness.socket.open();
  assert.equal(
    harness.socket.sent[0],
    bufferedAudio,
    "audio captured during connection setup must be flushed in order",
  );
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
  assert.equal(harness.capture.stopCount, 1);
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
  assert.equal(harness.capture.stopCount, 1);
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
  assert.equal(events.at(-1).type, "silence");
  assert.equal(events.some((event) => event.type === "complete"), false);
  assert.equal(events.some((event) => event.type === "error"), false);
}

{
  const harness = createHarness();
  const preRollOne = new ArrayBuffer(2);
  const preRollTwo = new ArrayBuffer(4);
  const connecting = new ArrayBuffer(6);
  const live = new ArrayBuffer(8);
  const capture = new FakeCapture(() => undefined, [preRollOne, preRollTwo]);
  const recognizer = new DeepgramSpeechRecognizer(
    {
      tokenUrl: "/voice/deepgram/token",
      initialCapture: capture,
    },
    callbacks([]),
    harness.dependencies,
  );
  await recognizer.start();
  assert.equal(
    harness.requestedConstraints,
    null,
    "barge-in must transfer its live capture without reopening the microphone",
  );
  capture.emit(connecting);
  assert.equal(harness.socket.sent.length, 0);
  assert.equal(
    new URL(harness.socket.url).searchParams.get("sample_rate"),
    "16000",
  );
  harness.socket.open();
  capture.emit(live);
  assert.deepEqual(
    harness.socket.sent,
    [preRollOne, preRollTwo, connecting, live],
    "pre-roll must reach Deepgram first, followed by later audio in order",
  );
  assert.equal(harness.socket.sent[0], preRollOne);
  recognizer.cancel();
  assert.equal(capture.stopCount, 1);
}

{
  const harness = createHarness();
  const saved = [];
  const preRoll = new ArrayBuffer(2);
  const live = new ArrayBuffer(4);
  const capture = new FakeCapture(() => undefined, [preRoll]);
  const recognizer = new DeepgramSpeechRecognizer(
    {
      tokenUrl: "/voice/deepgram/token",
      initialCapture: capture,
      onTurnAudio: (audio) => saved.push(audio),
    },
    callbacks([]),
    harness.dependencies,
  );
  await recognizer.start();
  harness.socket.open();
  capture.emit(live);
  assert.equal(saved.length, 0);
  harness.socket.message(resultMessage("hello", { isFinal: true }));
  harness.socket.message(JSON.stringify({ type: "UtteranceEnd" }));
  assert.equal(saved.length, 1, "a finished turn must be saved exactly once");
  assert.equal(saved[0].chunks[0], preRoll);
  assert.equal(saved[0].chunks[1], live);
  assert.equal(saved[0].sampleRate, 16000);

  for (const end of ["cancel", "error"]) {
    const endHarness = createHarness();
    const notSaved = [];
    const endRecognizer = new DeepgramSpeechRecognizer(
      {
        tokenUrl: "/voice/deepgram/token",
        onTurnAudio: (audio) => notSaved.push(audio),
      },
      callbacks([]),
      endHarness.dependencies,
    );
    await endRecognizer.start();
    endHarness.socket.open();
    endHarness.capture.emit(new ArrayBuffer(2));
    if (end === "cancel") {
      endRecognizer.cancel();
    } else {
      endHarness.socket.error();
    }
    assert.equal(notSaved.length, 0, `a ${end} turn must not be saved`);
  }

  const offHarness = createHarness();
  const offRecognizer = new DeepgramSpeechRecognizer(
    { tokenUrl: "/voice/deepgram/token" },
    callbacks([]),
    offHarness.dependencies,
  );
  await offRecognizer.start();
  offHarness.capture.emit(new ArrayBuffer(2));
  assert.equal(
    offRecognizer.turnAudio.length,
    0,
    "audio must not be retained unless saving was explicitly enabled",
  );
  offRecognizer.cancel();
}

{
  const harness = createHarness({ captureError: true });
  const events = [];
  const recognizer = new DeepgramSpeechRecognizer(
    { tokenUrl: "/voice/deepgram/token" },
    callbacks(events),
    harness.dependencies,
  );
  await recognizer.start();
  assert.equal(events.at(-1).type, "error");
  assert.match(events.at(-1).message, /compatible microphone capture/);
  assert.equal(
    harness.trackStops,
    1,
    "a failed capture must release the microphone",
  );
  assert.equal(harness.fetchCount, 0);
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

function compileToDataUrl(moduleSource, url, importMap = {}) {
  let compiledSource = ts.transpileModule(moduleSource, {
    compilerOptions: {
      module: ts.ModuleKind.ES2020,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: url.pathname,
  }).outputText;
  for (const [specifier, target] of Object.entries(importMap)) {
    compiledSource = compiledSource.replace(`"${specifier}"`, `"${target}"`);
  }
  return `data:text/javascript;base64,${Buffer.from(compiledSource).toString("base64")}`;
}

function callbacks(events) {
  return {
    onConnected: () => events.push({ type: "connected" }),
    onTranscript: (transcript) =>
      events.push({ type: "transcript", transcript }),
    onComplete: (utterance) =>
      events.push({ type: "complete", utterance }),
    onNoSpeech: () => events.push({ type: "silence" }),
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

function createHarness({
  tokenStatus = 200,
  permissionError = false,
  captureError = false,
} = {}) {
  let trackStops = 0;
  let fetchCount = 0;
  let requestedConstraints = null;
  let nextTimer = 1;
  const timeouts = new Map();
  const timeoutDelays = [];
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
  const capture = new FakeCapture(() => {
    stream.getTracks().forEach((track) => track.stop());
  });
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
    startPcmCapture: async () => {
      if (captureError) {
        throw new Error(
          "This browser could not start compatible microphone capture. Keep typing instead.",
        );
      }
      return capture;
    },
    now: () => 2000,
    setTimeout: (callback, delay) => {
      const id = nextTimer++;
      timeouts.set(id, callback);
      timeoutDelays.push(delay);
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
    stream,
    socket,
    capture,
    timeoutDelays,
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
