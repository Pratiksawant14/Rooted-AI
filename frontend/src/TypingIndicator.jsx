
import React from 'react';

export function TypingIndicator() {
    return (
        <div className="flex w-full justify-start animate-fade-in mb-6">
            <div className="flex-shrink-0 mr-3 mt-1">
                <div className="w-8 h-8 rounded-full bg-[#2d6a4f]/20 flex items-center justify-center border border-[#2d6a4f]/50">
                    {/* Simple pulse instead of icon for typing state */}
                    <div className="w-2 h-2 bg-[#40916c] rounded-full animate-pulse"></div>
                </div>
            </div>

            <div className="px-5 py-4 bg-[#1a1d1c] border border-white/5 rounded-2xl rounded-tl-sm flex items-center gap-1.5 h-12">
                <div className="w-1.5 h-1.5 bg-[#52b788] rounded-full animate-bounce" style={{ animationDelay: '0s' }}></div>
                <div className="w-1.5 h-1.5 bg-[#52b788] rounded-full animate-bounce" style={{ animationDelay: '0.15s' }}></div>
                <div className="w-1.5 h-1.5 bg-[#52b788] rounded-full animate-bounce" style={{ animationDelay: '0.3s' }}></div>
            </div>
        </div>
    );
}
