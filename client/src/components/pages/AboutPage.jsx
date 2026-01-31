import { useState, useEffect } from 'react';

export default function AboutPage() {
  const [versionInfo, setVersionInfo] = useState({ version: '6.0', last_updated: null });

  useEffect(() => {
    fetch('/api/version')
      .then(res => res.json())
      .then(data => setVersionInfo(data))
      .catch(err => console.error('Failed to fetch version info:', err));
  }, []);

  return (
    <div className="bg-white rounded-lg shadow p-4 sm:p-8">
      <h2 className="text-2xl font-semibold text-gray-900 mb-6">About Tesserae</h2>
      
      <div className="prose max-w-none space-y-8">
        <section>
          <h3 className="text-lg font-semibold text-gray-900 mb-3">What is Tesserae?</h3>
          <p className="text-gray-700 leading-relaxed mb-3">
            Tesserae is an intertextual analysis tool for discovering textual parallels in classical literature. 
            It helps scholars find passages where one author may have been influenced by, alluding to, or directly 
            quoting another text. Founded by Neil Coffee and J. P. Koenig in 2008 at the University at Buffalo, SUNY, 
            this is Version 6, a modern reimplementation of the V3 algorithm.
          </p>
          <p className="text-gray-700 leading-relaxed">
            The name "Tesserae" refers to the small tiles used in Roman mosaics. Just as these tiles combine 
            to form larger images, textual parallels reveal the interconnected nature of classical literature.
          </p>
        </section>

        <section className="bg-amber-50 border border-amber-200 rounded-lg p-5">
          <h3 className="text-lg font-semibold text-amber-900 mb-3">Creation & Credits</h3>
          <p className="text-gray-700 mb-3">
            <strong>Tesserae V6</strong> was created in January 2026 by{' '}
            <a 
              href="https://arts-sciences.buffalo.edu/classics/faculty/core-faculty/coffee-neil.html" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-amber-600 hover:underline font-semibold"
            >
              Neil Coffee
            </a>{' '}
            (University at Buffalo) using <strong>Replit Agent</strong>, an AI-assisted development platform.
          </p>
          <p className="text-gray-700 mb-4">
            Tesserae is a collaboration between{' '}
            <a 
              href="https://www.buffalo.edu/cas/english/faculty/faculty_directory.host.html/content/shared/cas/english/faculty-staff/faculty/coffee.detail.html" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-amber-600 hover:underline font-semibold"
            >
              Neil Coffee
            </a>{' '}
            (University at Buffalo) and{' '}
            <a 
              href="https://engineering.nd.edu/faculty/walter-scheirer/" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-amber-600 hover:underline font-semibold"
            >
              Walter Scheirer
            </a>{' '}
            (University of Notre Dame). Neil created V6 and the team collaborates on its ongoing development.
          </p>
          <p className="text-gray-700 mb-4">
            <a 
              href="https://mta.ca/directory/chris-forstall" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-amber-600 hover:underline font-semibold"
            >
              Chris Forstall
            </a>{' '}
            (Mount Allison University) was the lead developer of Tesserae V3, which established the 
            core algorithms and infrastructure that V6 builds upon.
          </p>
          <p className="text-gray-700 mb-4">
            Graduate Tesserae Fellows have been at the core of the project from its inception. In chronological 
            order from the beginning of the project in 2008, they are (UB = U. Buffalo graduate student, 
            ND = Notre Dame graduate student): Poornima Shakthi (UB), Roelant Ossewarde (UB), Chris Forstall (UB), 
            James Gawley (UB), Jeffery Kinnison (ND), Tessa Little (UB), Nozomu Okuda (UB), Joseph Miller (UB), John James (UB), Abby Swenor (ND).
          </p>
          <div className="text-sm text-gray-700 space-y-2">
            <p><strong>Built upon:</strong></p>
            <ul className="list-disc list-inside ml-2 space-y-1">
              <li><strong>Tesserae V3</strong>: Original scoring algorithm, text corpus, and synonym dictionaries (developed by Chris Forstall at University at Buffalo)</li>
              <li><strong>Tesserae V5</strong>: API design concepts and modern architecture patterns (developed with Walter Scheirer)</li>
            </ul>
            <p className="mt-3"><strong>License:</strong> MIT License - free to use, modify, and redistribute.</p>
          </div>
        </section>

        <section>
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Key Features</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium text-red-700 mb-2">Multi-Language Support</h4>
              <p className="text-sm text-gray-600">
                Search within Latin, Greek, or English texts. Our corpus includes works from Homer to medieval authors.
              </p>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium text-red-700 mb-2">Cross-Lingual Analysis</h4>
              <p className="text-sm text-gray-600">
                Discover connections between Greek and Latin texts using AI-powered semantic matching (SPhilBERTa model).
              </p>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium text-red-700 mb-2">Rare Word Search</h4>
              <p className="text-sm text-gray-600">
                Find rare vocabulary shared between texts - often indicative of direct influence.
              </p>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium text-red-700 mb-2">V3-Style Scoring</h4>
              <p className="text-sm text-gray-600">
                Our scoring algorithm uses Inverse Document Frequency (IDF) and distance penalties for precise results.
              </p>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium text-red-700 mb-2">Word Pairs Detection</h4>
              <p className="text-sm text-gray-600">
                Identify unusual word combinations (bigrams) that may indicate textual borrowing even when individual words are common.
              </p>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium text-red-700 mb-2">Intertext Repository</h4>
              <p className="text-sm text-gray-600">
                Save and share discovered parallels with the scholarly community. Track verified intertexts.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h3 className="text-lg font-semibold text-gray-900 mb-3">The Corpus</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <div className="text-3xl font-bold text-red-700">1,444+</div>
              <div className="text-sm text-gray-600">Latin Texts</div>
            </div>
            <div className="text-center p-4 bg-amber-50 rounded-lg">
              <div className="text-3xl font-bold text-amber-700">650+</div>
              <div className="text-sm text-gray-600">Greek Texts</div>
            </div>
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <div className="text-3xl font-bold text-green-700">14+</div>
              <div className="text-sm text-gray-600">English Texts</div>
            </div>
          </div>
          <p className="text-gray-700 text-sm">
            Our corpus draws from authoritative sources including Perseus Digital Library, CSEL, and other 
            scholarly editions. Provenance information is tracked for each text.
          </p>
        </section>

        <section>
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Technical Details</h3>
          <ul className="list-disc list-inside text-gray-700 space-y-2">
            <li>Lemmatization via CLTK (Classical Language Toolkit) for Latin and Greek</li>
            <li>NLTK for English text processing</li>
            <li>SPhilBERTa model for cross-lingual semantic similarity</li>
            <li>Universal Dependencies treebank support for syntax analysis</li>
            <li>Metrical scansion data integrated from MQDQ/Pede Certo</li>
          </ul>
        </section>

        <section className="bg-green-50 border border-green-200 rounded-lg p-5">
          <h3 className="text-lg font-semibold text-green-900 mb-4">Grant Support & Acknowledgments</h3>
          <p className="text-gray-700 mb-4">
            The Tesserae Project has been made possible by the generous support of the following organizations:
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div className="bg-white p-4 rounded-lg border border-green-100">
              <a 
                href="https://www.neh.gov/divisions/odh" 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center gap-3 hover:opacity-80"
              >
                <img 
                  src="/logos/neh-logo.jpg" 
                  alt="NEH Logo" 
                  className="w-20 h-auto object-contain flex-shrink-0"
                />
                <div>
                  <div className="font-semibold text-gray-900">National Endowment for the Humanities</div>
                  <div className="text-sm text-gray-600">Office of Digital Humanities</div>
                  <div className="text-xs text-gray-500">Digital Humanities Advancement Grant (2018-2020)</div>
                  <div className="text-xs text-gray-500">Start-Up Phase II Grant (2012-2013)</div>
                </div>
              </a>
            </div>
            
            <div className="bg-white p-4 rounded-lg border border-green-100">
              <a 
                href="https://arts-sciences.buffalo.edu/classics.html" 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center gap-3 hover:opacity-80"
              >
                <img 
                  src="/logos/ub-logo.png" 
                  alt="University at Buffalo Logo" 
                  className="w-20 h-auto object-contain flex-shrink-0"
                />
                <div>
                  <div className="font-semibold text-gray-900">University at Buffalo, SUNY</div>
                  <div className="text-sm text-gray-600">Department of Classics</div>
                  <div className="text-xs text-gray-500">Institutional home and ongoing support</div>
                </div>
              </a>
            </div>
            
            <div className="bg-white p-4 rounded-lg border border-green-100">
              <a 
                href="https://www.snf.ch/en" 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center gap-3 hover:opacity-80"
              >
                <img 
                  src="/logos/snsf-logo.png" 
                  alt="Swiss National Science Foundation Logo" 
                  className="w-24 h-auto object-contain flex-shrink-0"
                />
                <div>
                  <div className="font-semibold text-gray-900">Swiss National Science Foundation</div>
                  <div className="text-sm text-gray-600">Intertextuality in Flavian Epic Poetry</div>
                  <div className="text-xs text-gray-500">Research Grant (2013-2016)</div>
                </div>
              </a>
            </div>
            
            <div className="bg-white p-4 rounded-lg border border-green-100">
              <a 
                href="https://www.fmsh.fr/" 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center gap-3 hover:opacity-80"
              >
                <img 
                  src="/logos/fmsh-logo.png" 
                  alt="Fondation Maison des Sciences de l'Homme Logo" 
                  className="w-20 h-auto object-contain flex-shrink-0"
                />
                <div>
                  <div className="font-semibold text-gray-900">Fondation Maison des Sciences de l'Homme</div>
                  <div className="text-sm text-gray-600">Transatlantic Program for Digital Humanities</div>
                  <div className="text-xs text-gray-500">TESSERAE MUSIVAE Project (2016-2017)</div>
                </div>
              </a>
            </div>
            
            <div className="bg-white p-4 rounded-lg border border-green-100">
              <a 
                href="https://aws.amazon.com/" 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center gap-3 hover:opacity-80"
              >
                <div className="w-16 h-16 bg-orange-500 rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-white font-bold text-sm">AWS</span>
                </div>
                <div>
                  <div className="font-semibold text-gray-900">Amazon Web Services</div>
                  <div className="text-sm text-gray-600">Cloud Computing Resources</div>
                  <div className="text-xs text-gray-500">In-kind grant (2016-2017)</div>
                </div>
              </a>
            </div>
            
            <div className="bg-white p-4 rounded-lg border border-green-100">
              <a 
                href="https://www.buffalo.edu/humanities-institute.html" 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center gap-3 hover:opacity-80"
              >
                <div className="w-16 h-16 bg-blue-800 rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-white font-bold text-xs">UBHI</span>
                </div>
                <div>
                  <div className="font-semibold text-gray-900">UB Humanities Institute</div>
                  <div className="text-sm text-gray-600">Digital Humanities Institute at Buffalo</div>
                  <div className="text-xs text-gray-500">Seed Grants & Fellowships (2008-2020)</div>
                </div>
              </a>
            </div>
          </div>
          
          <p className="text-sm text-gray-600 italic">
            We are grateful to all our supporters who have made this research possible over the years.
          </p>
        </section>

        <section>
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Contact</h3>
          <p className="text-gray-700">
            Questions or feedback? Contact{' '}
            <a href="mailto:ncoffee@buffalo.edu" className="text-amber-600 hover:underline">
              ncoffee@buffalo.edu
            </a>
          </p>
          <p className="text-gray-700 mt-2">
            <strong>Neil Coffee</strong>, Department of Classics, University at Buffalo
          </p>
        </section>

        <section>
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Citation</h3>
          <div className="bg-gray-100 p-4 rounded font-mono text-sm">
            Coffee, Neil. Tesserae V6: Intertextual and Literary Discovery. 
            University at Buffalo, 2026. Available at: tesserae.caset.buffalo.edu
          </div>
        </section>

        {versionInfo.last_updated && (
          <section className="border-t pt-4 mt-6">
            <p className="text-sm text-gray-500">
              <strong>Last Updated:</strong> {versionInfo.last_updated}
            </p>
          </section>
        )}
      </div>
    </div>
  );
}
