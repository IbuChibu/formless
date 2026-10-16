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
  analyzeVoiceActivity,
  initialVoiceActivityGateState,
  startVoiceInterruptionDetector,
  updateVoiceActivityGate,
} = await import(moduleUrl);

function calibratedGate() {
  let gate = initialVoiceActivityGateState();
  gate = updateVoiceActivityGate(gate, 0.012, 0, true).state;
  gate = updateVoiceActivityGate(gate, 0.028, 300, true).state;
  gate = updateVoiceActivityGate(gate, 0.04, 600, true).state;
  const result = updateVoiceActivityGate(gate, 0.03, 900, true);
  assert.equal(result.becameArmed, true);
  assert.equal(result.detected, false);
  return result.state;
}

{
  const samples = new Float32Array(1024);
  fillSpeechWaveform(samples, 0.08);
  const speech = analyzeVoiceActivity(samples);
  assert.ok(speech.level > 0.07);
  assert.equal(speech.speechLike, true);

  samples.fill(0.08);
  assert.equal(analyzeVoiceActivity(samples).speechLike, false);
  samples.fill(0);
  samples[20] = 1;
  assert.equal(analyzeVoiceActivity(samples).speechLike, false);
}

{
  let gate = initialVoiceActivityGateState();
  const duringCalibration = updateVoiceActivityGate(
    gate,
    0.2,
    200,
    true,
  );
  gate = duringCalibration.state;
  assert.equal(duringCalibration.detected, false);
  assert.equal(gate.armed, false);
}

{
  let gate = calibratedGate();
  const spike = updateVoiceActivityGate(gate, 0.11, 940, true);
  gate = spike.state;
  assert.equal(spike.detected, false);
  const quiet = updateVoiceActivityGate(gate, 0.02, 1000, false);
  assert.equal(quiet.detected, false);
  assert.equal(quiet.state.activeSince, null);
}

{
  let gate = calibratedGate();
  for (const [timestamp, level] of [
    [940, 0.045],
    [1100, 0.052],
    [1300, 0.041],
    [1500, 0.05],
  ]) {
    const leakage = updateVoiceActivityGate(
      gate,
      level,
      timestamp,
      true,
    );
    gate = leakage.state;
    assert.equal(leakage.detected, false);
  }
}

{
  let gate = calibratedGate();
  for (const [timestamp, level] of [
    [940, 0.075],
    [1050, 0.09],
    [1160, 0.08],
    [1270, 0.1],
  ]) {
    const activity = updateVoiceActivityGate(
      gate,
      level,
      timestamp,
      true,
    );
    gate = activity.state;
    assert.equal(activity.detected, false);
  }
  const sustainedSpeech = updateVoiceActivityGate(
    gate,
    0.078,
    1380,
    true,
  );
  assert.equal(sustainedSpeech.detected, true);
}

{
  let gate = calibratedGate();
  for (const [timestamp, level] of [
    [940, 0.075],
    [1050, 0.09],
    [1160, 0.08],
    [1270, 0.1],
    [1380, 0.078],
  ]) {
    const nonSpeechSound = updateVoiceActivityGate(
      gate,
      level,
      timestamp,
      false,
    );
    gate = nonSpeechSound.state;
    assert.equal(nonSpeechSound.detected, false);
  }
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

  browser.runFrame(0, 0.012);
  browser.runFrame(300, 0.028);
  browser.runFrame(600, 0.04);
  browser.runFrame(900, 0.03);
  assert.equal(armedCount, 1);
  assert.deepEqual(browser.requestedAudioConstraints(), {
    autoGainControl: false,
    echoCancellation: true,
    noiseSuppression: true,
  });

  browser.runFrame(940, 0.045);
  browser.runFrame(1100, 0.052);
  browser.runFrame(1300, 0.041);
  browser.runFrame(1500, 0.05);
  assert.equal(voiceCount, 0, "playback leakage must not interrupt speech");

  browser.runFrame(1600, 0.075);
  browser.runFrame(1710, 0.09);
  browser.runFrame(1820, 0.08);
  browser.runFrame(1930, 0.1);
  browser.runFrame(2040, 0.078);

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
  let currentSampleKind = "speech";
  let nextFrameId = 1;
  let trackStopCount = 0;
  let contextCloseCount = 0;
  let requestedConstraints = null;
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
    getFloatTimeDomainData: (samples) => {
      if (currentSampleKind === "speech") {
        fillSpeechWaveform(samples, currentLevel);
      } else {
        samples.fill(currentLevel);
      }
    },
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
        getUserMedia: async (constraints) => {
          requestedConstraints = constraints;
          return getUserMedia ? getUserMedia() : stream;
        },
      },
    },
  });

  return {
    stream,
    contextCloses: () => contextCloseCount,
    pendingFrames: () => frames.size,
    requestedAudioConstraints: () => requestedConstraints?.audio,
    runFrame: (timestamp, level, sampleKind = "speech") => {
      currentLevel = level;
      currentSampleKind = sampleKind;
      const entry = frames.entries().next().value;
      assert.ok(entry, "expected a pending animation frame");
      const [id, callback] = entry;
      frames.delete(id);
      callback(timestamp);
    },
    trackStops: () => trackStopCount,
  };
}

function fillSpeechWaveform(samples, level) {
  const amplitude = level * Math.SQRT2;
  for (let index = 0; index < samples.length; index += 1) {
    samples[index] = amplitude * Math.sin((index / 16) * Math.PI * 2);
  }
}

async function flushMicrotasks() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}
