"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Send, Mic } from "lucide-react";
import { api } from "../../lib/api";
import "./SupportButton.css";

const GREETING = "Hey! How are you doing? Let me know what help you need.";

function getAssistantVoice() {
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

function speak(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1;
  utterance.pitch = 1.05;
  utterance.volume = 1;
  const voice = getAssistantVoice();
  if (voice) utterance.voice = voice;
  window.speechSynthesis.speak(utterance);
}

export default function SupportButton() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);

  const inputRef = useRef(null);
  const msgsEndRef = useRef(null);
  const recognitionRef = useRef(null);

  // Refs to allow event listeners to access the latest state
  const openRef = useRef(open);
  const isListeningRef = useRef(isListening);
  // Controls whether onend should auto-restart (prevents Chrome 'aborted' error)
  const shouldRestartRef = useRef(true);

  useEffect(() => { openRef.current = open; }, [open]);
  useEffect(() => { isListeningRef.current = isListening; }, [isListening]);

  const toggle = useCallback(() => {
    const next = !openRef.current;
    setOpen(next);
    if (next) {
      setMessages([
        { text: "Hey! How are you doing?", from: "bot" },
        { text: "Let me know what help you need.", from: "bot" },
      ]);
      speak(GREETING);
      setTimeout(() => { inputRef.current?.focus(); }, 300);
      setIsListening(true);
    } else {
      window.speechSynthesis.cancel();
      setIsListening(false);
      setMessages([]);
    }
  }, []);

  const toggleRef = useRef(toggle);
  useEffect(() => { toggleRef.current = toggle; }, [toggle]);

  // Global speech recognition (wake word + voice input)
  useEffect(() => {
    window.speechSynthesis?.getVoices();
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Speech Recognition is not supported in this browser.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-IN"; // or en-US
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      const lower = transcript.toLowerCase();
      if (!openRef.current) {
        if (
          lower.includes("hey sit") ||
          lower.includes("hay sit") ||
          lower.includes("hey site") ||
          lower.includes("hey siri") ||
          lower.includes("hey ai")
        ) {
          shouldRestartRef.current = false;
          recognition.stop();
          toggleRef.current();
        }
      } else {
        if (isListeningRef.current) {
          // Replace message with the latest final transcript chunk
          setMessage(transcript.trim());
        }
      }
    };

    // Only auto-restart when shouldRestartRef allows it,
    // and wait 150ms so Chrome doesn't abort the new session.
    recognition.onend = () => {
      console.log("Recognition ended");
    };
    recognition.onerror = (event) => {
      console.log("Speech Error:", event.error);

      switch (event.error) {
        case "no-speech":
          console.log("No speech detected");
          break;

        case "audio-capture":
          console.log("Microphone not found");
          break;

        case "not-allowed":
          console.log("Permission denied");
          break;

        case "network":
          console.log("Network error");
          break;

        default:
          console.log(event.error);
      }

      setIsListening(false);
    };

    recognitionRef.current = recognition;
    try { recognition.start(); } catch (e) { }
  }, []);

  useEffect(() => {
    msgsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const close = () => {
    setOpen(false);
    setMessages([]);
    window.speechSynthesis.cancel();
    setIsListening(false);
  };

  const toggleListening = () => {
    if (!recognitionRef.current) {
      alert("Speech Recognition not supported.");
      return;
    }

    if (isListeningRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (err) {
        console.log(err);
      }
    }
  };

  async function askAI(userMessage) {
    try {
      const response = await api.post("/ai/chat", { message: userMessage });
      return response;
    } catch (err) {
      throw new Error("Failed to contact AI");
    }
  }

  const handleSend = async () => {
    const text = message.trim();
    if (!text || loading) return;

    if (isListening && recognitionRef.current) {
      shouldRestartRef.current = false;
      recognitionRef.current.stop();
      setIsListening(false);
    }

    setMessages((prev) => [...prev, { text, from: "user" }]);
    setMessage("");
    setLoading(true);
    setMessages((prev) => [...prev, { text: "Thinking...", from: "bot", typing: true }]);

    try {
      const result = await askAI(text);
      setMessages((prev) => {
        const list = [...prev];
        list.pop();
        list.push({ text: result.reply, from: "bot" });
        return list;
      });

      if (result.audio) {
        const audioSrc = `data:audio/wav;base64,${result.audio}`;
        const audio = new Audio(audioSrc);
        audio.play().catch((e) => {
          console.warn("TTS audio autoplay failed, falling back to speech synthesis:", e);
          speak(result.reply);
        });
      } else {
        speak(result.reply);
      }
    } catch (err) {
      setMessages((prev) => {
        const list = [...prev];
        list.pop();
        list.push({ text: "Sorry, I couldn't reach the AI server.", from: "bot" });
        return list;
      });
    }

    setLoading(false);
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      <button className="support-button" onClick={toggle} aria-label="AI Support">
        <img src="/logo.png" alt="AI" className="support-logo-img" />
      </button>

      {open && (
        <div className="support-chat-popup">
          {/* Messages */}
          <div className="support-msgs-area">
            {messages.map((m, i) => (
              <div key={i} className={`support-msg support-msg-${m.from}`}>
                {m.text}
              </div>
            ))}
            <div ref={msgsEndRef} />
          </div>

          {/* Input / Voice Row */}
          <div className="support-input-row">
            {isListening ? (
              <div className="support-listening-row">
                {/* Audio-reactive heartbeat ball */}
                <div className="support-heartbeat-container">
                  <span
                    className="support-heartbeat-dot"
                  />
                </div>

                {/* Labels */}
                <div className="voice-text">
                  <span className="voice-title">Listening…</span>
                  <span className="voice-transcript">
                    {message.trim() ? message : "Speak naturally, I'm listening"}
                  </span>
                </div>

                {/* Stop & Send */}
                <button
                  type="button"
                  onClick={() => {

                    if (recognitionRef.current) {
                      recognitionRef.current.stop();
                    }

                    setIsListening(false);

                    setTimeout(() => {
                      handleSend();
                    }, 200);

                  }}
                  className="support-stop-send-btn"
                >
                  Stop &amp; Send
                </button>
              </div>
            ) : (
              <>
                <input
                  id="support-message"
                  name="support-message"
                  ref={inputRef}
                  className="support-input"
                  placeholder="Ask AI Site Studio…"
                  value={message}
                  disabled={loading}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={handleKey}
                />

                <button
                  type="button"
                  className={`support-mic${isListening ? " listening" : ""}`}
                  onClick={toggleListening}
                  disabled={loading}
                  aria-label="Toggle Voice Input"
                >
                  <Mic size={17} />
                </button>

                <button
                  type="button"
                  className="support-send"
                  onClick={handleSend}
                  disabled={loading}
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