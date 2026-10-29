import { useCallback, useEffect, useRef, useState } from "react";

import {
  nameConfidenceConcern,
  recognitionKeyterms,
  type VoiceRecognitionField,
} from "./deepgramSpeechRecognition";
import type { VoiceAssistantControls } from "./useVoiceAssistant";

export type VoiceInterviewStatus =
  | "inactive"
  | "starting"
  | "assistant_speaking"
  | "requesting_permission"
  | "listening"
  | "processing"
  | "waiting_agent"
  | "awaiting_confirmation"
  | "paused"
  | "complete"
  | "error"
  | "unsupported";

type AssistantTurn = {
  id: number;
  message: string;
};

type VoiceInterviewOptions = {
  voice: VoiceAssistantControls;
  agentIsBusy: boolean;
  agentHasError: boolean;
  canSendMessage: boolean;
  needsAdvance: boolean;
  latestAssistantTurn: AssistantTurn | null;
  activeField: VoiceRecognitionField | null;
  activeQuestion: string | null;
  hasPendingProposal: boolean;
  isFormComplete: boolean;
  onAdvance: () => void;
  onSendMessage: (message: string) => void;
};

export type VoiceInterviewControls = {
  isActive: boolean;
  isPaused: boolean;
  status: VoiceInterviewStatus;
  startInterview: () => void;
  pauseInterview: () => void;
  resumeInterview: () => void;
  endInterview: () => void;
  resetInterview: () => void;
  interruptAndListen: () => void;
  retryListening: () => void;
  submitEditedTranscript: (asCorrection: boolean) => void;
};

type SessionMode = "inactive" | "active" | "paused";

type VoiceTurnIntent =
  | { type: "message"; message: string }
  | { type: "pause" };

const pausePhrases = new Set([
  "pause",
  "pause conversation",
  "pause the conversation",
  "stop for now",
  "stop listening",
]);

