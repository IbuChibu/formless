import { useCallback, useEffect, useRef, useState } from "react";

export type VoiceInputStatus =
  | "idle"
  | "requesting_permission"
  | "listening"
  | "processing"
  | "review"
  | "error"
  | "unsupported";

type VoiceOutputStatus = "idle" | "speaking" | "error" | "unsupported";

interface SpeechRecognitionAlternativeLike {
  transcript: string;
}

interface SpeechRecognitionResultLike {
  readonly isFinal: boolean;
  readonly length: number;
  readonly [index: number]: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionResultListLike {
  readonly length: number;
  readonly [index: number]: SpeechRecognitionResultLike;
}

interface SpeechRecognitionEventLike extends Event {
  readonly results: SpeechRecognitionResultListLike;
}

interface SpeechRecognitionErrorEventLike extends Event {
  readonly error: string;
  readonly message?: string;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onstart: (() => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

export type VoiceAssistantControls = {
  inputSupported: boolean;
  inputStatus: VoiceInputStatus;
  inputError: string | null;
  transcript: string;
  setTranscript: (value: string) => void;
  startListening: () => void;
  stopListening: () => void;
  cancelListening: () => void;
  clearTranscript: () => void;
  outputSupported: boolean;
  outputStatus: VoiceOutputStatus;
  outputError: string | null;
  spokenRepliesEnabled: boolean;
  setSpokenRepliesEnabled: (enabled: boolean) => void;
  speakAssistantMessage: (message: string) => void;
  stopSpeaking: () => void;
  resetVoiceSession: () => void;
};

function getSpeechRecognitionConstructor():
  | SpeechRecognitionConstructor
  | undefined {
  return window.SpeechRecognition ?? window.webkitSpeechRecognition;
}

function browserSupportsVoiceInput(): boolean {
  return window.isSecureContext && Boolean(getSpeechRecognitionConstructor());
}

function browserSupportsVoiceOutput(): boolean {
  return (
    "speechSynthesis" in window &&
    typeof window.SpeechSynthesisUtterance === "function"
  );
}

function recognitionErrorMessage(error: string): string {
  const messages: Record<string, string> = {
    "not-allowed":
      "Microphone access was denied. Allow microphone access for this site, then try again.",
    "service-not-allowed":
      "Speech recognition is blocked by this browser. Check the site permissions or keep typing.",
    "audio-capture":
      "No working microphone was found. Check your microphone and try again.",
    network:
      "The browser speech service could not be reached. Try again or keep typing.",
    "no-speech":
      "I didn't hear any speech. Try again when you are ready, or type your answer.",
    "language-not-supported":
      "Speech recognition does not support your browser language. You can keep typing instead.",
  };

  return (
    messages[error] ??
    "Voice input could not be completed. Try again or keep typing your answer."
  );
}

function transcriptFromResults(results: SpeechRecognitionResultListLike): string {
  const segments: string[] = [];
  for (let index = 0; index < results.length; index += 1) {
    const transcript = results[index][0]?.transcript.trim();
    if (transcript) {
      segments.push(transcript);
    }
  }
  return segments.join(" ").trim();
}

export default function useVoiceAssistant(): VoiceAssistantControls {
  const inputSupported = browserSupportsVoiceInput();
  const outputSupported = browserSupportsVoiceOutput();
  const [inputStatus, setInputStatus] = useState<VoiceInputStatus>(
    inputSupported ? "idle" : "unsupported",
  );
  const [inputError, setInputError] = useState<string | null>(null);
  const [transcript, setTranscriptState] = useState("");
  const [outputStatus, setOutputStatus] = useState<VoiceOutputStatus>(
    outputSupported ? "idle" : "unsupported",
  );
  const [outputError, setOutputError] = useState<string | null>(null);
  const [spokenRepliesEnabled, setSpokenRepliesEnabledState] = useState(false);

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const recognitionSessionRef = useRef(0);
  const transcriptRef = useRef("");
  const cancelRequestedRef = useRef(false);
  const recognitionFailedRef = useRef(false);
  const spokenRepliesEnabledRef = useRef(false);
  const speechSessionRef = useRef(0);

  const setTranscript = useCallback((value: string) => {
    transcriptRef.current = value;
    setTranscriptState(value);
  }, []);

  const stopSpeaking = useCallback(() => {
    if (outputSupported) {
      speechSessionRef.current += 1;
      window.speechSynthesis.cancel();
      setOutputStatus("idle");
    }
  }, [outputSupported]);

  const speakAssistantMessage = useCallback(
    (message: string) => {
      if (!spokenRepliesEnabledRef.current || !outputSupported) {
        return;
      }

      speechSessionRef.current += 1;
      const speechSession = speechSessionRef.current;
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
        }
      };
      utterance.onerror = () => {
        if (speechSessionRef.current !== speechSession) {
          return;
        }
        setOutputError(
          "This response could not be spoken. It remains available as text.",
        );
        setOutputStatus("error");
      };
      window.speechSynthesis.speak(utterance);
    },
    [outputSupported],
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
    cancelRequestedRef.current = true;
    recognitionSessionRef.current += 1;
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    recognitionFailedRef.current = false;
    setInputError(null);
    setTranscript("");
    setInputStatus(inputSupported ? "idle" : "unsupported");
  }, [inputSupported, setTranscript]);

