'use client';

import React, { useState } from 'react';
import { useAuth } from '@/context/auth-context';

export function LoginModal() {
  const { showLoginModal, setShowLoginModal, login, signInWithGoogle, isLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!email || !password) {
      setError('Please fill in all fields');
      return;
    }

    try {
      const result = await login(email, password, isSignUp);
      setSuccess(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    }
  };

  const handleGoogleSignIn = async () => {
    setError('');
    setGoogleLoading(true);
    try {
      await signInWithGoogle();
      setGoogleLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Google sign-in failed');
      setGoogleLoading(false);
    }
  };

  if (!showLoginModal) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl border border-green-100">
        {/* Header */}
        <div className="border-b border-blue-100 bg-gradient-to-r from-blue-50 to-sky-50/35 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-[clamp(1.5rem,3vw,2.2rem)] leading-[1.2] tracking-[-0.03em] font-black bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 bg-clip-text text-transparent mb-3">
                {isSignUp ? 'Join Vylix Academic Hub' : 'Welcome Back'}
              </h2>
              <p className="cp-body mt-1 text-sm">
                {isSignUp
                  ? 'Create account to contribute'
                  : 'Sign in to upload & participate'}
              </p>
            </div>
            <button
              onClick={() => setShowLoginModal(false)}
              className="text-2xl text-gray-500 hover:text-gray-700 transition-colors"
              title="Close modal"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4 p-6">
          {/* Error Message */}
          {error && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-800 border border-red-200 font-medium">
              ⚠️ {error}
            </div>
          )}

          {success && (
            <div className="rounded-lg bg-gradient-to-br from-blue-50 to-sky-50/35 p-3 text-sm text-green-800 border border-blue-100 font-medium">
              {success}
            </div>
          )}

          {/* Email Input */}
          <div>
            <label className="cp-label block mb-2 text-gray-900">
              Email Address
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-lg border border-blue-100 bg-blue-50 px-4 py-2.5 text-gray-900 placeholder-gray-500 focus:border-green-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
              disabled={isLoading}
            />
          </div>

          {/* Password Input */}
          <div>
            <label className="cp-label block mb-2 text-gray-900">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-lg border border-blue-100 bg-blue-50 px-4 py-2.5 text-gray-900 placeholder-gray-500 focus:border-green-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
              disabled={isLoading}
            />
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-lg bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 py-2.5 font-bold text-white transition-all hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading
              ? 'Processing...'
              : isSignUp
                ? 'Create Account'
                : 'Sign In'}
          </button>

          {/* Divider */}
          <div className="relative my-2">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-blue-100" />
            </div>
            <div className="relative flex justify-center">
              <span className="bg-white px-3 text-xs text-gray-500">or</span>
            </div>
          </div>

          {/* Google Sign In */}
          <button
            type="button"
            onClick={handleGoogleSignIn}
            disabled={googleLoading}
            className="w-full flex items-center justify-center gap-3 rounded-lg border border-gray-200 bg-white py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-all disabled:opacity-50"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
            </svg>
            {googleLoading ? (
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              `Sign ${isSignUp ? 'up' : 'in'} with Google`
            )}
          </button>

          {/* Toggle Sign Up / Sign In */}
          <div className="border-t border-blue-100 pt-4 text-center">
            <p className="cp-body text-sm">
              {isSignUp
                ? 'Already have an account? '
                : "Don't have an account? "}
              <button
                type="button"
                onClick={() => {
                  setIsSignUp(!isSignUp);
                  setError('');
                  setSuccess('');
                }}
                className="font-semibold text-transparent bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 bg-clip-text hover:opacity-80 transition-opacity"
              >
                {isSignUp ? 'Sign In' : 'Sign Up'}
              </button>
            </p>
          </div>
        </form>

        {/* Info Box */}
        <div className="border-t border-blue-100 bg-gradient-to-r from-blue-50 to-sky-50/35 px-6 py-4">
          <p className="text-xs text-gray-700">
            <strong>Registration Required:</strong> You can browse materials and posts
            without signing in, but you&apos;ll need to register to upload, comment, or participate.
          </p>
        </div>
      </div>
    </div>
  );
}