export default function useVoiceInterview(
  options: VoiceInterviewOptions,
): VoiceInterviewControls {
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const [sessionMode, setSessionMode] =
    useState<SessionMode>("inactive");
  const [baseStatus, setBaseStatus] =
    useState<VoiceInterviewStatus>("inactive");
  const sessionModeRef = useRef<SessionMode>("inactive");
  const lastHandledAssistantIdRef = useRef<number | null>(null);
  const submitTranscriptRef = useRef<(transcript: string) => void>(() => {});
  const assistantSpeechSessionRef = useRef(0);

  const setMode = useCallback((mode: SessionMode) => {
    sessionModeRef.current = mode;
    setSessionMode(mode);
  }, []);

  const pauseInterview = useCallback(() => {
    const { voice } = optionsRef.current;
    assistantSpeechSessionRef.current += 1;
    voice.cancelListening();
    voice.stopSpeaking();
    setMode("paused");
    setBaseStatus("paused");
  }, [setMode]);

  const endInterview = useCallback(() => {
    const { voice } = optionsRef.current;
    assistantSpeechSessionRef.current += 1;
    voice.cancelListening();
    voice.stopSpeaking();
    lastHandledAssistantIdRef.current = null;
    setMode("inactive");
    setBaseStatus("inactive");
  }, [setMode]);

  const resetInterview = useCallback(() => {
    endInterview();
    optionsRef.current.voice.resetVoiceSession();
  }, [endInterview]);

  const beginListening = useCallback(() => {
    const current = optionsRef.current;
    if (
      sessionModeRef.current !== "active" ||
      current.agentIsBusy ||
      !current.canSendMessage
    ) {
      return;
    }
    if (!current.voice.inputSupported) {
      setBaseStatus("unsupported");
      return;
    }

    setBaseStatus(
      current.hasPendingProposal ? "awaiting_confirmation" : "starting",
    );
    const keyterms = recognitionKeyterms(current.activeField);
    current.voice.startListening((utterance) => {
      const concern = nameConfidenceConcern(current.activeField, utterance);
      if (concern) {
        current.voice.reportInputConcern(concern);
        setBaseStatus("error");
        return;
      }
      submitTranscriptRef.current(utterance.transcript);
    }, keyterms);
  }, []);

  const continueAfterSpeech = useCallback(() => {
    if (sessionModeRef.current !== "active") {
      return;
    }

    const current = optionsRef.current;
    if (current.isFormComplete) {
      setBaseStatus("complete");
      return;
    }
    beginListening();
  }, [beginListening]);

  const speakTurn = useCallback(
    (turn: AssistantTurn) => {
      if (sessionModeRef.current !== "active") {
        return;
      }
      lastHandledAssistantIdRef.current = turn.id;
      setBaseStatus("assistant_speaking");

      const { voice } = optionsRef.current;
      assistantSpeechSessionRef.current += 1;
      const assistantSpeechSession = assistantSpeechSessionRef.current;
      const finishSpeechTurn = () => {
        if (
          assistantSpeechSessionRef.current !== assistantSpeechSession
        ) {
          return;
        }
        assistantSpeechSessionRef.current += 1;
        voice.stopInterruptionDetection();
        continueAfterSpeech();
      };
      const started = voice.speakAssistantMessage(turn.message, {
        force: true,
        onEnd: finishSpeechTurn,
        onError: finishSpeechTurn,
      });
      if (!started) {
        finishSpeechTurn();
        return;
      }
      voice.startInterruptionDetection(() => {
        if (
          sessionModeRef.current !== "active" ||
          assistantSpeechSessionRef.current !== assistantSpeechSession
        ) {
          return;
        }
        assistantSpeechSessionRef.current += 1;
        voice.stopSpeaking();
        beginListening();
      });
    },
    [beginListening, continueAfterSpeech],
  );

  const startOrResume = useCallback(() => {
    const current = optionsRef.current;
    setMode("active");
    setBaseStatus("starting");

    if (current.agentIsBusy) {
      setBaseStatus("waiting_agent");
      return;
    }
    if (current.needsAdvance) {
      current.onAdvance();
      setBaseStatus("waiting_agent");
      return;
    }
    if (current.latestAssistantTurn) {
      speakTurn(current.latestAssistantTurn);
      return;
    }
    if (current.activeQuestion) {
      speakTurn({ id: -Date.now(), message: current.activeQuestion });
      return;
    }
    beginListening();
  }, [beginListening, setMode, speakTurn]);

  const interruptAndListen = useCallback(() => {
    if (sessionModeRef.current !== "active") {
      return;
    }
    assistantSpeechSessionRef.current += 1;
    optionsRef.current.voice.stopSpeaking();
    beginListening();
  }, [beginListening]);

  const retryListening = useCallback(() => {
    if (sessionModeRef.current !== "active") {
      setMode("active");
    }
    beginListening();
  }, [beginListening, setMode]);

  submitTranscriptRef.current = (transcript: string) => {
    const current = optionsRef.current;
    if (sessionModeRef.current !== "active" || current.agentIsBusy) {
      return;
    }

    const intent = classifyVoiceTurn(transcript);
    if (intent.type === "pause") {
      pauseInterview();
      return;
    }

    setBaseStatus("waiting_agent");
    current.onSendMessage(intent.message);
  };

  const submitEditedTranscript = useCallback((asCorrection: boolean) => {
    const current = optionsRef.current;
    const transcript = current.voice.transcript.trim();
    if (!transcript || current.agentIsBusy) {
      return;
    }
    void asCorrection;
    submitTranscriptRef.current(transcript);
  }, []);

  useEffect(() => {
    const turn = options.latestAssistantTurn;
    if (
      sessionMode !== "active" ||
      options.agentIsBusy ||
      !turn ||
      turn.id === lastHandledAssistantIdRef.current
    ) {
      return;
    }
    speakTurn(turn);
  }, [
    options.agentIsBusy,
    options.latestAssistantTurn,
    sessionMode,
    speakTurn,
  ]);

  useEffect(() => {
    if (sessionMode !== "active") {
      return;
    }
    if (options.agentHasError) {
      setBaseStatus("error");
    }
  }, [options.agentHasError, sessionMode]);

  const status = resolveInterviewStatus(
    sessionMode,
    baseStatus,
    options.voice,
    options.agentIsBusy,
    options.hasPendingProposal,
    options.isFormComplete,
  );

  return {
    isActive: sessionMode === "active",
    isPaused: sessionMode === "paused",
    status,
    startInterview: startOrResume,
    pauseInterview,
    resumeInterview: startOrResume,
    endInterview,
    resetInterview,
    interruptAndListen,
    retryListening,
    submitEditedTranscript,
  };
}

function resolveInterviewStatus(
  sessionMode: SessionMode,
  baseStatus: VoiceInterviewStatus,
  voice: VoiceAssistantControls,
  agentIsBusy: boolean,
  hasPendingProposal: boolean,
  isFormComplete: boolean,
): VoiceInterviewStatus {
  if (sessionMode === "inactive") {
    return voice.inputSupported ? "inactive" : "unsupported";
  }
  if (sessionMode === "paused") {
    return "paused";
  }
  if (voice.inputStatus === "error" || baseStatus === "error") {
    return "error";
  }
  if (agentIsBusy) {
    return "waiting_agent";
  }
  if (voice.outputStatus === "speaking") {
    return "assistant_speaking";
  }
  if (!voice.inputSupported) {
    return "unsupported";
  }
  if (voice.inputStatus === "requesting_permission") {
    return "requesting_permission";
  }
  if (voice.inputStatus === "listening") {
    return "listening";
  }
  if (voice.inputStatus === "processing") {
    return "processing";
  }
  if (hasPendingProposal) {
    return "awaiting_confirmation";
  }
  if (isFormComplete) {
    return "complete";
  }
  return baseStatus;
}

function classifyVoiceTurn(transcript: string): VoiceTurnIntent {
  const trimmedTranscript = transcript.trim();
  const normalized = normalizeVoiceCommand(trimmedTranscript);

  if (pausePhrases.has(normalized)) {
    return { type: "pause" };
  }
  return { type: "message", message: trimmedTranscript };
}

function normalizeVoiceCommand(value: string): string {
  return value
    .toLocaleLowerCase()
    .replace(/[,.!?;:]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
