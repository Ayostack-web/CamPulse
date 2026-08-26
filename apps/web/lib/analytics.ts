/**
 * Best-effort paywall funnel tracking.
 *
 * Fire-and-forget: never blocks the UI, never throws.
 * Events are sent to POST /api/paywall/events which logs to the
 * paywall_events table for conversion funnel analysis.
 */

import { getSupabaseBrowserClient } from '@/lib/supabase-client';

export type PaywallEventType =
  | 'paywall_shown'
  | 'paywall_dismissed'
  | 'plan_clicked'
  | 'checkout_started'
  | 'checkout_completed'
  | 'checkout_failed';

export function trackPaywallEvent(
  eventType: PaywallEventType,
  planKey?: string,
): void {
  try {
    const supabase = getSupabaseBrowserClient();
    supabase.auth.getSession().then(({ data: { session } }) => {
      fetch('/api/paywall/events', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
        },
        body: JSON.stringify({ event_type: eventType, plan_key: planKey }),
      }).catch(() => {});
    }).catch(() => {});
  } catch {
    // best-effort — never throw
  }
}
