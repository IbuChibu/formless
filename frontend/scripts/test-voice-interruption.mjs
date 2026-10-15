import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import ts from "typescript";

const sourceUrl = new URL(
  "../src/voiceInterruptionDetector.ts",
  import.meta.url,
);
const source = await readFile(sourceUrl, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2020,
    target: ts.ScriptTarget.ES2020,
  },
  fileName: sourceUrl.pathname,
}).outputText;
const moduleUrl = `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`;
const {
  initialVoiceActivityGateState,
  startVoiceInterruptionDetector,
  updateVoiceActivityGate,
} = await import(moduleUrl);

function calibratedGate() {
  let gate = initialVoiceActivityGateState();
  gate = updateVoiceActivityGate(gate, 0.01, 0).state;
  gate = updateVoiceActivityGate(gate, 0.012, 350).state;
  const result = updateVoiceActivityGate(gate, 0.011, 700);
  assert.equal(result.becameArmed, true);
  assert.equal(result.detected, false);
  return result.state;
}

{
  let gate = initialVoiceActivityGateState();
  const duringCalibration = updateVoiceActivityGate(gate, 0.2, 200);
  gate = duringCalibration.state;
  assert.equal(duringCalibration.detected, false);
  assert.equal(gate.armed, false);
}

{
  let gate = calibratedGate();
  const spike = updateVoiceActivityGate(gate, 0.09, 720);
  gate = spike.state;
  assert.equal(spike.detected, false);
  const quiet = updateVoiceActivityGate(gate, 0.01, 780);
  assert.equal(quiet.detected, false);
  assert.equal(quiet.state.activeSince, null);
}

{
  let gate = calibratedGate();
  gate = updateVoiceActivityGate(gate, 0.09, 720).state;
  const sustained = updateVoiceActivityGate(gate, 0.08, 905);
  assert.equal(sustained.detected, true);
}

{
  const browser = installFakeBrowser();
  let armedCount = 0;
  let voiceCount = 0;
  const errors = [];
  startVoiceInterruptionDetector({
    onArmed: () => {
      armedCount += 1;
    },
    onVoice: () => {
      voiceCount += 1;
    },
    onError: (message) => errors.push(message),
  });
  await flushMicrotasks();

  browser.runFrame(0, 0.01);
  browser.runFrame(350, 0.012);
  browser.runFrame(700, 0.011);
  assert.equal(armedCount, 1);
  browser.runFrame(720, 0.09);
  browser.runFrame(780, 0.01);
  assert.equal(voiceCount, 0);
  browser.runFrame(800, 0.09);
  browser.runFrame(990, 0.08);

  assert.equal(voiceCount, 1);
  assert.deepEqual(errors, []);
  assert.equal(browser.trackStops(), 1);
  assert.equal(browser.contextCloses(), 1);
  assert.equal(browser.pendingFrames(), 0);
}

{
  let resolveStream;
  const browser = installFakeBrowser(
    () => new Promise((resolve) => {
      resolveStream = resolve;
    }),
  );
  let voiceCount = 0;
  const detector = startVoiceInterruptionDetector({
    onArmed: () => undefined,
    onVoice: () => {
      voiceCount += 1;
    },
    onError: () => undefined,
  });
  detector.stop();
  resolveStream(browser.stream);
  await flushMicrotasks();

  assert.equal(voiceCount, 0);
  assert.equal(browser.trackStops(), 1);
  assert.equal(browser.pendingFrames(), 0);
}

console.log("voice interruption policy checks passed");

function installFakeBrowser(getUserMedia) {
  let currentLevel = 0;
  let nextFrameId = 1;
  let trackStopCount = 0;
  let contextCloseCount = 0;
  const frames = new Map();
  const stream = {
    getTracks: () => [
      {
        stop: () => {
          trackStopCount += 1;
        },
      },
    ],
  };
  const analyser = {
    fftSize: 1024,
    smoothingTimeConstant: 0,
    getFloatTimeDomainData: (samples) => samples.fill(currentLevel),
  };

  class FakeAudioContext {
    state = "running";

    createAnalyser() {
      return analyser;
    }

    createMediaStreamSource() {
      return {
        connect: () => undefined,
        disconnect: () => undefined,
      };
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
      cancelAnimationFrame: (id) => frames.delete(id),
      isSecureContext: true,
      requestAnimationFrame: (callback) => {
        const id = nextFrameId;
        nextFrameId += 1;
        frames.set(id, callback);
        return id;
      },
    },
  });
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: {
      mediaDevices: {
        getUserMedia: getUserMedia ?? (async () => stream),
      },
    },
  });

  return {
    stream,
    contextCloses: () => contextCloseCount,
    pendingFrames: () => frames.size,
    runFrame: (timestamp, level) => {
      currentLevel = level;
      const entry = frames.entries().next().value;
      assert.ok(entry, "expected a pending animation frame");
      const [id, callback] = entry;
      frames.delete(id);
      callback(timestamp);
    },
    trackStops: () => trackStopCount,
  };
}

async function flushMicrotasks() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}
