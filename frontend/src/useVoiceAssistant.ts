import { useCallback, useEffect, useRef, useState } from "react";

import { apiBaseUrl } from "./api";
import {
  browserSupportsDeepgramSpeech,
  DeepgramSpeechRecognizer,
  type DeepgramUtterance,
} from "./deepgramSpeechRecognition";
import {
  browserSupportsVoiceInterruption,
  startVoiceInterruptionDetector,
  type VoiceInterruptionDetector,
} from "./voiceInterruptionDetector";

export type VoiceInputStatus =
  | "idle"
  | "requesting_permission"
  | "listening"
  | "processing"
  | "review"
  | "error"
  | "unsupported";

type VoiceOutputStatus = "idle" | "speaking" | "error" | "unsupported";

export type VoiceInterruptionStatus =
  | "idle"
  | "arming"
  | "armed"
  | "error"
  | "unsupported";

export type VoiceTranscriptFinality = "none" | "interim" | "final";

export type VoiceAssistantControls = {
  inputSupported: boolean;
  inputStatus: VoiceInputStatus;
  inputError: string | null;
  transcript: string;
  transcriptFinality: VoiceTranscriptFinality;
  lastUtterance: DeepgramUtterance | null;
  setTranscript: (value: string) => void;
  startListening: (
    onComplete?: (utterance: DeepgramUtterance) => void,
    keyterms?: string[],
  ) => void;
  stopListening: () => void;
  cancelListening: () => void;
  clearTranscript: () => void;
  reportInputConcern: (message: string) => void;
  outputSupported: boolean;
  outputStatus: VoiceOutputStatus;
  outputError: string | null;
  spokenRepliesEnabled: boolean;
  setSpokenRepliesEnabled: (enabled: boolean) => void;
  interruptionSupported: boolean;
  interruptionStatus: VoiceInterruptionStatus;
  interruptionError: string | null;
  startInterruptionDetection: (onInterrupt: () => void) => void;
  stopInterruptionDetection: () => void;
  speakAssistantMessage: (
    message: string,
    options?: {
      force?: boolean;
      onEnd?: () => void;
      onError?: () => void;
    },
  ) => boolean;
  stopSpeaking: () => void;
  resetVoiceSession: () => void;
};

function browserSupportsVoiceOutput(): boolean {
  return (
    "speechSynthesis" in window &&
    typeof window.SpeechSynthesisUtterance === "function"
  );
}