  const startListening = useCallback(() => {
    const SpeechRecognition = getSpeechRecognitionConstructor();
    if (!inputSupported || !SpeechRecognition) {
      setInputStatus("unsupported");
      return;
    }

    recognitionSessionRef.current += 1;
    const recognitionSession = recognitionSessionRef.current;
    recognitionRef.current?.abort();
    stopSpeaking();
    cancelRequestedRef.current = false;
    recognitionFailedRef.current = false;
    setInputError(null);
    setTranscript("");

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = window.navigator.language || "en-GB";
    recognition.maxAlternatives = 1;
    recognition.onstart = () => {
      if (recognitionSessionRef.current === recognitionSession) {
        setInputStatus("listening");
      }
    };
    recognition.onresult = (event) => {
      if (recognitionSessionRef.current !== recognitionSession) {
        return;
      }
      const nextTranscript = transcriptFromResults(event.results);
      if (nextTranscript) {
        setTranscript(nextTranscript);
      }
    };
    recognition.onerror = (event) => {
      if (recognitionSessionRef.current !== recognitionSession) {
        return;
      }
      if (event.error === "aborted" && cancelRequestedRef.current) {
        return;
      }
      recognitionFailedRef.current = true;
      setInputError(recognitionErrorMessage(event.error));
      setInputStatus("error");
    };
    recognition.onend = () => {
      if (recognitionSessionRef.current !== recognitionSession) {
        return;
      }
      if (recognitionRef.current === recognition) {
        recognitionRef.current = null;
      }
      if (cancelRequestedRef.current) {
        cancelRequestedRef.current = false;
        return;
      }
      if (recognitionFailedRef.current) {
        return;
      }
      if (transcriptRef.current.trim()) {
        setInputStatus("review");
        return;
      }
      setInputError(
        "I didn't hear any speech. Try again when you are ready, or type your answer.",
      );
      setInputStatus("error");
    };

    recognitionRef.current = recognition;
    setInputStatus("requesting_permission");
    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setInputError(
        "Voice input could not start. Try again or keep typing your answer.",
      );
      setInputStatus("error");
    }
  }, [inputSupported, setTranscript, stopSpeaking]);

  const stopListening = useCallback(() => {
    if (!recognitionRef.current) {
      return;
    }
    setInputStatus("processing");
    try {
      recognitionRef.current.stop();
    } catch {
      recognitionRef.current.abort();
    }
  }, []);

  const clearTranscript = useCallback(() => {
    setInputError(null);
    setTranscript("");
    setInputStatus(inputSupported ? "idle" : "unsupported");
  }, [inputSupported, setTranscript]);

  const resetVoiceSession = useCallback(() => {
    cancelListening();
    stopSpeaking();
  }, [cancelListening, stopSpeaking]);

  useEffect(() => {
    return () => {
      cancelRequestedRef.current = true;
      recognitionSessionRef.current += 1;
      speechSessionRef.current += 1;
      recognitionRef.current?.abort();
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
    setTranscript,
    startListening,
    stopListening,
    cancelListening,
    clearTranscript,
    outputSupported,
    outputStatus,
    outputError,
    spokenRepliesEnabled,
    setSpokenRepliesEnabled,
    speakAssistantMessage,
    stopSpeaking,
    resetVoiceSession,
  };
}
