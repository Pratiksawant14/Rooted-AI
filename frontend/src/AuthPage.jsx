
import React, { useState } from 'react';
import { createClient } from '@supabase/supabase-js';

// TODO: These should be in environment variables
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export function AuthPage({ onLogin }) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [mode, setMode] = useState('login'); // 'login' or 'signup'

    const handleAuth = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            if (mode === 'signup') {
                const { data, error } = await supabase.auth.signUp({
                    email,
                    password,
                });
                if (error) throw error;

                if (data.session) {
                    onLogin(data.session);
                } else {
                    alert("Account created! If you haven't disabled 'Confirm Email' in Supabase, please check your inbox.");
                    setMode('login');
                }
            } else {
                const { data, error } = await supabase.auth.signInWithPassword({
                    email,
                    password,
                });
                if (error) throw error;
                onLogin(data.session);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex items-center justify-center h-screen w-full bg-[#0f1110] text-[#ececec]">
            <div className="glass p-8 rounded-2xl w-full max-w-md border border-white/10">
                <h2 className="text-2xl font-bold mb-6 text-center text-[#d8f3dc]">
                    {mode === 'login' ? 'Welcome Back' : 'Join Rooted AI'}
                </h2>

                {error && <div className="mb-4 p-3 bg-red-900/50 text-red-200 rounded">{error}</div>}

                <form onSubmit={handleAuth} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-1">Email</label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full bg-black/30 border border-white/10 rounded-lg p-3 outline-none focus:border-[#2d6a4f]"
                            required
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-1">Password</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full bg-black/30 border border-white/10 rounded-lg p-3 outline-none focus:border-[#2d6a4f]"
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-[#2d6a4f] hover:bg-[#40916c] text-white font-bold py-3 rounded-lg transition-colors disabled:opacity-50"
                    >
                        {loading ? 'Processing...' : (mode === 'login' ? 'Sign In' : 'Sign Up')}
                    </button>
                </form>

                <div className="mt-6 text-center text-sm text-gray-400">
                    {mode === 'login' ? (
                        <p>
                            Don't have an account?{' '}
                            <button onClick={() => setMode('signup')} className="text-[#40916c] hover:underline">
                                Sign Up
                            </button>
                        </p>
                    ) : (
                        <p>
                            Already have an account?{' '}
                            <button onClick={() => setMode('login')} className="text-[#40916c] hover:underline">
                                Sign In
                            </button>
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
}
