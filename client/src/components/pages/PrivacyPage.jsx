export default function PrivacyPage() {
  return (
    <div className="bg-white rounded-lg shadow p-6 sm:p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Privacy Policy</h1>
      <p className="text-sm text-gray-500 mb-4">The <a href="/terms" className="text-red-700 hover:underline">Terms of Use</a> state what the service may be used for.</p>
      
      <div className="prose max-w-none text-gray-700 space-y-6">
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Data Collection</h2>
          <p>
            Tesserae V6 collects minimal personal information necessary to provide our intertextual
            analysis services. If you create an account, we keep your name, your email address and
            your password to identify your account and attribute your contributions. The password is
            stored only in scrambled (hashed) form, so no one can read it.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">How We Use Your Data</h2>
          <ul className="list-disc list-inside space-y-1">
            <li>To provide personalized features like saved searches and personal intertext collections</li>
            <li>To attribute contributions to the Intertext Repository</li>
            <li>To respond to text requests and feedback submissions</li>
            <li>To improve the Tesserae platform and user experience</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">ORCID Integration</h2>
          <p>
            If you choose to link your ORCID identifier, this information is stored to provide 
            proper academic attribution for your contributions. ORCID linking is entirely optional 
            and can be removed at any time from your profile settings.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Data Storage</h2>
          <p>
            Your data is stored on the University at Buffalo server that runs this site. Search
            configurations may be stored locally in your browser's localStorage for convenience.
            Intertext contributions you mark as "public" will be visible to other users. Questions
            put to Tessa, the assistant, and her answers are kept on the server without any
            identifier, so that a sample can be read for accuracy; her model runs on the
            university's own AI platform, so the text of a question does not leave campus.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Speed Log</h2>
          <p>
            To measure how fast the site answers, the server logs each search request with its
            time, the kind of request and how long it took. Your search terms are not logged, and
            neither is your address. Each line carries a code that changes every day and cannot be
            traced back to you. It only tells one visitor&apos;s requests apart from another&apos;s
            on the same day.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Third-Party Services</h2>
          <p>
            Tesserae uses the following third-party services:
          </p>
          <ul className="list-disc list-inside space-y-1">
            <li><strong>Wiktionary API:</strong> Dictionary definitions for rare words</li>
            <li><strong>Perseus Digital Library:</strong> Fallback definitions</li>
            <li><strong>OpenStreetMap:</strong> The map on the Events page. Your browser fetches the map tiles from OpenStreetMap's servers, so OpenStreetMap sees your address and the map area requested. Nothing else is sent.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Your Rights</h2>
          <p>
            You may request deletion of your account and associated data by contacting us through 
            the feedback form. You can also manage your saved searches and intertext collections 
            directly through the application.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Research Use</h2>
          <p>
            Tesserae is an academic research tool. Anonymized usage statistics may be used for 
            research purposes to improve intertextual analysis methodologies. No personally 
            identifiable information is shared in research publications.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Contact</h2>
          <p>
            For privacy-related inquiries, please use the feedback form in the Help & Support 
            section or contact the Tesserae project team.
          </p>
        </section>

        <div className="text-sm text-gray-500 pt-4 border-t">
          Last updated: October 2026
        </div>
      </div>
    </div>
  );
}