export default function useVoiceAssistant(): VoiceAssistantControls {
  const inputSupported = browserSupportsDeepgramSpeech();
  const outputSupported = browserSupportsVoiceOutput();
  const interruptionSupported = browserSupportsVoiceInterruption();
  const [inputStatus, setInputStatus] = useState<VoiceInputStatus>(
    inputSupported ? "idle" : "unsupported",
  );
  const [inputError, setInputError] = useState<string | null>(null);
  const [transcript, setTranscriptState] = useState("");
  const [transcriptFinality, setTranscriptFinality] =
    useState<VoiceTranscriptFinality>("none");
  const [lastUtterance, setLastUtterance] =
    useState<DeepgramUtterance | null>(null);
  const [outputStatus, setOutputStatus] = useState<VoiceOutputStatus>(
    outputSupported ? "idle" : "unsupported",
  );
  const [outputError, setOutputError] = useState<string | null>(null);
  const [spokenRepliesEnabled, setSpokenRepliesEnabledState] = useState(false);
  const [interruptionStatus, setInterruptionStatus] =
    useState<VoiceInterruptionStatus>(
      interruptionSupported ? "idle" : "unsupported",
    );
  const [interruptionError, setInterruptionError] = useState<string | null>(
    null,
  );

  const recognitionRef = useRef<DeepgramSpeechRecognizer | null>(null);
  const recognitionSessionRef = useRef(0);
  const recognitionCompleteRef = useRef<
    ((utterance: DeepgramUtterance) => void) | null
  >(null);
  const spokenRepliesEnabledRef = useRef(false);
  const speechSessionRef = useRef(0);
  const interruptionDetectorRef = useRef<VoiceInterruptionDetector | null>(
    null,
  );
  const interruptionSessionRef = useRef(0);

  const setTranscript = useCallback((value: string) => {
    setTranscriptState(value);
    setTranscriptFinality(value.trim() ? "final" : "none");
    setLastUtterance(null);
  }, []);

  const stopInterruptionDetection = useCallback(() => {
    interruptionSessionRef.current += 1;
    interruptionDetectorRef.current?.stop();
    interruptionDetectorRef.current = null;
    setInterruptionStatus(
      interruptionSupported ? "idle" : "unsupported",
    );
  }, [interruptionSupported]);

  const startInterruptionDetection = useCallback(
    (onInterrupt: () => void) => {
      interruptionSessionRef.current += 1;
      const interruptionSession = interruptionSessionRef.current;
      interruptionDetectorRef.current?.stop();
      interruptionDetectorRef.current = null;
      setInterruptionError(null);

      if (!interruptionSupported) {
        setInterruptionStatus("unsupported");
        return;
      }

      setInterruptionStatus("arming");
      const detector = startVoiceInterruptionDetector({
        onArmed: () => {
          if (interruptionSessionRef.current === interruptionSession) {
            setInterruptionStatus("armed");
          }
        },
        onVoice: () => {
          if (interruptionSessionRef.current !== interruptionSession) {
            return;
          }
          interruptionSessionRef.current += 1;
          interruptionDetectorRef.current = null;
          setInterruptionStatus("idle");
          onInterrupt();
        },
        onError: (message) => {
          if (interruptionSessionRef.current !== interruptionSession) {
            return;
          }
          interruptionDetectorRef.current = null;
          setInterruptionError(message);
          setInterruptionStatus("error");
        },
      });
      interruptionDetectorRef.current = detector;
    },
    [interruptionSupported],
  );

  const stopSpeaking = useCallback(() => {
    stopInterruptionDetection();
    if (outputSupported) {
      speechSessionRef.current += 1;
      window.speechSynthesis.cancel();
      setOutputStatus("idle");
    }
  }, [outputSupported, stopInterruptionDetection]);

  const speakAssistantMessage = useCallback(
    (
      message: string,
      options?: {
        force?: boolean;
        onEnd?: () => void;
        onError?: () => void;
      },
    ) => {
      if (
        (!spokenRepliesEnabledRef.current && !options?.force) ||
        !outputSupported
      ) {
        return false;
      }

      speechSessionRef.current += 1;
      const speechSession = speechSessionRef.current;
      stopInterruptionDetection();
      window.speechSynthesis.cancel();
      setOutputError(null);
      const utterance = new window.SpeechSynthesisUtterance(message);
      utterance.lang = window.navigator.language || "en-GB";
      utterance.rate = 0.98;
      utterance.onstart = () => {
        if (speechSessionRef.current === speechSession) {
          setOutputStatus("speaking");
        }
      };
      utterance.onend = () => {
        if (speechSessionRef.current === speechSession) {
          setOutputStatus("idle");
          options?.onEnd?.();
        }
      };
      utterance.onerror = () => {
        if (speechSessionRef.current !== speechSession) {
          return;
        }
        speechSessionRef.current += 1;
        setOutputError(
          "This response could not be spoken. It remains available as text.",
        );
        setOutputStatus("error");
        options?.onError?.();
      };
      window.speechSynthesis.speak(utterance);
      return true;
    },
    [outputSupported, stopInterruptionDetection],
  );

  const setSpokenRepliesEnabled = useCallback(
    (enabled: boolean) => {
      spokenRepliesEnabledRef.current = enabled;
      setSpokenRepliesEnabledState(enabled);
      setOutputError(null);
      if (!enabled) {
        stopSpeaking();
      }
    },
    [stopSpeaking],
  );

  const cancelListening = useCallback(() => {
    recognitionSessionRef.current += 1;
    recognitionRef.current?.cancel();
    recognitionRef.current = null;
    recognitionCompleteRef.current = null;
    setInputError(null);
    setTranscriptState("");
    setTranscriptFinality("none");
    setLastUtterance(null);
    setInputStatus(inputSupported ? "idle" : "unsupported");
  }, [inputSupported]);

  const startListening = useCallback(
    (
      onComplete?: (utterance: DeepgramUtterance) => void,
      keyterms: string[] = [],
    ) => {
      if (!inputSupported) {
        setInputStatus("unsupported");
        return;
      }

      recognitionSessionRef.current += 1;
      const recognitionSession = recognitionSessionRef.current;
      recognitionRef.current?.cancel();
      stopSpeaking();
      recognitionCompleteRef.current = onComplete ?? null;
      setInputError(null);
      setTranscriptState("");
      setTranscriptFinality("none");
      setLastUtterance(null);
      const recognition = new DeepgramSpeechRecognizer(
        {
          tokenUrl: `${apiBaseUrl}/voice/deepgram/token`,
          keyterms,
        },
        {
          onConnected: () => {
            if (recognitionSessionRef.current === recognitionSession) {
              setInputStatus("listening");
            }
          },
          onTranscript: (nextTranscript) => {
            if (recognitionSessionRef.current !== recognitionSession) {
              return;
            }
            setTranscriptState(nextTranscript);
            setTranscriptFinality("interim");
          },
          onComplete: (utterance) => {
            if (recognitionSessionRef.current !== recognitionSession) {
              return;
            }
            recognitionRef.current = null;
            setTranscriptState(utterance.transcript);
            setTranscriptFinality("final");
            setLastUtterance(utterance);
            setInputStatus("review");
            const complete = recognitionCompleteRef.current;
            recognitionCompleteRef.current = null;
            complete?.(utterance);
          },
          onError: (message) => {
            if (recognitionSessionRef.current !== recognitionSession) {
              return;
            }
            recognitionRef.current = null;
            recognitionCompleteRef.current = null;
            setInputError(message);
            setInputStatus("error");
          },
        },
      );
      recognitionRef.current = recognition;
      setInputStatus("requesting_permission");
      void recognition.start();
    },
    [inputSupported, stopSpeaking],
  );

  const stopListening = useCallback(() => {
    if (!recognitionRef.current) {
      return;
    }
    setInputStatus("processing");
    recognitionRef.current.stop();
  }, []);

  const clearTranscript = useCallback(() => {
    recognitionCompleteRef.current = null;
    setInputError(null);
    setTranscriptState("");
    setTranscriptFinality("none");
    setLastUtterance(null);
    setInputStatus(inputSupported ? "idle" : "unsupported");
  }, [inputSupported]);

  const reportInputConcern = useCallback((message: string) => {
    recognitionCompleteRef.current = null;
    setInputError(message);
    setInputStatus("error");
  }, []);

  const resetVoiceSession = useCallback(() => {
    cancelListening();
    stopSpeaking();
    setInterruptionError(null);
  }, [cancelListening, stopSpeaking]);

  useEffect(() => {
    return () => {
      recognitionSessionRef.current += 1;
      speechSessionRef.current += 1;
      interruptionSessionRef.current += 1;
      recognitionRef.current?.cancel();
      interruptionDetectorRef.current?.stop();
      interruptionDetectorRef.current = null;
      recognitionCompleteRef.current = null;
      if (outputSupported) {
        window.speechSynthesis.cancel();
      }
    };
  }, [outputSupported]);

  return {
    inputSupported,
    inputStatus,
    inputError,
    transcript,
    transcriptFinality,
    lastUtterance,
    setTranscript,
    startListening,
    stopListening,
    cancelListening,
    clearTranscript,
    reportInputConcern,
    outputSupported,
    outputStatus,
    outputError,
    spokenRepliesEnabled,
    setSpokenRepliesEnabled,
    interruptionSupported,
    interruptionStatus,
    interruptionError,
    startInterruptionDetection,
    stopInterruptionDetection,
    speakAssistantMessage,
    stopSpeaking,
    resetVoiceSession,
  };
}
