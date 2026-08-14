"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Send, Mic, MicOff, Volume2, X, Sparkles, Loader2, AlertCircle } from "lucide-react";
import { api } from "../../lib/api";
import "./SupportButton.css";

const GREETING = "Hey! How can I help you today?";

// Find optimal Web Speech Synthesis Voice
function getAssistantVoice() {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  const preferred = [
    "Google UK English Female",
    "Google US English",
    "Samantha",
    "Microsoft Zira Desktop",
    "Microsoft Zira",
    "Karen",
    "Daniel",
    "Victoria",
  ];
  for (const name of preferred) {
    const voice = voices.find((v) => v.name.includes(name));
    if (voice) return voice;
  }
  return voices.find((v) => v.lang.startsWith("en")) || voices[0] || null;
}

export default function SupportButton() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [micError, setMicError] = useState("");

  const inputRef = useRef(null);
  const msgsEndRef = useRef(null);
  const recognitionRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const messageRef = useRef(message);

  // Refs for persistent event handling without closure stale state
  const openRef = useRef(open);
  const isListeningRef = useRef(isListening);
  const isSpeakingRef = useRef(isSpeaking);
  const loadingRef = useRef(loading);

  useEffect(() => { openRef.current = open; }, [open]);
  useEffect(() => { isListeningRef.current = isListening; }, [isListening]);
  useEffect(() => { isSpeakingRef.current = isSpeaking; }, [isSpeaking]);
  useEffect(() => { loadingRef.current = loading; }, [loading]);
  useEffect(() => { messageRef.current = message; }, [message]);

  // High-quality Browser TTS Fallback
  const speakText = useCallback((text, onComplete) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      if (onComplete) onComplete();
      return;
    }
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.05;
    utterance.volume = 1.0;

    const voice = getAssistantVoice();
    if (voice) utterance.voice = voice;

    setIsSpeaking(true);

    utterance.onend = () => {
      setIsSpeaking(false);
      if (onComplete) onComplete();
    };

    utterance.onerror = (err) => {
      console.warn("Speech Synthesis error:", err);
      setIsSpeaking(false);
      if (onComplete) onComplete();
    };

    window.speechSynthesis.speak(utterance);
  }, []);

  // Safe SpeechRecognition Initializer & Restarter
  const startRecognitionSafely = useCallback(() => {
    if (!recognitionRef.current) return;
    try {
      recognitionRef.current.start();
    } catch (e) {
      // Ignored if already running
    }
  }, []);

  const stopRecognitionSafely = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (!recognitionRef.current) return;
    try {
      recognitionRef.current.stop();
    } catch (e) {
      // Ignored
    }
  }, []);

  // Request Mic Permission & Initialize Recognition Instance
  const initSpeechRecognition = useCallback(async () => {
    if (typeof window === "undefined") return false;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setMicError("Speech Recognition is not supported in this browser. Please use Chrome, Edge, or Safari.");
      return false;
    }

    try {
      // Request mic permission from user gesture
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        await navigator.mediaDevices.getUserMedia({ audio: true });
      }
    } catch (err) {
      console.warn("Microphone access permission denied:", err);
      setMicError("Microphone permission denied. Please allow microphone access in your browser settings.");
      return false;
    }

    setMicError("");
    if (!recognitionRef.current) {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";
      recognition.maxAlternatives = 1;

      recognition.onresult = (event) => {
        if (isSpeakingRef.current || loadingRef.current) return;

        let accumulated = "";
        for (let i = 0; i < event.results.length; i++) {
          accumulated += event.results[i][0].transcript + " ";
        }
        const trimmed = accumulated.trim();
        if (trimmed) {
          setMessage(trimmed);

          // Auto-send after 1.8 seconds of silence
          if (silenceTimerRef.current) {
            clearTimeout(silenceTimerRef.current);
          }
          silenceTimerRef.current = setTimeout(() => {
            if (isListeningRef.current && !loadingRef.current) {
              handleSend(trimmed);
            }
          }, 1800);
        }
      };

      recognition.onend = () => {
        // Auto-restart listening if voice mode is still enabled and assistant is not speaking
        if (isListeningRef.current && !isSpeakingRef.current && !loadingRef.current) {
          setTimeout(() => {
            if (isListeningRef.current && !isSpeakingRef.current) {
              startRecognitionSafely();
            }
          }, 200);
        }
      };

      recognition.onerror = (event) => {
        if (event.error === "no-speech" || event.error === "aborted") {
          return;
        }
        console.warn("Speech Recognition error:", event.error);
        if (event.error === "not-allowed" || event.error === "audio-capture") {
          setMicError("Microphone permission denied or device not found.");
          setIsListening(false);
        }
      };

      recognitionRef.current = recognition;
    }

    return true;
  }, [startRecognitionSafely]);

  // Handle Voice Toggle from user click
  const toggleListening = async () => {
    if (isListening) {
      setIsListening(false);
      stopRecognitionSafely();
    } else {
      const ok = await initSpeechRecognition();
      if (ok) {
        setIsListening(true);
        startRecognitionSafely();
      }
    }
  };

  // Open Chat Modal
  const openModal = useCallback(async () => {
    setOpen(true);
    setMessages([
      { text: GREETING, from: "bot" }
    ]);

    // Speak greeting
    speakText(GREETING, async () => {
      const ok = await initSpeechRecognition();
      if (ok) {
        setIsListening(true);
        startRecognitionSafely();
      }
    });

    setTimeout(() => {
      inputRef.current?.focus();
    }, 300);
  }, [speakText, initSpeechRecognition, startRecognitionSafely]);

  // Close Chat Modal
  const closeModal = useCallback(() => {
    setOpen(false);
    setIsListening(false);
    setIsSpeaking(false);
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    stopRecognitionSafely();
    setMessages([]);
    setMicError("");
  }, [stopRecognitionSafely]);

  // Scroll to latest message
  useEffect(() => {
    msgsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Process and Send User Message to Concierge
  const handleSend = async (customText = null) => {
    const textToSend = (customText !== null ? customText : message).trim();
    if (!textToSend || loading) return;

    // Pause recognition during send & assistant processing
    stopRecognitionSafely();
    setIsListening(false);
    setMessage("");

    setMessages((prev) => [...prev, { text: textToSend, from: "user" }]);
    setLoading(true);

    try {
      const res = await api.post("/ai/chat", { message: textToSend });
      const replyText = res?.reply || "I am here to assist you with Site Studio!";

      setMessages((prev) => [...prev, { text: replyText, from: "bot" }]);

      // Speak reply audio or fallback to Web Speech Synthesis
      if (res?.audio) {
        setIsSpeaking(true);
        try {
          const audioSrc = `data:audio/wav;base64,${res.audio}`;
          const audio = new Audio(audioSrc);
          audio.onended = () => {
            setIsSpeaking(false);
            // Re-enable voice listening after assistant finishes speaking
            setIsListening(true);
            startRecognitionSafely();
          };
          audio.onerror = () => {
            speakText(replyText, () => {
              setIsListening(true);
              startRecognitionSafely();
            });
          };
          await audio.play();
        } catch (e) {
          speakText(replyText, () => {
            setIsListening(true);
            startRecognitionSafely();
          });
        }
      } else {
        speakText(replyText, () => {
          setIsListening(true);
          startRecognitionSafely();
        });
      }
    } catch (err) {
      console.error(err);
      const errReply = "Sorry, I couldn't reach the voice concierge. Please try again.";
      setMessages((prev) => [...prev, { text: errReply, from: "bot" }]);
      speakText(errReply, () => {
        setIsListening(true);
        startRecognitionSafely();
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* Floating Trigger Button */}
      <button
        className={`support-button ${open ? "active" : ""}`}
        onClick={open ? closeModal : openModal}
        aria-label="Voice Support Concierge"
      >
        {open ? (
          <X size={24} className="text-white" />
        ) : (
          <div className="relative flex items-center justify-center">
            <img src="/logo.png" alt="Studio Concierge" className="support-logo-img" />
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
          </div>
        )}
      </button>

      {/* Glassmorphic Support Chat Modal */}
      {open && (
        <div className="support-chat-popup">
          {/* Header */}
          <div className="support-header">
            <div className="support-header-dot" />
            <div className="flex items-center gap-1.5 flex-1">
              <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
              <span className="support-header-title">Voice Concierge</span>
            </div>
            <button className="support-header-close" onClick={closeModal} aria-label="Close Assistant">
              <X size={16} />
            </button>
          </div>

          {/* Messages Container */}
          <div className="support-msgs-area">
            {messages.map((m, i) => (
              <div key={i} className={`support-msg support-msg-${m.from}`}>
                {m.text}
              </div>
            ))}
            {loading && (
              <div className="support-msg support-msg-bot flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                <span>Thinking...</span>
              </div>
            )}
            {micError && (
              <div className="support-msg support-msg-bot border-rose-500/30 text-rose-300 text-xs flex items-center gap-1.5">
                <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                <span>{micError}</span>
              </div>
            )}
            <div ref={msgsEndRef} />
          </div>

          {/* Input & Voice Controls */}
          <div className="support-input-row">
            {isListening ? (
              <div className="support-listening-row">
                {/* Reactive Heartbeat Sphere */}
                <div className="support-heartbeat-container">
                  <span className={`support-heartbeat-dot ${isSpeaking ? "speaking" : "listening"}`} />
                </div>

                <div className="voice-text">
                  <span className="voice-title flex items-center gap-1.5">
                    {isSpeaking ? (
                      <>
                        <Volume2 className="w-4 h-4 text-emerald-400 animate-pulse" />
                        <span>Speaking...</span>
                      </>
                    ) : (
                      <>
                        <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                        <span>Listening...</span>
                      </>
                    )}
                  </span>
                  <span className="voice-transcript">
                    {message.trim() ? message : "Speak naturally, I'm listening..."}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleSend()}
                    disabled={loading}
                    className="support-stop-send-btn"
                  >
                    <span>Send Voice</span>
                    <Send size={13} />
                  </button>

                  <button
                    type="button"
                    onClick={toggleListening}
                    className="p-2 rounded-full bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 transition-colors"
                    title="Stop Listening"
                  >
                    <MicOff size={16} />
                  </button>
                </div>
              </div>
            ) : (
              <>
                <input
                  id="support-message"
                  name="support-message"
                  ref={inputRef}
                  className="support-input"
                  placeholder="Ask Voice Concierge..."
                  value={message}
                  disabled={loading}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={handleKeyDown}
                />

                <button
                  type="button"
                  className={`support-mic ${isListening ? "listening" : ""}`}
                  onClick={toggleListening}
                  disabled={loading}
                  title="Activate Voice Input"
                >
                  <Mic size={17} />
                </button>

                <button
                  type="button"
                  className="support-send"
                  onClick={() => handleSend()}
                  disabled={!message.trim() || loading}
                  title="Send Message"
                >
                  <Send size={15} />
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}