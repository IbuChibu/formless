import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import ts from "typescript";

const sourceUrl = new URL("../src/voiceAudioCapture.ts", import.meta.url);
const source = await readFile(sourceUrl, "utf8");
const assistantSource = await readFile(
  new URL("../src/useVoiceAssistant.ts", import.meta.url),
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
  PCM_WORKLET_SOURCE,
  browserSupportsPcmCapture,
  encodeWav,
  startPcmCapture,
} = await import(moduleUrl);

{
  const processor = loadWorkletProcessor(16000);
  const quantum = new Float32Array(800).fill(0.5);
  processor.process([[quantum]]);
  assert.equal(processor.posted.length, 0, "a partial chunk must wait");
  processor.process([[quantum]]);
  assert.equal(processor.posted.length, 1);

  const firstChunk = new Int16Array(processor.posted[0].buffer);
  assert.equal(firstChunk.length, 1600, "chunks must hold 100 ms at 16 kHz");
  assert.equal(
    firstChunk[0],
    Math.trunc(0.5 * 0x7fff),
    "audio already at 16 kHz must pass through unchanged",
  );
  assert.deepEqual(
    processor.posted[0].transfer,
    [processor.posted[0].buffer],
    "chunks must be transferred rather than copied",
  );

  const clipped = loadWorkletProcessor(16000);
  clipped.process([[new Float32Array(1600).fill(4)]]);
  clipped.process([[new Float32Array(1600).fill(-4)]]);
  assert.equal(new Int16Array(clipped.posted[0].buffer)[0], 32767);
  assert.equal(new Int16Array(clipped.posted[1].buffer)[0], -32768);

  const silent = loadWorkletProcessor(16000);
  assert.equal(silent.process([[]]), true, "a missing input must stay alive");
  assert.equal(silent.posted.length, 0);
}

{
  const inputRms = 0.5 * Math.SQRT1_2 * 0x7fff;
  for (const inputRate of [48000, 44100, 96000]) {
    const speech = playTone(inputRate, 1000);
    assert.ok(
      Math.abs(speech.samples - 32000) <= 200,
      `${inputRate} Hz must produce 16 kHz output, got ${speech.samples} in 2 s`,
    );
    assert.ok(
      Math.abs(speech.rms - inputRms) / inputRms < 0.03,
      `a 1 kHz tone must keep its level at ${inputRate} Hz, got ${speech.rms}`,
    );
    assert.ok(
      Math.abs(speech.crossingsPerSecond - 2000) <= 8,
      `a 1 kHz tone must keep its pitch at ${inputRate} Hz, got ${speech.crossingsPerSecond}`,
    );
    assert.ok(
      playTone(inputRate, 5000).rms > inputRms * 0.85,
      `consonant energy at 5 kHz must survive at ${inputRate} Hz`,
    );
    assert.ok(
      playTone(inputRate, 12000).rms < inputRms * 0.01,
      `a 12 kHz tone must not alias into speech at ${inputRate} Hz`,
    );
  }
  const upsampled = playTone(8000, 1000);
  assert.ok(Math.abs(upsampled.samples - 32000) <= 200);
  assert.ok(Math.abs(upsampled.crossingsPerSecond - 2000) <= 8);
}

{
  const wav = encodeWav({
    chunks: [
      new Int16Array([1, -2]).buffer,
      new Int16Array([3]).buffer,
    ],
    sampleRate: 48000,
  });
  assert.equal(wav.type, "audio/wav");
  const bytes = await wav.arrayBuffer();
  const view = new DataView(bytes);
  const text = (offset, length) =>
    String.fromCharCode(...new Uint8Array(bytes, offset, length));
  assert.equal(text(0, 4), "RIFF");
  assert.equal(view.getUint32(4, true), bytes.byteLength - 8);
  assert.equal(text(8, 4), "WAVE");
  assert.equal(text(12, 4), "fmt ");
  assert.equal(view.getUint16(20, true), 1, "format must be integer PCM");
  assert.equal(view.getUint16(22, true), 1, "audio must be mono");
  assert.equal(view.getUint32(24, true), 48000);
  assert.equal(view.getUint32(28, true), 96000);
  assert.equal(view.getUint16(32, true), 2);
  assert.equal(view.getUint16(34, true), 16);
  assert.equal(text(36, 4), "data");
  assert.equal(view.getUint32(40, true), 6);
  assert.deepEqual([...new Int16Array(bytes.slice(44))], [1, -2, 3]);
}

{
  const browser = installFakeBrowser();
  assert.equal(browserSupportsPcmCapture(), true);
  const capture = await startPcmCapture(browser.stream, 1000);
  assert.equal(
    capture.sampleRate,
    16000,
    "capture must report the rate it sends, not the 48 kHz device rate",
  );
  assert.deepEqual(browser.node.options, {
    channelCount: 1,
    channelCountMode: "explicit",
  });

  // 16000 samples/s at 2 bytes each: a one-second ring holds 32000 bytes.
  const chunks = Array.from({ length: 30 }, () => new ArrayBuffer(3200));
  chunks.forEach((chunk) => browser.emit(chunk));
  const drained = [];
  capture.setChunkListener((chunk) => drained.push(chunk));
  assert.deepEqual(drained, chunks.slice(-10));

  const live = new ArrayBuffer(3200);
  browser.emit(live);
  assert.equal(drained.at(-1), live, "live audio must follow the pre-roll");
  assert.equal(drained.length, 11);

  capture.stop();
  capture.stop();
  assert.equal(browser.trackStops(), 1, "stop must be idempotent");
  assert.equal(browser.contextCloses(), 1);
  assert.equal(browser.node.port.onmessage, null);
}

