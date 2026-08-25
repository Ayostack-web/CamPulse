'use client';

export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-3xl mx-auto mb-6">
        <button onClick={() => window.history.back()} className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>
      </div>
      <div className="max-w-3xl mx-auto bg-white rounded-2xl shadow-sm border border-gray-100 p-8 md:p-12">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Privacy Policy</h1>
        <p className="text-sm text-gray-500 mb-8">Last updated: July 17, 2026</p>

        <div className="space-y-8 text-gray-700 leading-relaxed">
          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">1. Introduction</h2>
            <p>
              Vylix Academic Hub (&quot;we&quot;, &quot;our&quot;, or &quot;us&quot;) is an AI-powered study companion platform designed for university students. This Privacy Policy explains how we collect, use, and protect your information when you use our application.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">2. Information We Collect</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li><strong>Account Information:</strong> Your name, email address, and profile picture when you sign in with Google.</li>
              <li><strong>Academic Information:</strong> Department, level, matric number, and course enrollments you provide.</li>
              <li><strong>Usage Data:</strong> Quiz performance, study patterns, and feature usage to personalize your experience.</li>
              <li><strong>Documents:</strong> Course materials you upload for AI analysis and studying.</li>
              <li><strong>Communications:</strong> Messages sent through the collaboration chat feature.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">3. How We Use Your Information</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li>To provide and personalize the AI tutoring and study features.</li>
              <li>To track your academic progress and generate study recommendations.</li>
              <li>To enable collaboration with classmates.</li>
              <li>To improve our application and develop new features.</li>
              <li>To send important updates about your account or the platform.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">4. Data Storage and Security</h2>
            <p>
              Your data is stored securely using industry-standard encryption. We use Supabase for authentication and database management, with data hosted on secure cloud infrastructure. We implement appropriate security measures to protect your personal information.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">5. Data Sharing</h2>
            <p>
              We do not sell or rent your personal information to third parties. Your data may be shared only in the following circumstances:
            </p>
            <ul className="list-disc pl-6 space-y-2 mt-2">
              <li>With your explicit consent.</li>
              <li>To comply with legal obligations.</li>
              <li>With service providers who assist in operating our platform (e.g., AI processing via Google Gemini).</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">6. AI Features</h2>
            <p>
              Our AI features use Google Gemini to process your queries and document content. Your messages and documents may be sent to AI services for processing. We do not use your data to train AI models.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">7. Your Rights</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li>Access and view your personal data.</li>
              <li>Request correction of inaccurate data.</li>
              <li>Request deletion of your account and data.</li>
              <li>Opt out of non-essential data collection.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">8. Children&apos;s Privacy</h2>
            <p>
              Our service is intended for university students who are 16 years or older. We do not knowingly collect information from children under 16.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">9. Changes to This Policy</h2>
            <p>
              We may update this Privacy Policy from time to time. We will notify you of any material changes by posting the new policy on this page and updating the &quot;Last updated&quot; date.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">10. Contact Us</h2>
            <p>
              If you have questions about this Privacy Policy, please contact us at{' '}
              <a href="mailto:ayostackdev@gmail.com" className="text-blue-600 hover:underline">
                ayostackdev@gmail.com
              </a>
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
