import { useCallback, useEffect, useRef, useState } from "react";

import {
  nameConfidenceConcern,
  recognitionChoiceKeyterms,
  recognitionKeyterms,
  type VoiceRecognitionField,
} from "./deepgramSpeechRecognition";
import type { VoiceAssistantControls } from "./useVoiceAssistant";
import {
  isRecoverableVoiceInputError,
  nextAutomaticRecoveryAttempt,
  transitionVoiceSessionMode,
  VOICE_RECOVERY_DELAY_MS,
  VOICE_SILENCE_REOPEN_DELAY_MS,
  voiceSilenceReopenDelay,
  type VoiceSessionControlEvent,
  type VoiceSessionMode,
} from "./voiceSessionPolicy";

export type VoiceInterviewStatus =
  | "inactive"
  | "starting"
  | "assistant_speaking"
  | "interrupted"
  | "requesting_permission"
  | "listening"
  | "processing"
  | "waiting_agent"
  | "awaiting_confirmation"
  | "recovering"
  | "muted"
  | "paused"
  | "complete"
  | "ended"
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
  isMuted: boolean;
  status: VoiceInterviewStatus;
  startInterview: () => void;
  pauseInterview: () => void;
  resumeInterview: () => void;
  muteInterview: () => void;
  unmuteInterview: () => void;
  endInterview: () => void;
  resetInterview: () => void;
  interruptAndListen: () => void;
  retryListening: () => void;
  submitEditedTranscript: (asCorrection: boolean) => void;
};

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
    useState<VoiceSessionMode>("inactive");
  const [baseStatus, setBaseStatus] =
    useState<VoiceInterviewStatus>("inactive");
  const sessionModeRef = useRef<VoiceSessionMode>("inactive");
  const lastHandledAssistantIdRef = useRef<number | null>(null);
  const submitTranscriptRef = useRef<(transcript: string) => void>(() => {});
  const beginListeningRef = useRef<(stream?: MediaStream) => void>(() => {});
  const assistantSpeechSessionRef = useRef(0);
  const listeningTurnRef = useRef(0);
  const recoveryAttemptsRef = useRef(0);
  const consecutiveSilencesRef = useRef(0);
  const recoveryTimerRef = useRef<number | null>(null);
  const localConcernRef = useRef(false);

  const clearRecoveryTimer = useCallback(() => {
    if (recoveryTimerRef.current !== null) {
      window.clearTimeout(recoveryTimerRef.current);
      recoveryTimerRef.current = null;
    }
  }, []);

  const applyMode = useCallback((event: VoiceSessionControlEvent) => {
    const next = transitionVoiceSessionMode(sessionModeRef.current, event);
    sessionModeRef.current = next;
    setSessionMode(next);
  }, []);

  const stopActiveAudio = useCallback(() => {
    const { voice } = optionsRef.current;
    listeningTurnRef.current += 1;
    assistantSpeechSessionRef.current += 1;
    clearRecoveryTimer();
    voice.cancelListening();
    voice.stopSpeaking();
  }, [clearRecoveryTimer]);

  const pauseInterview = useCallback(() => {
    stopActiveAudio();
    applyMode("pause");
    setBaseStatus("paused");
  }, [applyMode, stopActiveAudio]);

  const muteInterview = useCallback(() => {
    stopActiveAudio();
    applyMode("mute");
    setBaseStatus("muted");
  }, [applyMode, stopActiveAudio]);

  const endInterview = useCallback(() => {
    stopActiveAudio();
    lastHandledAssistantIdRef.current = null;
    recoveryAttemptsRef.current = 0;
    consecutiveSilencesRef.current = 0;
    applyMode("end");
    setBaseStatus("ended");
  }, [applyMode, stopActiveAudio]);

  const resetInterview = useCallback(() => {
    stopActiveAudio();
    lastHandledAssistantIdRef.current = null;
    recoveryAttemptsRef.current = 0;
    consecutiveSilencesRef.current = 0;
    localConcernRef.current = false;
    optionsRef.current.voice.resetVoiceSession();
    applyMode("reset");
    setBaseStatus("inactive");
  }, [applyMode, stopActiveAudio]);

  const scheduleListening = useCallback(
    (delayMs: number) => {
      clearRecoveryTimer();
      if (sessionModeRef.current !== "active") {
        return;
      }
      setBaseStatus("recovering");
      recoveryTimerRef.current = window.setTimeout(() => {
        recoveryTimerRef.current = null;
        if (sessionModeRef.current === "active") {
          beginListeningRef.current();
        }
      }, delayMs);
    },
    [clearRecoveryTimer],
  );

  const beginListening = useCallback(
    (initialStream?: MediaStream) => {
      const current = optionsRef.current;
      if (
        sessionModeRef.current !== "active" ||
        current.agentIsBusy ||
        !current.canSendMessage
      ) {
        initialStream?.getTracks().forEach((track) => track.stop());
        return;
      }
      if (!current.voice.inputSupported) {
        initialStream?.getTracks().forEach((track) => track.stop());
        setBaseStatus("unsupported");
        return;
      }

      clearRecoveryTimer();
      listeningTurnRef.current += 1;
      const listeningTurn = listeningTurnRef.current;
      setBaseStatus(
        initialStream
          ? "interrupted"
          : current.hasPendingProposal
            ? "awaiting_confirmation"
            : "starting",
      );
      const keyterms = recognitionKeyterms(current.activeField);
      const choiceKeyterms = recognitionChoiceKeyterms(current.activeField);
      current.voice.startListening(
        (utterance) => {
          if (
            sessionModeRef.current !== "active" ||
            listeningTurnRef.current !== listeningTurn
          ) {
            return;
          }
          listeningTurnRef.current += 1;
          recoveryAttemptsRef.current = 0;
          consecutiveSilencesRef.current = 0;
          const latest = optionsRef.current;
          const concern = nameConfidenceConcern(
            latest.activeField,
            utterance,
          );
          if (concern) {
            localConcernRef.current = true;
            latest.voice.reportInputConcern(concern);
            setBaseStatus("recovering");
            const reopen = () => {
              localConcernRef.current = false;
              latest.voice.clearTranscript();
              scheduleListening(VOICE_SILENCE_REOPEN_DELAY_MS);
            };
            const started = latest.voice.speakAssistantMessage(concern, {
              force: true,
              onEnd: reopen,
              onError: reopen,
            });
            if (!started) {
              reopen();
            }
            return;
          }
          submitTranscriptRef.current(utterance.transcript);
        },
        keyterms,
        () => {
          if (
            sessionModeRef.current !== "active" ||
            listeningTurnRef.current !== listeningTurn
          ) {
            return;
          }
          listeningTurnRef.current += 1;
          current.voice.clearTranscript();
          const delay = voiceSilenceReopenDelay(
            consecutiveSilencesRef.current,
          );
          consecutiveSilencesRef.current += 1;
          scheduleListening(delay);
        },
        initialStream,
        choiceKeyterms,
      );
    },
    [clearRecoveryTimer, scheduleListening],
  );
  beginListeningRef.current = beginListening;

  const continueAfterSpeech = useCallback(() => {
    if (sessionModeRef.current !== "active") {
      return;
    }
    if (optionsRef.current.isFormComplete) {
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
        if (assistantSpeechSessionRef.current !== assistantSpeechSession) {
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
      voice.startInterruptionDetection((stream) => {
        if (
          sessionModeRef.current !== "active" ||
          assistantSpeechSessionRef.current !== assistantSpeechSession
        ) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        assistantSpeechSessionRef.current += 1;
        setBaseStatus("interrupted");
        voice.stopSpeaking();
        beginListening(stream);
      });
    },
    [beginListening, continueAfterSpeech],
  );

  const startOrResume = useCallback(() => {
    const current = optionsRef.current;
    clearRecoveryTimer();
    recoveryAttemptsRef.current = 0;
    consecutiveSilencesRef.current = 0;
    current.voice.clearTranscript();
    applyMode(
      sessionModeRef.current === "inactive" ||
        sessionModeRef.current === "ended"
        ? "start"
        : "resume",
    );
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
    if (
      current.latestAssistantTurn &&
      current.latestAssistantTurn.id !== lastHandledAssistantIdRef.current
    ) {
      speakTurn(current.latestAssistantTurn);
      return;
    }
    if (
      current.activeQuestion &&
      lastHandledAssistantIdRef.current === null
    ) {
      speakTurn({ id: -Date.now(), message: current.activeQuestion });
      return;
    }
    beginListening();
  }, [applyMode, beginListening, clearRecoveryTimer, speakTurn]);

  const interruptAndListen = useCallback(() => {
    if (sessionModeRef.current !== "active") {
      return;
    }
    assistantSpeechSessionRef.current += 1;
    setBaseStatus("interrupted");
    optionsRef.current.voice.stopSpeaking();
    beginListening();
  }, [beginListening]);

  const retryListening = useCallback(() => {
    recoveryAttemptsRef.current = 0;
    optionsRef.current.voice.clearTranscript();
    applyMode("resume");
    beginListening();
  }, [applyMode, beginListening]);

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
    if (sessionMode !== "active" || !options.agentHasError) {
      return;
    }
    stopActiveAudio();
    applyMode("pause");
    setBaseStatus("error");
  }, [applyMode, options.agentHasError, sessionMode, stopActiveAudio]);

  useEffect(() => {
    if (
      sessionMode !== "active" ||
      options.voice.inputStatus !== "error" ||
      localConcernRef.current
    ) {
      return;
    }
    const message = options.voice.inputError ?? "";
    const nextAttempt = isRecoverableVoiceInputError(message)
      ? nextAutomaticRecoveryAttempt(recoveryAttemptsRef.current)
      : null;
    if (nextAttempt !== null) {
      recoveryAttemptsRef.current = nextAttempt;
      options.voice.clearTranscript();
      scheduleListening(VOICE_RECOVERY_DELAY_MS);
      return;
    }
    listeningTurnRef.current += 1;
    assistantSpeechSessionRef.current += 1;
    clearRecoveryTimer();
    options.voice.stopSpeaking();
    applyMode("pause");
    setBaseStatus("error");
  }, [
    applyMode,
    options.voice,
    options.voice.inputError,
    options.voice.inputStatus,
    clearRecoveryTimer,
    scheduleListening,
    sessionMode,
    stopActiveAudio,
  ]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden && sessionModeRef.current === "active") {
        pauseInterview();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [pauseInterview]);

  useEffect(() => {
    return () => {
      listeningTurnRef.current += 1;
      assistantSpeechSessionRef.current += 1;
      clearRecoveryTimer();
      optionsRef.current.voice.cancelListening();
      optionsRef.current.voice.stopSpeaking();
    };
  }, [clearRecoveryTimer]);

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
    isMuted: sessionMode === "muted",
    status,
    startInterview: startOrResume,
    pauseInterview,
    resumeInterview: startOrResume,
    muteInterview,
    unmuteInterview: startOrResume,
    endInterview,
    resetInterview,
    interruptAndListen,
    retryListening,
    submitEditedTranscript,
  };
}

function resolveInterviewStatus(
  sessionMode: VoiceSessionMode,
  baseStatus: VoiceInterviewStatus,
  voice: VoiceAssistantControls,
  agentIsBusy: boolean,
  hasPendingProposal: boolean,
  isFormComplete: boolean,
): VoiceInterviewStatus {
  if (sessionMode === "inactive") {
    return voice.inputSupported ? "inactive" : "unsupported";
  }
  if (sessionMode === "ended") {
    return "ended";
  }
  if (sessionMode === "muted") {
    return "muted";
  }
  if (sessionMode === "paused") {
    return baseStatus === "error" ? "error" : "paused";
  }
  if (voice.outputStatus === "speaking") {
    return "assistant_speaking";
  }
  if (baseStatus === "recovering" || baseStatus === "interrupted") {
    return baseStatus;
  }
  if (voice.inputStatus === "error" || baseStatus === "error") {
    return "error";
  }
  if (agentIsBusy) {
    return "waiting_agent";
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