{
  const browser = installFakeBrowser();
  const capture = await startPcmCapture(browser.stream);
  const firstChunk = new ArrayBuffer(200);
  const secondChunk = new ArrayBuffer(200);
  browser.emit(firstChunk);
  browser.emit(secondChunk);
  const drained = [];
  capture.setChunkListener((chunk) => drained.push(chunk));
  assert.deepEqual(
    drained,
    [secondChunk],
    "without pre-roll, only the chunk in flight may wait for a listener",
  );
  capture.stop();
}

{
  const browser = installFakeBrowser({ suspended: true });
  const capture = await startPcmCapture(browser.stream);
  assert.equal(browser.context.state, "running");
  capture.stop();
}

{
  const browser = installFakeBrowser({ workletError: true });
  await assert.rejects(
    startPcmCapture(browser.stream),
    /compatible microphone capture/,
  );
  assert.equal(browser.contextCloses(), 1, "failure must not leak a context");
  assert.equal(
    browser.trackStops(),
    0,
    "the caller still owns the stream when capture could not start",
  );
}

{
  const browser = installFakeBrowser({ noWorklet: true });
  assert.equal(browserSupportsPcmCapture(), false);
  assert.ok(browser);
}

assert.match(
  assistantSource,
  /const SAVE_VOICE_TURNS =\s*import\.meta\.env\.DEV && import\.meta\.env\.VITE_SAVE_VOICE_TURNS === "true";/,
  "saving voice turns must require both a development build and the explicit flag",
);
assert.match(
  assistantSource,
  /onTurnAudio: SAVE_VOICE_TURNS \? downloadVoiceTurnAudio : undefined/,
  "voice turns must be saved only through the gated flag",
);

console.log("voice audio capture checks passed");

function playTone(inputRate, frequency) {
  const processor = loadWorkletProcessor(inputRate);
  const inputSamples = inputRate * 2;
  for (let offset = 0; offset < inputSamples; offset += 128) {
    const quantum = new Float32Array(128);
    for (let index = 0; index < quantum.length; index += 1) {
      quantum[index] =
        0.5 * Math.sin((2 * Math.PI * frequency * (offset + index)) / inputRate);
    }
    processor.process([[quantum]]);
  }
  const samples = processor.posted.flatMap(({ buffer }) => [
    ...new Int16Array(buffer),
  ]);
  // Skips the filter's start-up transient.
  const settled = samples.slice(400);
  const rms = Math.sqrt(
    settled.reduce((total, sample) => total + sample * sample, 0) /
      settled.length,
  );
  let crossings = 0;
  for (let index = 1; index < settled.length; index += 1) {
    if (settled[index - 1] < 0 !== settled[index] < 0) {
      crossings += 1;
    }
  }
  return {
    samples: samples.length + processor.filled,
    rms,
    crossingsPerSecond: (crossings / settled.length) * 16000,
  };
}

function loadWorkletProcessor(sampleRate) {
  let Processor = null;
  class FakeAudioWorkletProcessor {
    posted = [];
    port = {
      postMessage: (buffer, transfer) => {
        this.posted.push({ buffer, transfer });
      },
    };
  }
  new Function(
    "AudioWorkletProcessor",
    "registerProcessor",
    "sampleRate",
    PCM_WORKLET_SOURCE,
  )(
    FakeAudioWorkletProcessor,
    (_name, processor) => {
      Processor = processor;
    },
    sampleRate,
  );
  return new Processor();
}

function installFakeBrowser({
  suspended = false,
  workletError = false,
  noWorklet = false,
} = {}) {
  let trackStopCount = 0;
  let contextCloseCount = 0;
  let node = null;
  let context = null;
  const stream = {
    getTracks: () => [
      {
        stop: () => {
          trackStopCount += 1;
        },
      },
    ],
  };

  class FakeAudioWorkletNode {
    port = { onmessage: null };

    constructor(_context, _name, options) {
      this.options = options;
      node = this;
    }

    connect() {}

    disconnect() {}
  }

  class FakeAudioContext {
    state = suspended ? "suspended" : "running";
    sampleRate = 48000;
    destination = {};
    audioWorklet = {
      addModule: async () => {
        if (workletError) {
          throw new Error("worklet blocked");
        }
      },
    };

    constructor() {
      context = this;
    }

    createMediaStreamSource() {
      return { connect: () => undefined, disconnect: () => undefined };
    }

    async resume() {
      this.state = "running";
    }

    async close() {
      this.state = "closed";
      contextCloseCount += 1;
    }
  }

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      AudioContext: FakeAudioContext,
      AudioWorkletNode: noWorklet ? undefined : FakeAudioWorkletNode,
    },
  });

  return {
    stream,
    get node() {
      return node;
    },
    get context() {
      return context;
    },
    emit: (chunk) => node.port.onmessage?.({ data: chunk }),
    trackStops: () => trackStopCount,
    contextCloses: () => contextCloseCount,
  };
}
