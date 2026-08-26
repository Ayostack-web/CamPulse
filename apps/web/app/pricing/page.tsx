'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/context/auth-context';
import { formatNaira, initializePaystackPayment } from '@/lib/payments';
import { getSupabaseBrowserClient } from '@/lib/supabase-client';
import { usePlans, type Plan } from '@/queries/use-ai-tokens';

function durationLabel(days: number | null): string {
  if (!days) return 'No expiry';
  if (days <= 2) return `${days} days`;
  if (days % 30 === 0) return `${days / 30} months`;
  return `${days} days`;
}

function featureList(plan: Plan): string[] {
  const features = [`${plan.query_quota?.toLocaleString() ?? '5 AI queries/day'}`];
  if (plan.storage_mb > 0) {
    features.push(`${plan.storage_mb}MB extra storage`);
  }
  if (plan.duration_days) {
    features.push(durationLabel(plan.duration_days));
  }
  return features;
}

export default function PricingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, promptLogin } = useAuth();
  const { data: plans, isLoading: plansLoading } = usePlans();
  const [loadingKey, setLoadingKey] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [purchasedPlan, setPurchasedPlan] = useState<string | null>(null);

  useEffect(() => {
    const ref = searchParams.get('trxref');
    if (!ref || !user) return;

    const verify = async () => {
      const supabase = getSupabaseBrowserClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch(`/api/payments/verify?reference=${encodeURIComponent(ref)}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${session.access_token}` },
      });

      if (res.ok) {
        const body = await res.json().catch(() => ({}));
        setPurchasedPlan(body.plan || null);
        setSuccess(true);
        setTimeout(() => router.push('/'), 3000);
      }
    };

    verify();
  }, [searchParams, user, router]);

  const handleSubscribe = async (plan: Plan) => {
    if (!user) {
      promptLogin('buy a plan');
      return;
    }

    const supabase = getSupabaseBrowserClient();
    const { data: { session } } = await supabase.auth.getSession();
    const email = session?.user.email || '';
    if (!email) {
      alert('No email found on your account. Please update your profile.');
      return;
    }

    setLoadingKey(plan.key);
    try {
      const { authorization_url } = await initializePaystackPayment(email, plan.key);
      window.location.assign(authorization_url);
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Payment initialization failed. Please try again.');
      setLoadingKey(null);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="max-w-sm w-full bg-white rounded-2xl shadow-lg border border-gray-100 p-8 text-center">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-50 to-green-100 flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">🎉</span>
          </div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">Payment successful!</h1>
          <p className="text-sm text-gray-500 mb-4">Your AI queries are ready. Redirecting to dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f6f7fb]">
      <header className="border-b border-gray-100 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-3">
          <button onClick={() => router.back()} className="p-2 -ml-2 rounded-xl hover:bg-gray-100 active:bg-gray-200/60 transition-colors" aria-label="Go back">
            <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-sm font-bold text-gray-900">Vylix</span>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <h1 className="text-3xl font-bold text-gray-900 mb-3">Pick your pass</h1>
          <p className="text-gray-500 max-w-md mx-auto">
            Buy AI queries by the night, semester or session. No subscriptions, no card on file — pay once and study.
          </p>
        </div>

        {plansLoading || !plans ? (
          <p className="text-center text-gray-400 text-sm">Loading plans...</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-4">
            {plans.map((plan) => (
              <div
                key={plan.key}
                className={`relative rounded-2xl bg-white p-6 shadow-sm border ${
                  plan.featured ? 'border-blue-300 ring-1 ring-blue-200' : 'border-gray-100'
                }`}
              >
                {plan.featured && (
                  <span className="absolute -top-2.5 left-6 px-2 py-0.5 rounded-full bg-gradient-to-r from-blue-600 to-sky-500 text-white text-[10px] font-bold">
                    MOST POPULAR
                  </span>
                )}

                <h2 className="text-sm font-bold text-gray-900">{plan.name}</h2>
                <p className="text-[11px] text-gray-500 mt-1 leading-snug min-h-[30px]">{plan.tagline}</p>

                <p className="text-2xl font-black text-gray-900 mt-3">
                  {plan.paid ? formatNaira(plan.price_ngn) : 'Free'}
                </p>
                <p className="text-[11px] text-gray-400">
                  {plan.paid ? `one-time · ${durationLabel(plan.duration_days)}` : 'forever · just sign in'}
                </p>

                <div className="space-y-1.5 mt-4">
                  {featureList(plan).map((f) => (
                    <p key={f} className="flex items-center gap-2 text-xs text-gray-700">
                      <span className="w-4 h-4 rounded-full bg-emerald-50 flex items-center justify-center shrink-0">
                        <svg className="w-2.5 h-2.5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      </span>
                      {f}
                    </p>
                  ))}
                </div>

                <button
                  onClick={() => (plan.paid ? handleSubscribe(plan) : router.push('/'))}
                  disabled={loadingKey === plan.key}
                  className={`mt-6 w-full py-2.5 rounded-xl text-sm font-bold transition-all disabled:opacity-50 ${
                    plan.paid
                      ? plan.featured
                        ? 'bg-gradient-to-r from-blue-600 to-sky-500 text-white hover:shadow-lg'
                        : 'bg-gray-900 text-white hover:bg-gray-700'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {loadingKey === plan.key ? 'Redirecting to Paystack...' : plan.paid ? `Pay ${formatNaira(plan.price_ngn)}` : 'Start Free'}
                </button>
              </div>
            ))}
          </div>
        )}

        <p className="text-xs text-gray-400 text-center mt-8">
          Secured by Paystack · Free tier includes 5 AI queries/day
        </p>
      </div>
    </div>
  );
}
