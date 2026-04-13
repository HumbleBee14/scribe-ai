"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type VoiceState = "idle" | "listening" | "processing" | "speaking";

interface UseVoiceOptions {
  onTranscript: (text: string) => void;
  autoSend?: boolean;
  autoListen?: boolean; // re-listen after TTS finishes (hands-free loop)
  lang?: string;
}

interface UseVoiceReturn {
  state: VoiceState;
  isListening: boolean;
  isSpeaking: boolean;
  interimText: string;
  startListening: () => void;
  stopListening: () => void;
  speak: (text: string) => void;
  stopSpeaking: () => void;
  toggleListening: () => void;
  handsFreeModeOn: boolean;
  setHandsFreeMode: (on: boolean) => void;
  supported: boolean;
}

export function useVoice({
  onTranscript,
  autoSend = true,
  autoListen = false,
  lang = "en-US",
}: UseVoiceOptions): UseVoiceReturn {
  const [state, setState] = useState<VoiceState>("idle");
  const [interimText, setInterimText] = useState("");
  const [handsFreeModeOn, setHandsFreeMode] = useState(false);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const cachedVoiceRef = useRef<SpeechSynthesisVoice | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  onTranscriptRef.current = onTranscript;

  // Check browser support
  const supported = typeof window !== "undefined" && (
    "SpeechRecognition" in window || "webkitSpeechRecognition" in window
  );

  // Initialize SpeechRecognition
  useEffect(() => {
    if (!supported) return;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false; // stop after silence
    recognition.interimResults = true;
    recognition.lang = lang;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          final += transcript;
        } else {
          interim += transcript;
        }
      }
      setInterimText(interim);
      if (final.trim()) {
        setInterimText("");
        setState("processing");
        onTranscriptRef.current(final.trim());
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      // "no-speech" and "aborted" are normal - user didn't say anything or we stopped
      if (event.error !== "no-speech" && event.error !== "aborted") {
        console.warn("[Voice] STT error:", event.error);
      }
      setState("idle");
      setInterimText("");
    };

    recognition.onend = () => {
      // Only reset to idle if we're still in listening state
      // (processing state means we got a result and shouldn't reset)
      setState((prev) => (prev === "listening" ? "idle" : prev));
      setInterimText("");
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.abort();
    };
  }, [supported, lang]);

  const startListening = useCallback(() => {
    const recognition = recognitionRef.current;
    if (!recognition) return;
    try {
      // Stop any ongoing TTS
      window.speechSynthesis?.cancel();
      recognition.start();
      setState("listening");
      setInterimText("");
    } catch {
      // Already started - ignore
    }
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setState("idle");
    setInterimText("");
  }, []);

  const toggleListening = useCallback(() => {
    if (state === "listening") {
      stopListening();
    } else {
      startListening();
    }
  }, [state, startListening, stopListening]);

  // TTS
  const speak = useCallback((text: string) => {
    if (!window.speechSynthesis) return;

    // Strip markdown, HTML, artifacts, emojis, and noise for clean speech
    const clean = text
      .replace(/<artifact[\s\S]*?<\/artifact>/gi, "") // inline artifacts
      .replace(/<[^>]+>/g, "") // HTML tags
      .replace(/```followups[\s\S]*?```/g, "") // follow-up blocks
      .replace(/```[\s\S]*?```/g, "") // code blocks
      .replace(/\*\*([^*]+)\*\*/g, "$1") // bold
      .replace(/\*([^*]+)\*/g, "$1") // italic
      .replace(/#{1,6}\s/g, "") // headings
      .replace(/`([^`]+)`/g, "$1") // inline code
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1") // links
      .replace(/[|][-]+[|]/g, "") // table separators
      .replace(/[|]/g, ", ") // table pipes to pauses
      // Emojis and unicode symbols
      .replace(/[\u{1F600}-\u{1F64F}]/gu, "") // emoticons
      .replace(/[\u{1F300}-\u{1F5FF}]/gu, "") // misc symbols
      .replace(/[\u{1F680}-\u{1F6FF}]/gu, "") // transport
      .replace(/[\u{1F1E0}-\u{1F1FF}]/gu, "") // flags
      .replace(/[\u{2600}-\u{26FF}]/gu, "") // misc symbols
      .replace(/[\u{2700}-\u{27BF}]/gu, "") // dingbats
      .replace(/[\u{FE00}-\u{FE0F}]/gu, "") // variation selectors
      .replace(/[\u{1F900}-\u{1F9FF}]/gu, "") // supplemental
      .replace(/[\u{200D}]/gu, "") // zero width joiner
      .replace(/^>\s*/gm, "") // markdown blockquotes
      .replace(/^[-*+]\s/gm, "") // bullet list markers (-, *, +)
      // Keep numbered lists but make them speakable: "1." -> "First,", "2." -> "Second," etc
      .replace(/^1\.\s/gm, "First, ")
      .replace(/^2\.\s/gm, "Second, ")
      .replace(/^3\.\s/gm, "Third, ")
      .replace(/^4\.\s/gm, "Fourth, ")
      .replace(/^5\.\s/gm, "Fifth, ")
      .replace(/^6\.\s/gm, "Sixth, ")
      .replace(/^7\.\s/gm, "Seventh, ")
      .replace(/^8\.\s/gm, "Eighth, ")
      .replace(/^9\.\s/gm, "Ninth, ")
      .replace(/^(\d+)\.\s/gm, "Number $1, ") // 10+ fallback
      .replace(/---+/g, "") // horizontal rules
      .replace(/===+/g, "") // horizontal rules alt
      .replace(/\u2014/g, ", ") // em dash to pause
      .replace(/\u2013/g, " to ") // en dash to "to" (e.g. "pages 10-23")
      .replace(/\u2026/g, "...") // ellipsis character
      .replace(/&amp;/g, "and") // HTML entity
      .replace(/&lt;/g, "less than")
      .replace(/&gt;/g, "greater than")
      .replace(/--/g, ", ") // double dashes to pause
      .replace(/\*{2,}/g, "") // leftover asterisks
      .replace(/[_]{2,}/g, "") // leftover underscores
      .replace(/\(p\.\s*\d+[-\d]*\)/g, "") // page refs like (p. 13-14)
      .replace(/\bpage\s+\d+/gi, (m) => m) // keep "page 7" readable
      .replace(/\n{2,}/g, ". ") // double newlines to pause
      .replace(/\n/g, " ") // single newlines
      .replace(/\s{2,}/g, " ") // collapse whitespace
      .trim();

    if (!clean) return;

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.lang = lang;
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    // Pick a female/natural voice -- cached after first selection
    if (!cachedVoiceRef.current) {
      let voices = window.speechSynthesis.getVoices();
      if (voices.length === 0) {
        // Force voice loading (Chrome loads async)
        window.speechSynthesis.speak(new SpeechSynthesisUtterance(""));
        window.speechSynthesis.cancel();
        voices = window.speechSynthesis.getVoices();
      }
      const langPrefix = lang.split("-")[0];
      const preferred = voices.find(
        // macOS premium voices
        (v) => v.lang.startsWith(langPrefix) && /samantha|ava|allison|susan|kate/i.test(v.name)
      ) || voices.find(
        // Windows natural voices
        (v) => v.lang.startsWith(langPrefix) && /natural|jenny|aria|sara/i.test(v.name)
      ) || voices.find(
        // Google voices (Chrome)
        (v) => v.lang.startsWith(langPrefix) && /google.*us|google.*uk/i.test(v.name)
      ) || voices.find(
        // Any female-sounding name
        (v) => v.lang.startsWith(langPrefix) && /zira|hazel|fiona|karen|victoria|tessa|moira|veena/i.test(v.name)
      ) || voices.find(
        // Any matching language
        (v) => v.lang.startsWith(langPrefix)
      );
      if (preferred) cachedVoiceRef.current = preferred;
    }
    if (cachedVoiceRef.current) utterance.voice = cachedVoiceRef.current;

    utterance.onstart = () => setState("speaking");
    utterance.onend = () => {
      setState("idle");
      // Hands-free: auto-listen after speaking
      if (handsFreeModeOn) {
        setTimeout(() => startListening(), 300);
      }
    };
    utterance.onerror = () => setState("idle");

    window.speechSynthesis.speak(utterance);
  }, [lang, handsFreeModeOn, startListening]);

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel();
    setState("idle");
  }, []);

  return {
    state,
    isListening: state === "listening",
    isSpeaking: state === "speaking",
    interimText,
    startListening,
    stopListening,
    speak,
    stopSpeaking,
    toggleListening,
    handsFreeModeOn,
    setHandsFreeMode,
    supported,
  };
}
