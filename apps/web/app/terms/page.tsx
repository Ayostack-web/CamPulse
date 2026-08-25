'use client';

export default function TermsOfService() {
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
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Terms of Service</h1>
        <p className="text-sm text-gray-500 mb-8">Last updated: July 17, 2026</p>

        <div className="space-y-8 text-gray-700 leading-relaxed">
          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">1. Acceptance of Terms</h2>
            <p>
              By accessing or using Vylix Academic Hub (&quot;the Service&quot;), you agree to be bound by these Terms of Service. If you do not agree to these terms, please do not use the Service.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">2. Description of Service</h2>
            <p>
              Vylix Academic Hub is an AI-powered study companion platform for university students. The Service provides course material management, AI tutoring, practice quizzes, study planning, and collaboration features.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">3. Eligibility</h2>
            <p>
              The Service is available to university students aged 16 and older. By using the Service, you represent that you meet these eligibility requirements.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">4. Account Responsibilities</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li>You are responsible for maintaining the security of your account.</li>
              <li>You must provide accurate and complete information when creating your account.</li>
              <li>You must not share your account credentials with others.</li>
              <li>You must notify us immediately of any unauthorized use of your account.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">5. Acceptable Use</h2>
            <p>You agree not to:</p>
            <ul className="list-disc pl-6 space-y-2 mt-2">
              <li>Use the Service for any unlawful purpose.</li>
              <li>Upload malicious content or viruses.</li>
              <li>Attempt to gain unauthorized access to other users&apos; accounts or data.</li>
              <li>Use the Service to harass, abuse, or harm others.</li>
              <li>Reverse engineer or attempt to extract the source code of the Service.</li>
              <li>Use automated systems to access the Service without permission.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">6. User Content</h2>
            <p>
              You retain ownership of any content you upload to the Service, including course materials and documents. By uploading content, you grant us a limited license to process and store your content for the purpose of providing the Service.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">7. AI Features Disclaimer</h2>
            <p>
              Our AI features are provided for educational assistance only. AI-generated content may contain errors and should not be considered authoritative academic advice. Always verify AI-generated information with your course materials and instructors.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">8. Intellectual Property</h2>
            <p>
              The Service, including its design, code, and features, is owned by Vylix and protected by intellectual property laws. You may not copy, modify, or distribute any part of the Service without our written permission.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">9. Limitation of Liability</h2>
            <p>
              The Service is provided &quot;as is&quot; without warranties of any kind. We are not liable for any damages arising from your use of the Service, including but not limited to direct, indirect, incidental, or consequential damages.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">10. Termination</h2>
            <p>
              We reserve the right to suspend or terminate your access to the Service at any time for conduct that we determine violates these Terms or is harmful to other users or the Service.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">11. Changes to Terms</h2>
            <p>
              We may update these Terms of Service from time to time. We will notify you of any material changes by posting the updated terms on this page.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">12. Contact</h2>
            <p>
              For questions about these Terms, contact us at{' '}
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
