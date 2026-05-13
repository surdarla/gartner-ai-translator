import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, HelpCircle, Send, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import clsx from 'clsx';
import { getApiUrl } from '../api';

/** Lightweight markdown-to-JSX renderer for chatbot messages */
function renderMarkdown(text: string): React.ReactNode {
  // Split into lines for block-level processing
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let listBuffer: string[] = [];

  const flushList = () => {
    if (listBuffer.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} className="list-disc pl-4 space-y-1 my-1">
          {listBuffer.map((item, i) => (
            <li key={i}>{inlineFormat(item)}</li>
          ))}
        </ul>
      );
      listBuffer = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    // List items: - or *
    const listMatch = line.match(/^\s*[-*]\s+(.*)/);
    if (listMatch) {
      listBuffer.push(listMatch[1]);
      continue;
    }

    flushList();

    // Empty line → spacing
    if (line.trim() === '') {
      elements.push(<div key={`br-${i}`} className="h-1" />);
      continue;
    }

    // Regular paragraph
    elements.push(
      <p key={`p-${i}`} className="my-0.5 leading-relaxed">{inlineFormat(line)}</p>
    );
  }
  flushList();
  return <>{elements}</>;
}

/** Inline formatting: **bold**, *italic*, `code` */
function inlineFormat(text: string): React.ReactNode {
  // Process bold, italic, code with regex splits
  const parts: React.ReactNode[] = [];
  // Combined regex for **bold**, *italic*, `code`
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    // Push text before match
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    if (match[2]) {
      // **bold**
      parts.push(<strong key={match.index} className="font-extrabold">{match[2]}</strong>);
    } else if (match[3]) {
      // *italic*
      parts.push(<em key={match.index}>{match[3]}</em>);
    } else if (match[4]) {
      // `code`
      parts.push(
        <code key={match.index} className="bg-slate-100 text-indigo-600 px-1 py-0.5 rounded text-xs">
          {match[4]}
        </code>
      );
    }

    lastIndex = match.index + match[0].length;
  }

  // Remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? <>{parts}</> : text;
}

export const HelpChatbot: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const scrollRef = useRef<HTMLDivElement>(null);
  
  const [history, setHistory] = useState<{type: 'bot' | 'user', text: string}[]>([
    { type: 'bot', text: t('chatbot_hello') }
  ]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history, isTyping]);

  const handleSend = async (msg: string) => {
    if (!msg.trim()) return;
    setHistory(prev => [...prev, { type: 'user', text: msg }]);
    setInput('');
    setIsTyping(true);

    try {
      const res = await axios.post(getApiUrl('/chat'), 
        { message: msg },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setHistory(prev => [...prev, { type: 'bot', text: res.data.response }]);
    } catch (err) {
      setHistory(prev => [...prev, { type: 'bot', text: "죄송합니다. 서버와 통신 중 오류가 발생했습니다." }]);
    } finally {
      setIsTyping(false);
    }
  };

  const suggestions = {
    ko: ["번역 방법 알려줘", "용어집은 어떻게 써?", "레이아웃이 깨져요"],
    en: ["How to translate?", "How to use glossary?", "Layout is broken"],
    ja: ["翻訳方法を教えて", "用語集の使い方は？", "レイアウトが崩れます"]
  };
  const currentSuggestions = suggestions[i18n.language as keyof typeof suggestions] || suggestions['en'];

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {isOpen ? (
        <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-88 md:w-104 flex flex-col overflow-hidden animate-fade-in"
             style={{ height: 'min(75vh, 44rem)' }}>
          {/* Header */}
          <div className="bg-linear-to-r from-blue-600 to-indigo-600 text-white px-5 py-4 flex justify-between items-center shrink-0">
            <div className="flex items-center gap-3 font-black text-sm">
              <MessageCircle className="w-5 h-5" />
              {t('chatbot_title')}
            </div>
            <button onClick={() => setIsOpen(false)} className="text-white/80 hover:text-white transition-colors p-1 hover:bg-white/10 rounded-lg">
              <X className="w-5 h-5" />
            </button>
          </div>
          
          {/* Chat History */}
          <div ref={scrollRef} className="flex-1 min-h-0 p-4 overflow-y-auto bg-slate-50 space-y-3 flex flex-col custom-scrollbar">
            {history.map((msg, i) => (
              <div key={i} className={clsx(
                "max-w-[88%] rounded-2xl px-4 py-3 text-[13px] shadow-sm transition-all animate-slide-in",
                msg.type === 'bot' 
                  ? "bg-white border border-slate-200 text-slate-700 self-start rounded-tl-sm leading-relaxed" 
                  : "bg-blue-600 text-white self-end rounded-tr-sm font-semibold"
              )}>
                {msg.type === 'bot' ? renderMarkdown(msg.text) : msg.text}
              </div>
            ))}
            {isTyping && (
              <div className="bg-white border border-slate-200 text-slate-400 self-start rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm animate-pulse flex items-center gap-2 text-[13px]">
                <Loader2 className="w-4 h-4 animate-spin" />
                AI가 생각 중...
              </div>
            )}
          </div> 
          
          {/* Footer Input */}
          <div className="p-3 bg-white border-t border-slate-100 space-y-2 shrink-0">
            <div className="flex flex-wrap gap-1.5">
              {currentSuggestions.map((s, idx) => (
                <button 
                  key={idx}
                  onClick={() => handleSend(s)}
                  className="text-[10px] font-bold bg-slate-50 hover:bg-blue-50 text-slate-500 hover:text-blue-600 border border-slate-100 hover:border-blue-200 rounded-full px-2.5 py-1 transition-all"
                >
                  {s}
                </button>
              ))}
            </div>
            <form 
              onSubmit={(e) => { e.preventDefault(); handleSend(input); }}
              className="relative"
            >
              <input 
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="무엇이든 물어보세요..."
                className="w-full bg-slate-100 border-none rounded-xl p-3 pr-11 text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
              />
              <button 
                type="submit"
                disabled={!input.trim() || isTyping}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-30"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      ) : (
        <button 
          onClick={() => setIsOpen(true)}
          className="w-14 h-14 bg-linear-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white rounded-full shadow-2xl shadow-blue-600/30 flex items-center justify-center transition-all hover:scale-110 active:scale-95 group relative"
        >
          <HelpCircle className="w-8 h-8" />
          <span className="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-[9px] font-black px-1.5 py-0.5 rounded-full border-2 border-white animate-bounce">AI</span>
        </button>
      )}
    </div>
  );
};
