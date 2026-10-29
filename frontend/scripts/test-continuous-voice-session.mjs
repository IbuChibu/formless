import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import ts from "typescript";

const policyUrl = new URL("../src/voiceSessionPolicy.ts", import.meta.url);
const policySource = await readFile(policyUrl, "utf8");
const interviewSource = await readFile(
  new URL("../src/useVoiceInterview.ts", import.meta.url),
  "utf8",
);
const panelSource = await readFile(
  new URL("../src/VoiceAssistantPanel.tsx", import.meta.url),
  "utf8",
);
const compiled = ts.transpileModule(policySource, {
  compilerOptions: {
    module: ts.ModuleKind.ES2020,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: policyUrl.pathname,
}).outputText;
const moduleUrl = `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`;
const {
  isRecoverableVoiceInputError,
  nextAutomaticRecoveryAttempt,
  transitionVoiceSessionMode,
  voiceSilenceReopenDelay,
} = await import(moduleUrl);

let mode = "inactive";
mode = transitionVoiceSessionMode(mode, "start");
assert.equal(mode, "active");
mode = transitionVoiceSessionMode(mode, "mute");
assert.equal(mode, "muted");
mode = transitionVoiceSessionMode(mode, "resume");
assert.equal(mode, "active");
mode = transitionVoiceSessionMode(mode, "pause");
assert.equal(mode, "paused");
mode = transitionVoiceSessionMode(mode, "resume");
assert.equal(mode, "active");
mode = transitionVoiceSessionMode(mode, "end");
assert.equal(mode, "ended");
mode = transitionVoiceSessionMode(mode, "start");
assert.equal(mode, "active");
mode = transitionVoiceSessionMode(mode, "reset");
assert.equal(mode, "inactive");

assert.equal(nextAutomaticRecoveryAttempt(0), 1);
assert.equal(nextAutomaticRecoveryAttempt(1), null);
assert.equal(voiceSilenceReopenDelay(0), 250);
assert.equal(voiceSilenceReopenDelay(1), 500);
assert.equal(voiceSilenceReopenDelay(20), 4000);
assert.equal(
  isRecoverableVoiceInputError("Deepgram voice input disconnected."),
  true,
);
assert.equal(
  isRecoverableVoiceInputError("Microphone access was denied."),
  false,
);
assert.equal(
  isRecoverableVoiceInputError("Deepgram voice input is not configured."),
  false,
);

assert.match(
  interviewSource,
  /current\.voice\.clearTranscript\(\);[\s\S]*voiceSilenceReopenDelay[\s\S]*scheduleListening\(delay\)/,
  "ordinary silence must reopen listening without dispatching a form turn",
);
assert.match(
  interviewSource,
  /nextAutomaticRecoveryAttempt[\s\S]*VOICE_RECOVERY_DELAY_MS/,
  "one transient provider failure must recover automatically",
);
assert.match(
  interviewSource,
  /document\.addEventListener\("visibilitychange"/,
  "backgrounding the page must pause the active microphone session",
);
assert.match(
  interviewSource,
  /startInterruptionDetection\(\(stream\)[\s\S]*beginListening\(stream\)/,
  "barge-in must transfer the live microphone stream into recognition",
);
assert.match(
  interviewSource,
  /listeningTurnRef\.current !== listeningTurn/,
  "stale callbacks must not dispatch a duplicate utterance",
);
for (const control of ["Mute", "Pause", "End"]) {
  assert.match(panelSource, new RegExp(`>${control}<|\\n\\s*${control}\\n`));
}
assert.match(panelSource, /automatically listens again after each/);

console.log("continuous voice session checks passed");
