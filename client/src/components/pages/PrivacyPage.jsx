export default function PrivacyPage() {
  return (
    <div className="bg-white rounded-lg shadow p-6 sm:p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Privacy Policy</h1>
      
      <div className="prose max-w-none text-gray-700 space-y-6">
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Data Collection</h2>
          <p>
            Tesserae V6 collects minimal personal information necessary to provide our intertextual 
            analysis services. When you sign in using Replit authentication, we receive your name 
            and email address to identify your account and attribute your contributions.
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
            Your data is stored securely on Replit's infrastructure. Search configurations may be 
            stored locally in your browser's localStorage for convenience. Intertext contributions 
            you mark as "public" will be visible to other users.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Third-Party Services</h2>
          <p>
            Tesserae uses the following third-party services:
          </p>
          <ul className="list-disc list-inside space-y-1">
            <li><strong>Replit:</strong> Hosting and authentication services</li>
            <li><strong>Wiktionary API:</strong> Dictionary definitions for rare words</li>
            <li><strong>Perseus Digital Library:</strong> Fallback definitions</li>
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
          Last updated: January 2026
        </div>
      </div>
    </div>
  );
}
