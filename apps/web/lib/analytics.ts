/**
 * Best-effort paywall funnel tracking.
 *
 * Fire-and-forget: never blocks the UI, never throws.
 * Events are sent to POST /api/paywall/events which logs to the
 * paywall_events table for conversion funnel analysis.
 */

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
    fetch('/api/paywall/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_type: eventType, plan_key: planKey }),
    }).catch(() => {});
  } catch {
    // best-effort — never throw
  }
}
