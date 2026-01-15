import React, { useState, useEffect, useRef } from 'react';
import { Send, LogOut, Brain } from 'lucide-react';
import { sendMessage } from './api';
import { AuthPage, supabase } from './AuthPage';
import { MessageBubble } from './MessageBubble';
import { TypingIndicator } from './TypingIndicator';
import './index.css';

function App() {
  const [session, setSession] = useState(null);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Auth State Management
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => setSession(session));
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_, session) => setSession(session));
    return () => subscription.unsubscribe();
  }, []);

  // Auto-scroll logic
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMsg = { role: 'user', text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const data = await sendMessage(userMsg.text, session.access_token);

      const aiMsg = {
        role: 'ai',
        text: data.response,
        explanation: data.memory_used // Passing structured memory for the toggle
      };

      setMessages(prev => [...prev, aiMsg]);
    } catch (error) {
      console.error("Error:", error);
      setMessages(prev => [...prev, { role: 'ai', text: "I'm having trouble connecting to my memory patterns right now." }]);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    setMessages([]);
  };

  if (!session) {
    return <AuthPage onLogin={setSession} />;
  }

  return (
    <div className="flex h-screen w-full bg-[#0d0f0e] text-[#ececec] overflow-hidden justify-center font-inter">

      {/* Centered Chat Container */}
      <div className="w-full max-w-3xl flex flex-col h-full bg-[#0d0f0e] shadow-2xl relative">

        {/* Header - Minimal & Floating */}
        <header className="absolute top-0 left-0 right-0 z-20 flex justify-between items-center px-6 py-4 bg-gradient-to-b from-[#0d0f0e] via-[#0d0f0e]/90 to-transparent">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-[#40916c] animate-pulse"></div>
            <span className="text-sm font-medium tracking-widest uppercase text-[#888]">ROOTED AI</span>
          </div>
          <button
            onClick={handleLogout}
            className="p-2 text-[#666] hover:text-white transition-colors text-xs uppercase tracking-wide"
          >
            Log Out
          </button>
        </header>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-8 py-24 space-y-2 scroll-smooth no-scrollbar">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center opacity-40 animate-fade-in select-none">
              <Brain size={64} strokeWidth={1} className="mb-6 text-[#2d6a4f]" />
              <p className="text-xl font-light tracking-wide text-gray-400">Where shall we begin?</p>
            </div>
          )}

          {messages.map((msg, idx) => (
            <MessageBubble key={idx} message={msg} />
          ))}

          {loading && <TypingIndicator />}

          <div ref={messagesEndRef} className="h-4" />
        </div>

        {/* Input Area - Sticky Bottom */}
        <div className="p-6 bg-gradient-to-t from-[#0d0f0e] via-[#0d0f0e] to-transparent z-20">
          <form
            onSubmit={handleSend}
            className="group relative flex items-center gap-3 max-w-2xl mx-auto"
          >
            <div className="relative flex-1">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={loading}
                placeholder="Talk to ROOTED AI..."
                className="w-full bg-[#151716] border border-white/10 rounded-2xl px-6 py-4 pr-12 
                               text-[1rem] text-gray-200 placeholder-gray-600 outline-none 
                               focus:border-[#2d6a4f]/50 focus:bg-[#1a1c1b] transition-all shadow-lg"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="absolute right-3 p-2 bg-[#2d6a4f] text-white rounded-xl 
                         hover:bg-[#40916c] disabled:opacity-0 disabled:scale-90 
                         transition-all duration-300 shadow-lg shadow-green-900/20"
            >
              <Send size={18} />
            </button>
          </form>
          <div className="text-center mt-3">
            <span className="text-[10px] text-[#444] uppercase tracking-widest">
              Long-term Memory Active
            </span>
          </div>
        </div>

      </div>
    </div>
  );
}

export default App;
