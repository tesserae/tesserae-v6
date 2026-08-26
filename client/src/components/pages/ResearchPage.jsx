export default function ResearchPage({ setPageType }) {
  return (
    <div className="bg-white rounded-lg shadow p-4 sm:p-8">
      <h2 className="text-2xl font-semibold text-gray-900 mb-2">Research</h2>
      <p className="text-gray-600 text-sm mb-4">
        As part of its ongoing work, the project team endeavors to produce publications and presentations
        that report on methods developed, theoretical consequences of digital intertextual search, and
        applied literary studies. The Tesserae project is by nature collaborative and interdisciplinary,
        and we welcome feedback from users and interested scholars.
      </p>

      <div className="prose max-w-none space-y-8">

        {/* Publications */}
        <section>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Publications</h3>
          <ul className="space-y-3 text-gray-700 text-sm leading-relaxed">
            <li>
              Coffee, Neil, and James Gawley. 2020. "How Rare are the Words that Make up Intertexts? A Study in Latin and Greek Epic Poetry." In Coffee, N., et al. (eds.),{' '}
              <em>Intertextuality in Flavian Epic Poetry</em>. Berlin: De Gruyter.
            </li>
            <li>
              Coffee, Neil, Christopher Forstall, Lavinia Galli Milic, and Damien Nelis, eds. 2020.{' '}
              <em>Intertextuality in Flavian Epic Poetry</em>. Trends in Classics — Supplementary Volumes 64. Berlin: De Gruyter.
            </li>
            <li>
              Yolles, Julian. 2019. "Review: Discovering Intertextual Parallels in Latin and Greek Texts with Tesserae."{' '}
              <em>SCS Blog, Society for Classical Studies</em>, March 24, 2019.
            </li>
            <li>
              Forstall, Christopher W., and Walter J. Scheirer. 2019.{' '}
              <em>Quantitative Intertextuality: Analyzing the Markers of Information Reuse</em>. Springer International Publishing.
            </li>
            <li>
              Coffee, Neil. 2019. "Intertextuality as Viral Phrases: Roses and Lilies." In Monica Berti (ed.),{' '}
              <em>Digital Classical Philology: Ancient Greek and Latin in the Digital Revolution</em>. De Gruyter, pp. 177–200.
            </li>
            <li>
              Coffee, Neil. 2018. "An Agenda for the Study of Intertextuality."{' '}
              <em>Transactions of the American Philological Association</em> 148, no. 1: 205–223.
            </li>
            <li>
              Coffee, Neil, Christopher Forstall, and James Gawley. 2017. "The Tesserae Project: Detecting Intertextuality of Meaning and Sound." In Mastandrea, P. (ed.),{' '}
              <em>Strumenti digitali e collaborativi per le Scienze dell'Antichità</em>. Edizioni Ca'Foscari, pp. 189–192.
            </li>
            <li>
              Diddams, A. C., and James Gawley. 2017. "Measuring the Presence of Roman Rhetoric: An Intertextual Analysis of Augustine's <em>De Doctrina Christiana</em> IV."{' '}
              <em>Mouseion</em> 14, no. 3: 391–408.
            </li>
            <li>
              Coffee, Neil, and Christopher Forstall. 2016. "Claudian's Engagement with Lucan in his Historical and Mythological Hexameters." In Berlincourt, V., Galli-Milic, L., and Nelis, D. (eds.),{' '}
              <em>Lucan and Claudian: Context and Intertext</em>. Winter Verlag, pp. 255–284.
            </li>
            <li>
              Scheirer, Walter, Christopher Forstall, and Neil Coffee. 2016. "The Sense of a Connection: Automatic Tracing of Intertextuality by Meaning."{' '}
              <em>Digital Scholarship in the Humanities</em> 31, no. 1: 204–217.
            </li>
            <li>
              Forstall, Christopher, Neil Coffee, Thomas Buck, Katherine Roache, and Sarah Jacobson. 2015.
              "Modeling the Scholars: Detecting Intertextuality through Enhanced Word-Level N-Gram Matching."{' '}
              <em>Digital Scholarship in the Humanities</em> 30, no. 4: 503–515.
            </li>
            <li>
              Coffee, Neil, James Gawley, Christopher Forstall, Walter Scheirer, Jason Corso, David Johnson, and Brian Parks. 2014.
              "Modeling the Interpretation of Literary Allusion with Machine Learning Techniques."{' '}
              <em>Journal of Digital Humanities</em> 3, no. 1.
            </li>
            <li>
              Coffee, Neil, Jean-Pierre Koenig, Shakthi Poornima, Christopher Forstall, Roelant Ossewaarde, and Sarah Jacobson. 2012.
              "The Tesserae Project: Intertextual Analysis of Latin Poetry."{' '}
              <em>Literary and Linguistic Computing</em> 28, no. 1: 221–228.
            </li>
            <li>
              Coffee, Neil, Jean-Pierre Koenig, Shakthi Poornima, Christopher Forstall, Roelant Ossewaarde, and Sarah Jacobson. 2012.
              "Intertextuality in the Digital Age."{' '}
              <em>Transactions of the American Philological Association</em> 142, no. 2: 383–422.
            </li>
            <li>
              Forstall, Christopher, Sarah Jacobson, and Walter Scheirer. 2011. "Evidence of Intertextuality: Investigating Paul the Deacon's <em>Angustae Vitae</em>."{' '}
              <em>Literary and Linguistic Computing</em> 26, no. 3: 285–296.
            </li>
            <li>
              Forstall, Christopher, and Walter Scheirer. 2010. "Features from Frequency: Authorship and Stylistic Analysis Using Repetitive Sound."{' '}
              <em>Proceedings of the Chicago Colloquium on Digital Humanities and Computer Science</em> 1, no. 2.
            </li>
          </ul>
        </section>

        {/* Conferences Organized */}
        <section>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Conferences Organized</h3>
          <ul className="space-y-3 text-gray-700 text-sm leading-relaxed">
            <li>
              "Intertextuality in Flavian Epic Poetry." May 28–30, 2015, Fondation Hardt, Geneva, Switzerland.
              Co-organized with Damien Nelis, Lavinia Galli-Milic, and Christopher Forstall, University of Geneva Classics.
            </li>
            <li>
              "Intertextualité et humanités numériques: approches, méthodes, tendances / Intertextuality and Digital Humanities: Approaches, Methods, Trends."
              February 13–15, 2014, Fondation Hardt, Geneva, Switzerland.
              Co-organized with Damien Nelis and Lavinia Galli-Milic, University of Geneva Classics.
            </li>
          </ul>
        </section>

        {/* Evaluation Data */}
        <section className="bg-amber-50 border border-amber-200 rounded-lg p-5">
          <h3 className="text-lg font-semibold text-amber-900 mb-3">Evaluation Data</h3>
          <p className="text-gray-700 text-sm mb-4">
            Tesserae V6's feature fusion system was evaluated against gold-standard benchmark datasets
            comprising 862 parallel passages drawn from published scholarly commentaries. 
            Detailed results and benchmark datasets are available on the downloads page.
          </p>
          <button
            onClick={() => setPageType('downloads')}
            className="text-amber-700 hover:underline font-medium text-sm transition-colors"
          >
            Access Evaluation Benchmarks and Downloads →
          </button>
        </section>


        {/* Presentations */}
        <section>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Presentations</h3>
          <ul className="space-y-3 text-gray-700 text-sm leading-relaxed">
            <li>Scheirer, Walter. 2018. "Tesserae Information Service." NEH Office of Digital Humanities Directors Meeting Lightning Round. February 9.</li>
            <li>Coffee, Neil. 2017. "Roses and Lilies: What Digital Approaches Can Do for the Study of Intertextuality." <em>Classical Philology Goes Digital: Working on Textual Phenomena of Ancient Texts</em>. Potsdam, Germany. February 16–17.</li>
            <li>Gawley, James, Elizabeth Hunter, Tessa Little, and Caitlin Diddams. 2017. "Vergil and Homer: A Digital Annotation of Knauer's Intertextual Catalogue." DiXit Workshop: "The Educational Impact of DSE." Rome, Italy. January 24.</li>
            <li>Gawley, James. 2017. "Intertext Mining with Tesserae." Ancient MakerSpaces Workshop, SCS 2017. Toronto, Canada. January 7.</li>
            <li>Diddams, Caitlin. 2016. "Comparative Bigram Frequencies of Latin Authors and the Classical Latin Corpus." LAWDNY Digital Antiquity Research Workshop at ISAW. December 2.</li>
            <li>Diddams, Caitlin. 2016. "Something Old, Something New: Quantifying the Influence of Ancient Latin Epic on Prudentius' <em>Psychomachia</em>." <em>Rising Up: Resurgences and Revivals in the Ancient World</em>. Buffalo, NY. October 1.</li>
            <li>Forstall, Christopher W., Lavinia Galli Milic, and Damien Nelis. 2016. "Approaches to Thematic Classification for Latin Epic." <em>Digital Humanities 2016</em>. Krakow, Poland. July.</li>
            <li>Gawley, James, and Caitlin Diddams. 2016. "Big Data and the Study of Allusion: An Exploration of Tesserae's Multitext Capability." <em>Digital Humanities 2016</em>. Krakow, Poland. July.</li>
            <li>Bernstein, Neil. 2016. "Practical Criticism and the New Digital Tools for Intertextual Study. Comparing Tesserae and Musisque Deoque." Midwest Classical Literature Consortium, Oberlin College. April 16.</li>
            <li>Diddams, Caitlin. 2016. "Echoes of Cicero: A Digital Approach to Augustine's Presentation of Pauline Diction." <em>Classical Association of the Middle West and South Annual Meeting</em>. Williamsburg, VA. March 18.</li>
            <li>Forstall, Christopher, and Lavinia Galli Milic. 2015. "Thematic Features for Intertextual Analysis." <em>Digital Classicist Seminar Berlin</em>. October 13.</li>
            <li>Burns, Patrick. 2015. "Measuring Allusive Density in Lucan's <em>Bellum Civile</em> Using Tesserae." <em>Institute for the Study of the Ancient World</em>. October 2.</li>
            <li>Bernstein, Neil. 2015. "Comparative Rates of Text Reuse in Classical Latin Hexameter Poetry." <em>Classical Association of the Middle West and South Annual Meeting</em>. Boulder, CO. March.</li>
            <li>Coffee, Neil. 2015. Response, "Making Meaning from Data." Digital Classics Association Joint Colloquium, <em>AIA/SCS Annual Meetings</em>. New Orleans, LA. January 11.</li>
            <li>Gawley, James, Christopher Forstall, and Konnor Clark. 2014. "Automating the Search for Cross-Language Text Reuse." Short paper, <em>Digital Humanities 2014</em>. Lausanne, Switzerland. July 11.</li>
            <li>Scheirer, Walter, and Christopher Forstall. 2014. "Euterpe's Hidden Song: Patterns in Elegy." Poster, <em>Digital Humanities 2014</em>. Lausanne, Switzerland. July 10.</li>
            <li>Coffee, Neil. 2014. Panel participant, "Rethinking Text Reuse as Digital Classicists." <em>Digital Humanities 2014</em>. Lausanne, Switzerland. July 10.</li>
            <li>Coffee, Neil. 2014. "Modeling the Scholars: Detecting Intertextuality through Enhanced Word-Level N-Gram Matching." <em>International Workshop on Computer Aided Processing of Intertextuality in Ancient Languages</em>. INSA Lyon. June 2.</li>
            <li>Gervais, Kyle. 2014. "Flavian Intertextuality: A Digital Approach." 35th ASCS Conference. Auckland, NZ. January.</li>
            <li>Bernstein, Neil, Kyle Gervais, and Wei Lin. 2014. "Comparative Rates of Text Reuse in Latin Epic." <em>APA/AIA Annual Meetings</em>. January 3.</li>
            <li>Coffee, Neil. 2013. "Roses and Lilies: Digital Adventures in Intertextuality." Invited lecture, Yale University. December 5.</li>
            <li>Gawley, James, Christopher Forstall, Konnor Clark, and Amy Miu. 2013. "Two Methods for Discovering Cross-Language Text Reuse." <em>Chicago Colloquium on Digital Humanities & Computer Science</em>. December 5.</li>
            <li>Coffee, Neil, James Gawley, Christopher Forstall, Walter Scheirer, David Johnson, Jason Corso, and Brian Parks. 2013. "Modeling the Interpretation of Literary Allusion with Machine Learning Techniques." Poster, <em>Digital Humanities 2013</em>. University of Nebraska–Lincoln. July 18.</li>
            <li>Coffee, Neil, Christopher Forstall, and James Gawley. 2013. "What is Allusion? A Digital Approach." Poster, <em>Digital Classics Association</em> conference. University at Buffalo. April 5.</li>
            <li>Forstall, Christopher, and Walter J. Scheirer. 2012. "Revealing Hidden Patterns in the Meter of Homer's <em>Iliad</em>." Poster, <em>Chicago Colloquium on Digital Humanities and Computer Science</em>. University of Chicago. November 17–19.</li>
            <li>Gawley, James, Christopher Forstall, and Neil Coffee. 2012. "Evaluating the Literary Significance of Text Re-Use in Latin Poetry." Poster, <em>Chicago Colloquium on Digital Humanities and Computer Science</em>. University of Chicago. November 17–19.</li>
            <li>Coffee, Neil. 2012. "Large- and Small-Scale Intertextuality in Claudian's Historical and Mythical Hexameters." <em>Lucain et Claudien face à face</em>. Fondation Hardt, Geneva, Switzerland. November 8–10.</li>
            <li>Forstall, Christopher. 2012. "Revealing Intertextuality with Tesserae." Workshop, <em>Lucain et Claudien face à face</em>. Fondation Hardt, Geneva, Switzerland. November 8–10.</li>
            <li>Coffee, Neil, Jean-Pierre Koenig, Shakthi Poornima, Christopher Forstall, Roelant Ossewaarde, and Sarah Jacobson. 2011. "The Tesserae Project: Intertextual Analysis of Latin Poetry." Poster, <em>Digital Humanities 2011</em>. Stanford University. June 19–21.</li>
            <li>Forstall, Christopher, and Walter Scheirer. 2011. "Visualizing Sound as Functional N-Grams in Homeric Greek Poetry." Poster, <em>Digital Humanities 2011</em>. Stanford University. June 19–21.</li>
            <li>Forstall, Christopher, and Walter Scheirer. 2010. "A Statistical Stylistic Study of Latin Elegiac Couplets." Poster, <em>Chicago Colloquium on Digital Humanities and Computer Science</em>. November 21–22.</li>
          </ul>
        </section>

        {/* References to Tesserae */}
        <section>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">References to Tesserae</h3>
          <p className="text-gray-700 text-sm mb-4">
            Tesserae has been cited and used by researchers across classics, digital humanities,
            and computational linguistics:
          </p>
          <ul className="space-y-3 text-gray-700 text-sm leading-relaxed">
            <li>Gong, Ashley, Katy Gero, and Mark Schiefsky. 2025. "Augmented Close Reading for Classical Latin Using BERT for Intertextual Exploration." <em>Proceedings of the 5th International Conference on Natural Language Processing for Digital Humanities</em>.</li>
            <li>Dexter, Joseph P., Pramit Chaudhuri, Patrick J. Burns, et al. 2024. "A Database of Intertexts in Valerius Flaccus' <em>Argonautica</em> 1." <em>Journal of Open Humanities Data</em> 10 (1): 14.</li>
            <li>Riemenschneider, Frederick, and Anette Frank. 2023. "Graecia capta ferum victorem cepit: Detecting Latin Allusions to Ancient Greek Literature." <em>Proceedings of the Ancient Language Processing Workshop</em>, 30–38.</li>
            <li>Burns, Patrick J., James A. Brofos, Kyle Li, Pramit Chaudhuri, and Joseph P. Dexter. 2021. "Profiling of Intertextuality in Latin Literature Using Word Embeddings." <em>Proceedings of NAACL-HLT 2021</em>, 4900–4907.</li>
            <li>Pade, Marriane. 2020. "Imitation and Intertextuality in Humanist Translation." In <em>Philology Then and Now. Proceedings of the Danish Academy in Rome</em>. Academia di Danimarca, 169–186.</li>
            <li>Corbeill, Anthony. 2020. "How Not to Write like Cicero: <em>Pridie quam in exilium iret oratio</em>." <em>Ciceroniana Online</em> IV:1, pp. 17–36.</li>
            <li>Manjavacas, Enrique, Brian Long, and Mike Kestemont. 2019. "On the Feasibility of Automated Detection of Allusive Text Reuse." <em>Proceedings of the 3rd Joint SIGHUM Workshop</em>, 104–114.</li>
            <li>Chaudhuri, Pramit, and Joseph P. Dexter. 2017. "Bioinformatics and Classical Literary Study." <em>Journal of Data Mining & Digital Humanities</em>, Special Issue.</li>
            <li>Nelis, Damien, Christopher Forstall, and Lavinia Galli Milic. 2017. "Intertextuality and Narrative Context: Digital Narratology?" HAL preprint hal-01480773.</li>
            <li>Burns, Patrick. 2016. "Measuring and Mapping Intergeneric Allusion in Latin Poetry Using Tesserae." <em>Journal of Data Mining and Digital Humanities</em>.</li>
            <li>Marmerola, Guilherme D., et al. 2016. "On the Reconstruction of Text Phylogeny Trees: Evaluation and Analysis of Textual Relationships." <em>PLoS ONE</em> 11(12): e0167822.</li>
            <li>Roe, Glenn, Clovis Gladstone, Robert Morrissey, et al. 2016. "Digging into ECCO: Identifying Commonplaces and Other Forms of Text Reuse at Scale." <em>Digital Humanities DH2016</em>. Krakow, Poland, pp. 336–339.</li>
            <li>Jänicke, Stefan, Greta Franzini, Muhammad Faisal Cheema, and Gerik Scheuermann. 2016. "Visual Text Analysis in Digital Humanities." <em>Computer Graphics Forum</em>. June.</li>
            <li>Verhaar, P. A. F. 2016. <em>Affordances and Limitations of Algorithmic Criticism</em>. Ph.D. dissertation, Leiden.</li>
            <li>Duhaime, Douglas Ernest. 2016. "Textual Reuse in the Eighteenth Century: Mining Eliza Haywood's Quotations." <em>Digital Humanities Quarterly</em> 10, no. 1.</li>
            <li>Montoro, Rocío. 2016. "The Year's Work in Stylistics 2015." <em>Language and Literature</em> 25(4): 380.</li>
            <li>Bernstein, Neil, Kyle Gervais, and Wei Lin. 2015. "Comparative Rates of Text Reuse in Classical Latin Hexameter Poetry." <em>Digital Humanities Quarterly</em> 9, no. 3.</li>
            <li><em>Authors Guild v. Google Inc.</em> 2015. 2nd Circuit Appeals Court Decision, October 16. P. 8 n. 6, citing Forstall, Coffee et al. 2015.</li>
            <li>Chaudhuri, Pramit, Joseph P. Dexter, and Jorge A. Bonilla Lopez. 2015. "Strings, Triangles, and Go-betweens: Intertextual Approaches to Silius' Carthaginian Debates." <em>Dictynna</em> 12.</li>
            <li>Newlands, Carole E., Kyle Gervais, and William J. Dominik. 2015. "Reading Statius." In <em>Brill's Companion to Statius</em>. p. 12 n. 49.</li>
            <li>Buchanan, Sarah. 2015. "The Emerging Tradition of Digital Classics." In <em>Annual Review of Cultural Heritage Informatics: 2014</em>, ed. S. K. Hastings. Rowman & Littlefield.</li>
            <li>Mastandrea, Paolo. 2014. "<em>Laudes Domini</em> e <em>Vestigia Ennii</em>. Automatismi e volontarietà nel riuso dei testi." <em>Il calamo della memoria</em> VI: 51–80.</li>
            <li>Büchler, Marco, Greta Franzini, Emily Franzini, and Maria Moritz. 2014. "Scaling Historical Text Re-Use." <em>Big Data (Big Data), 2014 IEEE International Conference</em>.</li>
            <li>Crane, Gregory, Bridget Almas, et al. 2014. "Cataloging for a Billion Word Library of Greek and Latin." <em>DATeCH '14 Proceedings</em>, pp. 83–88.</li>
            <li>Ganascia, Jean-Gabriel, Pierre Glaudes, and Andrea Del Lungo. 2014. "Automatic Detection of Reuses and Citations in Literary Texts." <em>Literary and Linguistic Computing</em> 29: 412–421.</li>
            <li>Ripoll, François. 2014. "Mémoire de Valérius Flaccus dans l'Achilléide de Stace." <em>Revue des Études Anciennes</em> 116: 84 n. 5.</li>
            <li>Williams, David-Antoine. 2013. "Method as Tautology in the Digital Humanities." <em>Digital Scholarship in the Humanities</em>.</li>
            <li>Baraz, Yelena, and Christopher van den Berg. 2013. "Introduction" to special issue on Intertextuality. <em>American Journal of Philology</em> 134: p. 4 n. 22.</li>
          </ul>
        </section>

        {/* V3 Blog Archive Link */}
        <section>
          <h3 className="text-lg font-semibold text-gray-900 mb-3">V3 Blog Archive</h3>
          <p className="text-gray-700 text-sm">
            Scholarly posts from the legacy Tesserae V3 website (2019–2021) have been preserved.{' '}
            <button
              onClick={() => setPageType('blog-archive')}
              className="text-amber-600 hover:underline font-medium"
            >
              View archived blog posts
            </button>
          </p>
        </section>

        {/* Contact */}
        <section className="border-t pt-6 mt-6">
          <p className="text-gray-700 text-sm">
            For questions about Tesserae research, contact{' '}
            <a href="mailto:ncoffee@buffalo.edu" className="text-amber-600 hover:underline">
              Neil Coffee
            </a>{' '}
            (Department of Classics, University at Buffalo).
          </p>
        </section>
      </div>
    </div>
  );
}
