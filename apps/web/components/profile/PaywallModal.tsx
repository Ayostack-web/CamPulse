'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/context/auth-context';
import { formatNaira, initializePaystackPayment } from '@/lib/payments';
import { getSupabaseBrowserClient } from '@/lib/supabase-client';
import { useAiTokens, usePlans, type Plan } from '@/queries/use-ai-tokens';

const PAYWALL_ORDER = ['night', 'weekly', 'semester', 'session'];

function durationLabel(days: number | null): string {
  if (!days) return 'Lifetime access';
  if (days <= 2) return `${days} days`;
  if (days % 30 === 0) return `${days / 30} months`;
  return `${days} days`;
}

function featureList(plan: Plan): string[] {
  const features = [`${plan.query_quota?.toLocaleString() ?? 'Unlimited'} AI queries`];
  if (plan.storage_mb > 0) {
    features.push(`${plan.storage_mb}MB extra vault storage`);
  }
  features.push(durationLabel(plan.duration_days));
  return features;
}

interface PaywallModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function PaywallModal({ isOpen, onClose }: PaywallModalProps) {
  const { user, promptLogin } = useAuth();
  const { data: tokens, refetch: refetchTokens } = useAiTokens();
  const { data: plans } = usePlans();
  const [payingFor, setPayingFor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      setError(null);
      refetchTokens();
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = '' };
  }, [isOpen, refetchTokens]);

  if (!isOpen) return null;

  const exhaustedPass = Boolean(tokens?.has_paid_pass && (tokens.remaining ?? 0) <= 0);
  const paidCards = (plans ?? []).filter((p) => p.paid);
  paidCards.sort((a, b) => PAYWALL_ORDER.indexOf(a.key) - PAYWALL_ORDER.indexOf(b.key));
  const topUp = (plans ?? []).find((p) => p.key === 'topup');
  const topUpMini = (plans ?? []).find((p) => p.key === 'topup_mini');

  const handlePay = async (plan: Plan) => {
    if (!user) {
      promptLogin('get AI queries');
      return;
    }

    const supabase = getSupabaseBrowserClient();
    const { data: { session } } = await supabase.auth.getSession();
    const email = session?.user.email || '';
    if (!email) {
      setError('No email found on your account. Please update your profile.');
      return;
    }

    setPayingFor(plan.key);
    setError(null);
    try {
      const { authorization_url } = await initializePaystackPayment(email, plan.key);
      window.location.assign(authorization_url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Payment initialization failed. Please try again.');
      setPayingFor(null);
    }
  };

  const title = exhaustedPass ? 'AI queries used up' : 'Daily AI limit reached';
  const subtitle = exhaustedPass
    ? 'Your pass queries are all used. Top up for more or grab a bigger pass.'
    : 'Pick a pass to unlock more AI queries for the semester.';

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md max-h-[90vh] overflow-y-auto rounded-2xl bg-white shadow-2xl p-6 animate-fade-in">
        <div className="text-center mb-5">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-amber-50 to-orange-100 flex items-center justify-center mx-auto mb-3">
            <span className="text-2xl">⚡</span>
          </div>
          <h2 className="text-lg font-bold text-gray-900">{title}</h2>
          <p className="text-xs text-gray-500 mt-1 leading-relaxed">{subtitle}</p>
        </div>

        {(topUp || topUpMini) && (
          <div className="flex gap-2 mb-4">
            {topUpMini && (
              <button
                onClick={() => handlePay(topUpMini)}
                disabled={payingFor === topUpMini.key}
                className="flex-1 flex items-center justify-between rounded-xl border-2 border-amber-200 bg-amber-50 p-3 hover:bg-amber-100 transition-all disabled:opacity-50 text-left"
              >
                <div>
                  <p className="text-xs font-bold text-amber-800">Mini {topUpMini.query_quota} queries</p>
                  <p className="text-[9px] text-amber-600 mt-0.5">Stacks · {durationLabel(topUpMini.duration_days)}</p>
                </div>
                <span className="text-xs font-black text-amber-800">{formatNaira(topUpMini.price_ngn)}</span>
              </button>
            )}
            {topUp && (
              <button
                onClick={() => handlePay(topUp)}
                disabled={payingFor === topUp.key}
                className="flex-1 flex items-center justify-between rounded-xl border-2 border-amber-300 bg-amber-50 p-3 hover:bg-amber-100 transition-all disabled:opacity-50 text-left"
              >
                <div>
                  <p className="text-xs font-bold text-amber-800">Top-Up {topUp.query_quota?.toLocaleString()} queries</p>
                  <p className="text-[9px] text-amber-600 mt-0.5">Stacks · {durationLabel(topUp.duration_days)}</p>
                </div>
                <span className="text-sm font-black text-amber-800">{formatNaira(topUp.price_ngn)}</span>
              </button>
            )}
          </div>
        )}

        <div className="space-y-3">
          {paidCards.map((plan) => (
            <div
              key={plan.key}
              className={`relative rounded-2xl border p-4 ${
                plan.featured ? 'border-blue-300 bg-blue-50/50 ring-1 ring-blue-200' : 'border-gray-200'
              }`}
            >
              {plan.featured && (
                <span className="absolute -top-2.5 left-4 px-2 py-0.5 rounded-full bg-gradient-to-r from-blue-600 to-sky-500 text-white text-[10px] font-bold">
                  MOST POPULAR
                </span>
              )}
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold text-gray-900">{plan.name}</p>
                  <p className="text-[10px] text-gray-500 mt-0.5 leading-snug">{plan.tagline}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-lg font-black text-gray-900">{formatNaira(plan.price_ngn)}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-1.5 mt-2.5">
                {featureList(plan).map((f) => (
                  <span key={f} className="text-[10px] font-semibold text-blue-700 bg-white/80 border border-blue-100 px-2 py-0.5 rounded-md">
                    {f}
                  </span>
                ))}
              </div>

              <button
                onClick={() => handlePay(plan)}
                disabled={payingFor === plan.key}
                className={`mt-3 w-full py-2.5 rounded-xl text-sm font-bold transition-all disabled:opacity-50 ${
                  plan.featured
                    ? 'bg-gradient-to-r from-blue-600 to-sky-500 text-white hover:shadow-lg'
                    : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                }`}
              >
                {payingFor === plan.key ? 'Redirecting to Paystack...' : `Get ${plan.name}`}
              </button>
            </div>
          ))}
        </div>

        {error && (
          <p className="text-[11px] text-red-500 mt-3 text-center">{error}</p>
        )}

        <button
          onClick={onClose}
          className="w-full mt-4 py-2.5 rounded-xl bg-gray-100 text-gray-600 font-medium text-xs hover:bg-gray-200 transition-all"
        >
          Maybe Later
        </button>

        <p className="text-[10px] text-gray-400 text-center mt-3">
          Secured by Paystack · Free tier: {tokens?.is_premium ? '—' : '5 AI queries/day'}
        </p>
      </div>
    </div>
  );
}
