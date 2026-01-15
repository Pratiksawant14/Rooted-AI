
import React, { useState } from 'react';
import { Leaf } from 'lucide-react';

export function MessageBubble({ message }) {
    const isUser = message.role === 'user';
    const [showExplain, setShowExplain] = useState(false);

    // Parsing memory from the explanation object if present
    const memoryData = message.explanation || {};
    const hasMemory = memoryData.stem?.length > 0 || memoryData.branch?.length > 0;

    return (
        <div className={`flex w-full mb-6 ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in group`}>

            {/* Avatar for AI */}
            {!isUser && (
                <div className="flex-shrink-0 mr-3 mt-1">
                    <div className="w-8 h-8 rounded-full bg-[#2d6a4f]/20 flex items-center justify-center border border-[#2d6a4f]/50">
                        <Leaf size={14} className="text-[#40916c]" />
                    </div>
                </div>
            )}

            <div className={`flex flex-col max-w-[85%] md:max-w-[70%]`}>
                <div
                    className={`px-5 py-3.5 text-[0.95rem] leading-relaxed shadow-sm relative
            ${isUser
                            ? 'bg-[#2d6a4f] text-white rounded-2xl rounded-tr-sm'
                            : 'bg-[#1a1d1c] border border-white/5 text-gray-200 rounded-2xl rounded-tl-sm'
                        }`}
                >
                    {message.text}
                </div>

                {/* Explainability Toggle */}
                {!isUser && hasMemory && (
                    <div className="mt-1 ml-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                        <button
                            onClick={() => setShowExplain(!showExplain)}
                            className="text-xs text-[#52b788] hover:text-[#74c69d] hover:underline flex items-center gap-1"
                        >
                            {showExplain ? "Hide Context" : "Why did I say this?"}
                        </button>
                    </div>
                )}

                {/* Explanation Panel */}
                {showExplain && !isUser && hasMemory && (
                    <div className="mt-2 ml-1 p-3 bg-[#111312] border border-[#2d6a4f]/30 rounded-lg text-xs animate-fade-in">
                        <div className="mb-2 text-[#a0a0a0] font-medium uppercase tracking-wider text-[10px]">Memory Context Used</div>

                        {memoryData.stem?.length > 0 && (
                            <div className="mb-2">
                                <span className="text-[#40916c] font-bold">STEM (Identity):</span>
                                <ul className="list-disc list-inside mt-0.5 text-gray-400 pl-1 space-y-0.5">
                                    {memoryData.stem.map((m, i) => <li key={i}>{m}</li>)}
                                </ul>
                            </div>
                        )}

                        {memoryData.branch?.length > 0 && (
                            <div className="mb-0">
                                <span className="text-[#52b788] font-bold">BRANCH (Pattern):</span>
                                <ul className="list-disc list-inside mt-0.5 text-gray-400 pl-1 space-y-0.5">
                                    {memoryData.branch.map((m, i) => <li key={i}>{m}</li>)}
                                </ul>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
