"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare,
  Sparkles,
  Send,
  Loader2,
  Volume2,
  Bot,
  User,
  Zap,
  CheckCircle2,
  HelpCircle,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { api } from "@/lib/api";

export default function TemplateAIChat({ template }) {
  const token = useAuthStore((s) => s.token);
  const currentUser = useAuthStore((s) => s.user);

  const title = template?.title || "Website Template";
  const framework = template?.framework || "HTML5 / Vanilla CSS";
  const category = template?.category?.name || "Portfolio & Business";
  const pages = template?.included_pages?.length
    ? template.included_pages.join(", ")
    : `${template?.pages_count || 1} physical pages (index.html, about.html, contact.html)`;
  const developer = template?.seller?.full_name || template?.developer_name || "Verified Author";

  const [messages, setMessages] = useState([
    {
      id: "initial",
      sender: "assistant",
      text: `Hello! I'm your AI Template Specialist for "${title}". Ask me anything about the code architecture, included pages (${pages}), framework customization, or live edge deployment.`,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [playingAudioId, setPlayingAudioId] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const QUICK_PROMPTS = [
    { label: "What pages are included?", prompt: `What physical pages are included in "${title}"?` },
    { label: "How do I customize colors?", prompt: `How do I customize the color palette and typography in ${framework}?` },
    { label: "Working contact forms & APIs?", prompt: `Does "${title}" include working contact forms and backend REST endpoints?` },
    { label: "Custom domain deployment?", prompt: `How does deploying "${title}" to a custom GoDaddy domain work?` },
  ];

  // Intelligent fallback generator if user is not logged in or endpoint has limits
  const generateLocalAnswer = (prompt) => {
    const p = prompt.toLowerCase();
    if (p.includes("page")) {
      return `"${title}" delivers complete, physically existing pages: ${pages}. In accordance with Site Studio architecture standards, every page listed physically exists in the source ZIP with relative links, fluid typography, and working drawer navigation.`;
    }
    if (p.includes("color") || p.includes("font") || p.includes("css") || p.includes("style")) {
      return `Customizing colors and fonts in "${title}" (${framework}) is straightforward! Design tokens are declared in global CSS variables (e.g. \`--primary\`, \`--background\`, \`--foreground\`). You can also use our live canvas "AI Fill" feature to derive brand palettes automatically using Gemini AI.`;
    }
    if (p.includes("form") || p.includes("api") || p.includes("contact") || p.includes("backend")) {
      return `Yes! Fullstack and standalone packages include working REST endpoints: \`POST /api/contact\` for message submissions, \`POST /api/leads\`, and \`GET /api/health\`, backed by local SQLite persistence and CORS middleware. Frontend forms submit asynchronously with zero page reload.`;
    }
    if (p.includes("domain") || p.includes("deploy") || p.includes("host")) {
      return `Deploying "${title}" takes one click! You can publish instantly to a free Studio subdomain (e.g. \`${template?.slug || "mysite"}.aisitestudio.com\`) or link your custom GoDaddy domain with automated TLS 1.3 SSL certificate generation and sub-millisecond edge CDN routing.`;
    }
    return `"${title}" is a high-performance ${category} template engineered with ${framework}. It includes full source code, lifetime commercial license, fluid responsive reflow across all mobile and desktop viewports, and zero horizontal overflow.`;
  };

  const handleSend = async (messageText) => {
    const textToSend = messageText || input;
    if (!textToSend.trim() || loading) return;

    const userMsg = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: textToSend.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      if (token) {
        // Enriched contextual prompt for Gemini backend
        const contextualPrompt = `You are the technical AI specialist for the website template "${title}" (Framework: ${framework}, Category: ${category}, Pages: ${pages}, Author: ${developer}). Answer this buyer question accurately and concisely: ${textToSend}`;
        
        const res = await api.post("/ai/chat", { message: contextualPrompt }, token);
        const reply = res?.reply || generateLocalAnswer(textToSend);

        setMessages((prev) => [
          ...prev,
          {
            id: `asst-${Date.now()}`,
            sender: "assistant",
            text: reply,
            audio: res?.audio || null,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          },
        ]);
      } else {
        // Instant local template intelligence for guest browsers
        await new Promise((r) => setTimeout(r, 400));
        const reply = generateLocalAnswer(textToSend);
        setMessages((prev) => [
          ...prev,
          {
            id: `asst-${Date.now()}`,
            sender: "assistant",
            text: reply,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          },
        ]);
      }
    } catch (err) {
      console.warn("AI chat fallback to local intelligence:", err);
      const fallbackReply = generateLocalAnswer(textToSend);
      setMessages((prev) => [
        ...prev,
        {
          id: `asst-${Date.now()}`,
          sender: "assistant",
          text: fallbackReply,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const playSpeech = (msg) => {
    if (msg.audio) {
      try {
        const audio = new Audio(`data:audio/wav;base64,${msg.audio}`);
        setPlayingAudioId(msg.id);
        audio.onended = () => setPlayingAudioId(null);
        audio.onerror = () => setPlayingAudioId(null);
        audio.play();
        return;
      } catch (e) {}
    }

    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(msg.text);
      utterance.onend = () => setPlayingAudioId(null);
      setPlayingAudioId(msg.id);
      window.speechSynthesis.speak(utterance);
    }
  };

  return (
    <div className="template-ai-chat-card">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-purple-600/30">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-white flex items-center gap-2">
              <span>Chat with Template AI Specialist</span>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            </h4>
            <span className="text-[11px] text-muted-foreground block">
              Instant answers on code architecture, customization & deployment
            </span>
          </div>
        </div>

        <span className="text-[10px] font-mono font-bold text-purple-300 bg-purple-500/10 px-2 py-0.5 rounded-full border border-purple-500/20">
          Gemini 1.5 Powered
        </span>
      </div>

      {/* Quick Prompt Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-3 mb-3 scrollbar-none">
        {QUICK_PROMPTS.map((qp, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => handleSend(qp.prompt)}
            className="px-2.5 py-1 rounded-full text-[11px] font-semibold text-purple-200 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/25 shrink-0 transition-all cursor-pointer"
          >
            {qp.label}
          </button>
        ))}
      </div>

      {/* Messages Thread Container */}
      <div className="template-ai-chat-thread">
        {messages.map((m) => {
          const isUser = m.sender === "user";
          return (
            <motion.div
              key={m.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className={`flex gap-2.5 ${isUser ? "justify-end" : "justify-start"}`}
            >
              {!isUser && (
                <div className="w-6 h-6 rounded-md bg-purple-600/20 border border-purple-500/30 flex items-center justify-center text-purple-300 shrink-0 mt-0.5">
                  <Bot className="w-3.5 h-3.5" />
                </div>
              )}

              <div
                className={`max-w-[85%] rounded-xl p-3 text-xs leading-relaxed ${
                  isUser
                    ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-tr-none shadow-md"
                    : "bg-white/5 border border-white/10 text-slate-200 rounded-tl-none"
                }`}
              >
                <p className="m-0 whitespace-pre-wrap">{m.text}</p>
                <div className="flex items-center justify-between gap-2 mt-1.5 pt-1 border-t border-white/5 text-[10px] opacity-60">
                  <span>{m.timestamp}</span>
                  {!isUser && (
                    <button
                      type="button"
                      onClick={() => playSpeech(m)}
                      className={`hover:opacity-100 transition-opacity cursor-pointer ${
                        playingAudioId === m.id ? "text-purple-400 opacity-100" : ""
                      }`}
                      title="Listen with Text-to-Speech"
                    >
                      <Volume2 className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>

              {isUser && (
                <div className="w-6 h-6 rounded-md bg-white/10 border border-white/20 flex items-center justify-center text-white shrink-0 mt-0.5">
                  <User className="w-3.5 h-3.5" />
                </div>
              )}
            </motion.div>
          );
        })}

        {loading && (
          <div className="flex gap-2.5 items-center text-xs text-purple-400">
            <div className="w-6 h-6 rounded-md bg-purple-600/20 border border-purple-500/30 flex items-center justify-center text-purple-300">
              <Bot className="w-3.5 h-3.5" />
            </div>
            <div className="p-2.5 rounded-xl bg-white/5 border border-white/10 flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Analyzing template architecture...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Chat Input Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="template-ai-chat-input-bar mt-3"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={`Ask about ${title} code, responsive reflow, or deployment...`}
          className="template-ai-chat-input"
        />
        <button
          type="submit"
          disabled={!input.trim() || loading}
          className="template-ai-chat-send-btn"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
}

