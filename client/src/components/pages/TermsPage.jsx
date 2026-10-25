// Terms of Use for the site, its API and the Claude connector. The code
// license (PolyForm Noncommercial 1.0.0) and the data licenses on the Sources
// page govern what may be done with what the service returns; this page states
// the terms of using the service itself, so that bulk use is covered by a
// stated rule and not only by a license file in the repository.
export default function TermsPage() {
  return (
    <div className="bg-white rounded-lg shadow p-6 sm:p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Terms of Use</h1>

      <div className="prose max-w-none text-gray-700 space-y-6">
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">What this covers</h2>
          <p>
            These terms apply to the Tesserae website, its public API, its downloads and the
            Tesserae connector for AI assistants. By using any of them you accept these terms.
            Tesserae is a free research service for scholars, students and readers. It is
            operated by Neil Coffee, who holds the copyright in the software and in the
            project&rsquo;s own datasets.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Noncommercial use</h2>
          <p>
            The service, its results and its downloads are for noncommercial use, which means
            personal study, teaching, research, publication in scholarly form, and use by
            universities, libraries, schools, charities and public bodies. Commercial use of the service, of
            its results in bulk, or of its datasets needs a separate license from the copyright
            holder. The software is licensed under the PolyForm Noncommercial License 1.0.0 and
            the project&rsquo;s own datasets under CC BY-NC 4.0. The texts and catalogs in the
            corpus carry their own licenses, which the Sources page lists, and a few are
            indexed for search only and are never served in full.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Fair use of a shared service</h2>
          <p>
            The service runs on one university server for everyone. Use it as a reader would. Run searches, read passages, export the results you need. Whole texts, indexes and
            datasets are offered as archives on the Downloads page, each under the license named
            there, and that is the way to take them in bulk. Do not copy them through the API or
            the connector, do not run automated requests at a rate that crowds out other users, and
            do not try to reach data the site does not offer. The service may slow down, hold back
            or refuse requests that exceed what a person at a keyboard would make, and may block an
            address that keeps doing so. If you need something the Downloads page does not offer,
            ask through the request link on the site and we will usually arrange it.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Citing what you use</h2>
          <p>
            Results used in published work should cite Tesserae as the About page describes and
            name the source and translator of any text quoted, as the Reader shows them. Machine
            translations are marked as such and are unreviewed. Quote them only with that label.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Accounts and contributions</h2>
          <p>
            An account is optional and is governed by the Privacy Policy. Texts, corrections and
            requests you submit may be used to improve the corpus and the service, with credit
            where a source is named. By submitting a text you confirm that you have the right to
            share it under the license you state.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">No warranty</h2>
          <p>
            The service is provided as it is, without warranty of any kind. Parallels, scores,
            descriptions and machine translations are produced by software and should be checked
            against the texts before they are relied on. The service may change or pause without
            notice.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Questions</h2>
          <p>
            For a commercial license, a large extract or any question about these terms, use the
            request link in the site header or the contact address on the About page.
          </p>
          <p className="text-sm text-gray-500">In force from 2026-10-25.</p>
        </section>
      </div>
    </div>
  );
}
