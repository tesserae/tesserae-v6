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
              Coffee, Neil, and Walter Scheirer. 2026. "Multi-Channel Fusion Search for Coptic Text Reuse."
              Preprint, Zenodo, November 25, 2026. Under review.{' '}
              <a href="https://doi.org/10.5281/zenodo.24542318" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.5281/zenodo.24542318
              </a>
            </li>
            <li>
              Coffee, Neil, and Walter Scheirer. 2026. "Feature Fusion for Computational Intertextuality Detection in Tesserae V6."
              Preprint, Zenodo, November 14, 2026.{' '}
              <a href="https://doi.org/10.5281/zenodo.24206123" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.5281/zenodo.24206123
              </a>
            </li>
            <li>
              Coffee, Neil, and James Gawley. 2020. "How Rare are the Words that Make up Intertexts? A Study in Latin and Greek Epic Poetry." In Coffee, N., et al. (eds.),{' '}
              <em>Intertextuality in Flavian Epic Poetry</em>. Berlin: De Gruyter.{' '}
              <a href="https://doi.org/10.1515/9783110602203-019" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.1515/9783110602203-019
              </a>
            </li>
            <li>
              Coffee, Neil, Christopher Forstall, Lavinia Galli Milic, and Damien Nelis, eds. 2020.{' '}
              <em>Intertextuality in Flavian Epic Poetry</em>. Trends in Classics — Supplementary Volumes 64. Berlin: De Gruyter.{' '}
              <a href="https://doi.org/10.1515/9783110602203" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.1515/9783110602203
              </a>
            </li>
            <li>
              Forstall, Christopher W., and Walter J. Scheirer. 2019.{' '}
              <em>Quantitative Intertextuality: Analyzing the Markers of Information Reuse</em>. Springer International Publishing.{' '}
              <a href="https://doi.org/10.1007/978-3-030-23415-7" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.1007/978-3-030-23415-7
              </a>
            </li>
            <li>
              Coffee, Neil. 2019. "Intertextuality as Viral Phrases: Roses and Lilies." In Monica Berti (ed.),{' '}
              <em>Digital Classical Philology: Ancient Greek and Latin in the Digital Revolution</em>. De Gruyter, pp. 177–200.{' '}
              <a href="https://doi.org/10.1515/9783110599572-011" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.1515/9783110599572-011
              </a> (open access)
            </li>
            <li>
              Coffee, Neil. 2018. "An Agenda for the Study of Intertextuality."{' '}
              <em>Transactions of the American Philological Association</em> 148, no. 1: 205–223.{' '}
              <a href="https://doi.org/10.1353/apa.2018.0008" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.1353/apa.2018.0008
              </a>
            </li>
            <li>
              Coffee, Neil, Christopher Forstall, and James Gawley. 2017. "The Tesserae Project: Detecting Intertextuality of Meaning and Sound." In Mastandrea, P. (ed.),{' '}
              <em>Strumenti digitali e collaborativi per le Scienze dell'Antichità</em>. Edizioni Ca'Foscari, pp. 189–192.{' '}
              <a href="https://doi.org/10.14277/6969-182-9/ANT-14-14" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.14277/6969-182-9/ANT-14-14
              </a> (open access)
            </li>
            <li>
              Diddams, A. C., and James Gawley. 2017. "Measuring the Presence of Roman Rhetoric: An Intertextual Analysis of Augustine's <em>De Doctrina Christiana</em> IV."{' '}
              <em>Mouseion</em> 14, no. 3: 391–408.{' '}
              <a href="https://doi.org/10.3138/mous.14.3-5" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.3138/mous.14.3-5
              </a>
            </li>
            <li>
              Coffee, Neil, and Christopher Forstall. 2016. "Claudian's Engagement with Lucan in his Historical and Mythological Hexameters." In Berlincourt, V., Galli-Milic, L., and Nelis, D. (eds.),{' '}
              <em>Lucan and Claudian: Context and Intertext</em>. Winter Verlag, pp. 255–284.{' '}
              <a href="https://doi.org/10.33675/978-3-8253-7564-5" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.33675/978-3-8253-7564-5
              </a>
            </li>
            <li>
              Scheirer, Walter, Christopher Forstall, and Neil Coffee. 2016. "The Sense of a Connection: Automatic Tracing of Intertextuality by Meaning."{' '}
              <em>Digital Scholarship in the Humanities</em> 31, no. 1: 204–217.{' '}
              <a href="https://doi.org/10.1093/llc/fqu058" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.1093/llc/fqu058
              </a>
            </li>
            <li>
              Forstall, Christopher, Neil Coffee, Thomas Buck, Katherine Roache, and Sarah Jacobson. 2015.
              "Modeling the Scholars: Detecting Intertextuality through Enhanced Word-Level N-Gram Matching."{' '}
              <em>Digital Scholarship in the Humanities</em> 30, no. 4: 503–515.{' '}
              <a href="https://doi.org/10.1093/llc/fqu014" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.1093/llc/fqu014
              </a>
            </li>
            <li>
              Coffee, Neil, James Gawley, Christopher Forstall, Walter Scheirer, Jason Corso, David Johnson, and Brian Parks. 2014.
              "Modeling the Interpretation of Literary Allusion with Machine Learning Techniques."{' '}
              <em>Journal of Digital Humanities</em> 3, no. 1.{' '}
              <a href="https://journalofdigitalhumanities.org/3-1/modelling-the-interpretation-of-literary-allusion-with-machine-learning-techniques/" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                journalofdigitalhumanities.org
              </a> (open access)
            </li>
            <li>
              Coffee, Neil, Jean-Pierre Koenig, Shakthi Poornima, Christopher Forstall, Roelant Ossewaarde, and Sarah Jacobson. 2012.
              "The Tesserae Project: Intertextual Analysis of Latin Poetry."{' '}
              <em>Literary and Linguistic Computing</em> 28, no. 1: 221–228.{' '}
              <a href="https://doi.org/10.1093/llc/fqs033" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.1093/llc/fqs033
              </a>
            </li>
            <li>
              Coffee, Neil, Jean-Pierre Koenig, Shakthi Poornima, Christopher Forstall, Roelant Ossewaarde, and Sarah Jacobson. 2012.
              "Intertextuality in the Digital Age."{' '}
              <em>Transactions of the American Philological Association</em> 142, no. 2: 383–422.{' '}
              <a href="https://doi.org/10.1353/apa.2012.0010" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.1353/apa.2012.0010
              </a>
            </li>
            <li>
              Forstall, Christopher, Sarah Jacobson, and Walter Scheirer. 2011. "Evidence of Intertextuality: Investigating Paul the Deacon's <em>Angustae Vitae</em>."{' '}
              <em>Literary and Linguistic Computing</em> 26, no. 3: 285–296.{' '}
              <a href="https://doi.org/10.1093/llc/fqr029" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.1093/llc/fqr029
              </a>
            </li>
            <li>
              Forstall, Christopher, and Walter Scheirer. 2010. "Features from Frequency: Authorship and Stylistic Analysis Using Repetitive Sound."{' '}
              <em>Proceedings of the Chicago Colloquium on Digital Humanities and Computer Science</em> 1, no. 2.{' '}
              <a href="https://doi.org/10.6082/M1TM789G" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">
                https://doi.org/10.6082/M1TM789G
              </a> (open access)
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
            <li>
              "Word, Space, Time: Digital Perspectives on the Classical World." April 5–6, 2013, University at Buffalo.
              Inaugural conference of the Digital Classics Association, with thirty presenters from Europe and North America.
            </li>
            <li>
              "Lucain et Claudien face à face: une poésie politique entre épopée, histoire et panégyrique." November 8–10, 2012, Fondation Hardt, Geneva, Switzerland.
              Co-organized with Damien Nelis, Lavinia Galli-Milic and Valéry Berlincourt, University of Geneva Classics.
            </li>
          </ul>
        </section>

        {/* Evaluation Data */}
        <section className="bg-amber-50 border border-amber-200 rounded-lg p-5">
          <h3 className="text-lg font-semibold text-amber-900 mb-3">Evaluation Data</h3>
          <p className="text-gray-700 text-sm mb-4">
            Tesserae V6's feature fusion system was evaluated against gold-standard benchmark datasets
            comprising 862 parallel passages drawn from published scholarly commentaries.
            The method and the evaluation are described in the preprint listed above,{' '}
            <a href="https://doi.org/10.5281/zenodo.24206123" target="_blank" rel="noopener noreferrer"
               className="text-amber-700 hover:underline">Coffee and Scheirer 2026</a>.
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
            <li>Coffee, Neil. 2028. Invited lecture on Tesserae. Department of Classical Studies, University of Western Ontario. London, Ontario. Early 2028, forthcoming.</li>
            <li>Coffee, Neil. 2027. "Tesserae V6 and Agentic AI in the Humanities" (provisional title). Invited paper, <em>Intertextuality and Quotations: Challenges and Possibilities at the Crossing between Rhetoric and Digital Humanities</em>. University of Turin, Italy. June 15–16, forthcoming.</li>
            <li>Coffee, Neil. 2027. "Multi-Channel Fusion for Improving Intertextual Search Recall." <em>Society for Classical Studies Annual Meeting</em>. Boston, MA. January, forthcoming.</li>
            <li>Coffee, Neil. 2026. "The Transparent Box: Building the Tesserae V6 Literary Research Site with Agentic AI." University at Buffalo Department of Classics. October 23.</li>
            <li>Coffee, Neil. 2026. "Tesserae V6 and Agentic AI in the Humanities." Lightning round talk, University at Buffalo Department of AI and Society Open House. September 21.</li>
            <li>Coffee, Neil. 2024. "The Tesserae Project." Digital and Public Humanities Roundtable, University of Missouri, Kansas City. February 29.</li>
            <li>Coffee, Neil. 2022. "Tesserulae Recompostae: The Evolution of the Tesserae Project for the Digital Study of Intertextuality." <em>Digital Humanities Beyond Modern English: Computational Analysis of Premodern and Non-Western Literature</em>. University of Texas at Austin. April 6.</li>
            <li>Coffee, Neil. 2021. "Finding Literary Allusions with Tesserae." American Library Association, European Studies Section, Classical, Medieval and Renaissance Discussion Group. January 27.</li>
            <li>Coffee, Neil. 2019. "The Tesserae Project." Lightning round presentation, University at Buffalo Digital Humanities Reading Group. September 20.</li>
            <li>Coffee, Neil. 2019. "Tracing Intertextuality by Meaning." <em>Quantitative Criticism Laboratory Conference</em>. Dartmouth College. April 25.</li>
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
            <li>Coffee, Neil. 2015. "Introduction to Tesserae." University of Colorado Department of Classics. December 8.</li>
            <li>Forstall, Christopher, Lavinia Galli Milic, Neil Coffee, and Damien Nelis. 2015. "Beyond Verbal Identity: Contextual Features for Intertext Discovery." Poster, <em>Humanités Numériques et Antiquité</em>. Grenoble, France. September 2–4.</li>
            <li>Coffee, Neil. 2015. "Microanalysis of Latin Intertextuality by Formal Features: Frequency and Line-Edge Proximity of Latin Epic Intertexts." <em>Intertextuality in Flavian Epic Poetry</em>. Fondation Hardt, Geneva, Switzerland. May 28.</li>
            <li>Coffee, Neil. 2015. "Micro and Macro Literary History: Exploring Intertextuality with Tesserae." Netherlands Institute for Advanced Study, Wassenaar, Netherlands. March 4.</li>
            <li>Gawley, James, Christopher Forstall, and Konnor Clark. 2014. "Automating the Search for Cross-Language Text Reuse." Short paper, <em>Digital Humanities 2014</em>. Lausanne, Switzerland. July 11.</li>
            <li>Scheirer, Walter, and Christopher Forstall. 2014. "Euterpe's Hidden Song: Patterns in Elegy." Poster, <em>Digital Humanities 2014</em>. Lausanne, Switzerland. July 10.</li>
            <li>Coffee, Neil. 2014. Panel participant, "Rethinking Text Reuse as Digital Classicists." <em>Digital Humanities 2014</em>. Lausanne, Switzerland. July 10.</li>
            <li>Coffee, Neil. 2014. "Modeling the Scholars: Detecting Intertextuality through Enhanced Word-Level N-Gram Matching." <em>International Workshop on Computer Aided Processing of Intertextuality in Ancient Languages</em>. INSA Lyon. June 2.</li>
            <li>Gervais, Kyle. 2014. "Flavian Intertextuality: A Digital Approach." 35th ASCS Conference. Auckland, NZ. January.</li>
            <li>Bernstein, Neil, Kyle Gervais, and Wei Lin. 2014. "Comparative Rates of Text Reuse in Latin Epic." <em>APA/AIA Annual Meetings</em>. January 3.</li>
            <li>Coffee, Neil. 2014. "Introduction to Tesserae." <em>Risorse digitali e strumenti collaborativi per le Scienze dell'Antichità</em>. Università Ca' Foscari, Venice, Italy. October 3.</li>
            <li>Coffee, Neil. 2014. "Roses and Lilies: Digital Adventures in Intertextuality." Invited lecture, Cornell University. March 7.</li>
            <li>Coffee, Neil. 2013. "Roses and Lilies: Digital Adventures in Intertextuality." Invited lecture, Yale University. December 5.</li>
            <li>Gawley, James, Christopher Forstall, Konnor Clark, and Amy Miu. 2013. "Two Methods for Discovering Cross-Language Text Reuse." <em>Chicago Colloquium on Digital Humanities & Computer Science</em>. December 5.</li>
            <li>Coffee, Neil, James Gawley, Christopher Forstall, Walter Scheirer, David Johnson, Jason Corso, and Brian Parks. 2013. "Modeling the Interpretation of Literary Allusion with Machine Learning Techniques." Poster, <em>Digital Humanities 2013</em>. University of Nebraska–Lincoln. July 18.</li>
            <li>Coffee, Neil, Christopher Forstall, and James Gawley. 2013. "What is Allusion? A Digital Approach." Poster, <em>Digital Classics Association</em> conference. University at Buffalo. April 5.</li>
            <li>Forstall, Christopher, and Walter J. Scheirer. 2012. "Revealing Hidden Patterns in the Meter of Homer's <em>Iliad</em>." Poster, <em>Chicago Colloquium on Digital Humanities and Computer Science</em>. University of Chicago. November 17–19.</li>
            <li>Gawley, James, Christopher Forstall, and Neil Coffee. 2012. "Evaluating the Literary Significance of Text Re-Use in Latin Poetry." Poster, <em>Chicago Colloquium on Digital Humanities and Computer Science</em>. University of Chicago. November 17–19.</li>
            <li>Coffee, Neil. 2012. "Large- and Small-Scale Intertextuality in Claudian's Historical and Mythical Hexameters." <em>Lucain et Claudien face à face</em>. Fondation Hardt, Geneva, Switzerland. November 8–10.</li>
            <li>Forstall, Christopher. 2012. "Revealing Intertextuality with Tesserae." Workshop, <em>Lucain et Claudien face à face</em>. Fondation Hardt, Geneva, Switzerland. November 8–10.</li>
            <li>Coffee, Neil. 2012. "The Tesserae Project: A Search Engine for Allusion." Roundtable discussion leader, <em>APA Annual Meeting</em>. Philadelphia, PA. January.</li>
            <li>Coffee, Neil, Jean-Pierre Koenig, Shakthi Poornima, Christopher Forstall, Roelant Ossewaarde, and Sarah Jacobson. 2011. "The Tesserae Project: Intertextual Analysis of Latin Poetry." Poster, <em>Digital Humanities 2011</em>. Stanford University. June 19–21.</li>
            <li>Forstall, Christopher, and Walter Scheirer. 2011. "Visualizing Sound as Functional N-Grams in Homeric Greek Poetry." Poster, <em>Digital Humanities 2011</em>. Stanford University. June 19–21.</li>
            <li>Coffee, Neil. 2011. "The Tesserae Project: Intertextual Analysis of Latin Poetry." E-Poetry International Digital Poetry Festival, University at Buffalo. May.</li>
            <li>Forstall, Christopher, and Walter Scheirer. 2010. "A Statistical Stylistic Study of Latin Elegiac Couplets." Poster, <em>Chicago Colloquium on Digital Humanities and Computer Science</em>. November 21–22.</li>
            <li>Coffee, Neil. 2010. "Lucan's Vergil: The Tesserae Project." Digital Humanities Initiative at Buffalo. March.</li>
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
            <li>Audsley, Shellie. 2026. "'aSimMatrix' Dimensions: A Scalable Framework for Benchmarking Intertextual Similarity." <em>Journal of Open Humanities Data</em> 12. <a href="https://doi.org/10.5334/johd.486" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.5334/johd.486</a></li>
            <li>Reichbauer, Sebastian, Shu Okabe, and Alexander Fraser. 2026. "Evaluating Latin and Ancient Greek Sentence Alignment through Parallel Sentence Mining." <em>Proceedings of the 6th International Conference on Natural Language Processing for the Digital Humanities</em>: 106–120. <a href="https://doi.org/10.18653/v1/2026.nlp4dh-1.11" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.18653/v1/2026.nlp4dh-1.11</a></li>
            <li>Golan, Shahar, and Chaya Liebeskind. 2026. "Cite and Seek: Automated Literary Reference Mining at Corpus Scale." <em>IEEE Access</em> 14: 38375–38391. <a href="https://doi.org/10.1109/access.2026.3672034" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1109/access.2026.3672034</a></li>
            <li>Re, Alessandro. 2026. "Applicazioni alle lingue e alle letterature classiche delle tecniche di analisi digitale." <em>Umanistica Digitale</em> 24: 263–288. <a href="https://doi.org/10.60923/issn.2532-8816/22980" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.60923/issn.2532-8816/22980</a></li>
            <li>Ruskov, Martin, Maksim Gavrilkov, Iris Karafillidis, Tomáš Mikulka, and Janusz Szablewski. 2026. "Semi-automatic Identification and Attribution of Biblical Quotations in Old Church Slavonic Texts: Computational Methods in the Project 'BogoSlov'." <em>Scripta & e-Scripta</em> 26: 105–120. <a href="https://doi.org/10.66260/ses2026mr-mg-ik-tm-js" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.66260/ses2026mr-mg-ik-tm-js</a></li>
            <li>Burns, Patrick J. 2026. "Latin Intertext Detection." In <em>The Oxford Handbook of Digital Classical Studies</em>. Oxford University Press, 457–468. <a href="https://doi.org/10.1093/9780197835210.003.0017" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1093/9780197835210.003.0017</a></li>
            <li>de la Selle, Théotime, and Laurence Mellerin. 2026. "Detection and Typology of Psalmic Text Reuses in the New Testament." <em>Religions</em> 17(1): 88. <a href="https://doi.org/10.3390/rel17010088" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.3390/rel17010088</a></li>
            <li>Gong, Ashley, Katy Gero, and Mark Schiefsky. 2025. "Augmented Close Reading for Classical Latin Using BERT for Intertextual Exploration." <em>Proceedings of the 5th International Conference on Natural Language Processing for Digital Humanities</em>.</li>
            <li>Kelly, Tynan. 2025. "Detecting Text Reuse in Historical Arabic Texts: Challenges and Strategies." <em>Journal of Digital Islamicate Research</em> 3(2): 362–395. <a href="https://doi.org/10.1163/27732363-bja00013" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1163/27732363-bja00013</a></li>
            <li>Bolt, Thomas J., Elizabeth D. Adams, Zafeirios Adramerinas, et al. 2025. "Stylometric Criticism of Latin Literature: From Exploratory Data Analysis to Close Reading." <em>TAPA</em> 155(1): 205–250. <a href="https://doi.org/10.1353/apa.2025.a957882" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1353/apa.2025.a957882</a></li>
            <li>McGovern, Hope, Hale Sirin, and Tom Lippincott. 2025. "Characterizing the Effects of Translation on Intertextuality using Multilingual Embedding Spaces." <em>Proceedings of NAACL 2025, Volume 2: Short Papers</em>: 161–167. <a href="https://doi.org/10.18653/v1/2025.naacl-short.14" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.18653/v1/2025.naacl-short.14</a></li>
            <li>Resch, Sascha. 2025. "ImitatioInspector: A Prototype Machine Learning Tool Regarding imitatio Dantis and imitatio Petrarcae." <em>Digital Scholarship in the Humanities</em> 40(3): 871–883. <a href="https://doi.org/10.1093/llc/fqaf049" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1093/llc/fqaf049</a></li>
            <li>Kersten, Markus. 2025. "Stellen lesen." In <em>Grenzen der Künste im digitalen Zeitalter</em>. De Gruyter, 227–260. <a href="https://doi.org/10.1515/9783111398518-012" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1515/9783111398518-012</a></li>
            <li>Dexter, Joseph P., Pramit Chaudhuri, Patrick J. Burns, et al. 2024. "A Database of Intertexts in Valerius Flaccus' <em>Argonautica</em> 1." <em>Journal of Open Humanities Data</em> 10 (1): 14.</li>
            <li>Umphrey, Ray, Jesse Roberts, and Lindsey Roberts. 2024. "Investigating Expert-in-the-Loop LLM Discourse Patterns for Ancient Intertextual Analysis." <em>Proceedings of the 4th International Conference on Natural Language Processing for Digital Humanities</em>: 31–40. <a href="https://doi.org/10.18653/v1/2024.nlp4dh-1.4" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.18653/v1/2024.nlp4dh-1.4</a></li>
            <li>Wang, Jun, Siyu Duan, Binghao Fu, Liangcai Gao, and Qi Su. 2024. "Evol project: a comprehensive online platform for quantitative analysis of ancient literature." <em>Humanities and Social Sciences Communications</em> 11(1). <a href="https://doi.org/10.1057/s41599-024-02763-6" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1057/s41599-024-02763-6</a></li>
            <li>Roe, Glenn. 2024. "Text reuse as cultural practice: intertextuality in the 18th-century digital archive." <em>Digital Enlightenment Studies</em> 2(1). <a href="https://doi.org/10.61147/des.23" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.61147/des.23</a></li>
            <li>Miyagawa, So, Yuki Kyogoku, Yuzuki Tsukagoshi, and Kyoko Amano. 2024. "Exploring Similarity Measures and Intertextuality in Vedic Sanskrit Literature." <em>Proceedings of the 4th International Conference on Natural Language Processing for Digital Humanities</em>: 123–131. <a href="https://doi.org/10.18653/v1/2024.nlp4dh-1.12" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.18653/v1/2024.nlp4dh-1.12</a></li>
            <li>Vanni, Laurent, Hadi Mahmoudi, Dominique Longrée, and Damon Mayaffre. 2024. "Multichannel Convolutional Transformer and Intertextuality: A Latin Case Study." In <em>Studies in Classification, Data Analysis, and Knowledge Organization</em>. Springer, 197–207. <a href="https://doi.org/10.1007/978-3-031-55917-4_16" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1007/978-3-031-55917-4_16</a></li>
            <li>Schropp, Franziska, Thomas E. Konrad, Marie Revellio, and Barbara Feichtinger. 2024. "Towards a differentiated digital-hermeneutic analysis tool for the detection of short quotations using the example of the Church Father Jerome." <em>Digital Humanities Quarterly</em> 18(3). <a href="https://doi.org/10.63744/4tj79yabkksn" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.63744/4tj79yabkksn</a></li>
            <li>Fedchenko, Valentina, Dario Maria Nicolosi, and Glenn Roe. 2024. "À la recherche des réseaux intertextuels : défis de la recherche littéraire à grande échelle." <em>Humanités numériques</em> 9. <a href="https://doi.org/10.4000/11wmw" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.4000/11wmw</a></li>
            <li>Nicolosi, Dario Maria, and Glenn Roe. 2024. "Modelling Enlightenment: reassembling intertextual networks through data-driven research (ModERN)." <em>Digital Enlightenment Studies</em> 2(1). <a href="https://doi.org/10.61147/des.22" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.61147/des.22</a></li>
            <li>Wójcik, Jerzy. 2024. "On Measuring Psalm Similarity: A Case for Word-Level n-Grams." <em>Roczniki Humanistyczne</em> 72(5): 185–208. <a href="https://doi.org/10.18290/rh24725.9s" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.18290/rh24725.9s</a></li>
            <li>O’Rourke, Donncha, and Aaron Pelttari. 2024. "Intertextuality." In <em>The Cambridge Critical Guide to Latin Literature</em>. Cambridge University Press, 208–271. <a href="https://doi.org/10.1017/9781108363303.006" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1017/9781108363303.006</a></li>
            <li>Enslen, Joshua Alma, and Jocelyn R. Bell. 2024. "Minha Terra Tem ____: Patterns of Text Reuse in 'Song of Exile' and its Intertexts." <em>MATLIT: Materialidades da Literatura</em> 10(1): 107–124. <a href="https://doi.org/10.14195/2182-8830_10-1_7" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.14195/2182-8830_10-1_7</a></li>
            <li>Horstmann, Jan, Christian Lück, and Immanuel Normann. 2024. "Systems of Intertextuality: Towards a formalization of text relations for manual annotation and automated reasoning." <em>Digital Humanities Quarterly</em> 17(3). <a href="https://doi.org/10.63744/rt8v39wzhp3z" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.63744/rt8v39wzhp3z</a></li>
            <li>Vasicek, Piper, Courtni Byun, and Kevin Seppi. 2024. "It is a Truth Individually Acknowledged: Cross-references On Demand." <em>Proceedings of the 4th International Conference on Natural Language Processing for Digital Humanities</em>: 63–74. <a href="https://doi.org/10.18653/v1/2024.nlp4dh-1.7" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.18653/v1/2024.nlp4dh-1.7</a></li>
            <li>van den Broek, Pieter. 2024. <em>Narratives in Silius Italicus' Punica</em>. Leiden: Brill. <a href="https://doi.org/10.1163/9789004685833" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1163/9789004685833</a></li>
            <li>Riemenschneider, Frederick, and Anette Frank. 2023. "Graecia capta ferum victorem cepit: Detecting Latin Allusions to Ancient Greek Literature." <em>Proceedings of the Ancient Language Processing Workshop</em>, 30–38.</li>
            <li>Sommerschield, Thea, Yannis Assael, John Pavlopoulos, et al. 2023. "Machine Learning for Ancient Languages: A Survey." <em>Computational Linguistics</em> 49(3): 703–747. <a href="https://doi.org/10.1162/coli_a_00481" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1162/coli_a_00481</a></li>
            <li>Janicki, Maciej. 2023. "Large-scale weighted sequence alignment for the study of intertextuality in Finnic oral folk poetry." <em>Journal of Data Mining & Digital Humanities</em> (NLP4DH special issue). <a href="https://doi.org/10.46298/jdmdh.11390" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.46298/jdmdh.11390</a></li>
            <li>Nagy, Ben, and Janice M. Lee. 2023. "New Light on the Additamentum Aldinum (Silius Italicus, Punica 8.144–223)." <em>Classical Quarterly</em> 73(1): 271–292. <a href="https://doi.org/10.1017/s0009838823000502" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1017/s0009838823000502</a></li>
            <li>Cannizzaro, Francesco. 2023. <em>Sulle orme dell'Iliade: Riflessi dell'eroismo omerico nell'epica d'età flavia</em>. Florence: Società Editrice Fiorentina. <a href="https://doi.org/10.35948/dilef/978-88-6032-690-4" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.35948/dilef/978-88-6032-690-4</a></li>
            <li>Janicki, Maciej, Kati Kallio, and Mari Sarv. 2023. "Exploring Finnic written oral folk poetry through string similarity." <em>Digital Scholarship in the Humanities</em> 38(1): 180–194. <a href="https://doi.org/10.1093/llc/fqac034" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1093/llc/fqac034</a></li>
            <li>Revellio, Marie. 2022. <em>Zitate der Aeneis in den Briefen des Hieronymus: Eine digitale Intertextualitätsanalyse</em>. Berlin: De Gruyter. <a href="https://doi.org/10.1515/9783110760828" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1515/9783110760828</a></li>
            <li>Miyagawa, So. 2022. <em>Shenoute, Besa and the Bible: Digital Text Reuse Analysis of Selected Monastic Writings from Egypt</em>. Dissertation, University of Göttingen. <a href="https://doi.org/10.53846/goediss-9082" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.53846/goediss-9082</a></li>
            <li>Suchecka, Karolina, and Nathalie Gasiglia. 2022. "On Digital Comparative Editions and Textual Similarity Detection Tools: Towards a Hypertextual Cartography of a Rewritten Myth." In <em>Tackling the Toolkit: Plotting Poetry through Computational Literary Studies</em>. Institute of Czech Literature, 167–182. <a href="https://doi.org/10.51305/icl.cz.9788076580336.11" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.51305/icl.cz.9788076580336.11</a></li>
            <li>Burns, Patrick J., James A. Brofos, Kyle Li, Pramit Chaudhuri, and Joseph P. Dexter. 2021. "Profiling of Intertextuality in Latin Literature Using Word Embeddings." <em>Proceedings of NAACL-HLT 2021</em>, 4900–4907.</li>
            <li>Shang, Wenyi, and Ted Underwood. 2021. "Improving Measures of Text Reuse in English Poetry: A TF–IDF Based Method." In <em>Diversity, Divergence, Dialogue (iConference 2021), Lecture Notes in Computer Science</em>. Springer, 469–477. <a href="https://doi.org/10.1007/978-3-030-71292-1_36" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1007/978-3-030-71292-1_36</a></li>
            <li>Suchecka, Karolina, and Nathalie Gasiglia. 2021. "Réécritures d'un mythe et outils de détection des réutilisations. De l'Orphée de Virgile à celui de Ballanche." <em>Humanités numériques</em> 4. <a href="https://doi.org/10.4000/revuehn.2467" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.4000/revuehn.2467</a></li>
            <li>van der Schuur, Marco. 2021. <em>Seneca's Challenge: Genre and Intertextuality in Senecan Tragedy and Statius' Thebaid</em>. Dissertation, University of Groningen. <a href="https://doi.org/10.33612/diss.192829503" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.33612/diss.192829503</a></li>
            <li>Pade, Marriane. 2020. "Imitation and Intertextuality in Humanist Translation." In <em>Philology Then and Now. Proceedings of the Danish Academy in Rome</em>. Academia di Danimarca, 169–186.</li>
            <li>Corbeill, Anthony. 2020. "How Not to Write like Cicero: <em>Pridie quam in exilium iret oratio</em>." <em>Ciceroniana Online</em> IV:1, pp. 17–36.</li>
            <li>Pöckelmann, Marcus, Janis Dähne, Jörg Ritter, and Paul Molitor. 2020. "Fast paraphrase extraction in Ancient Greek literature." <em>it - Information Technology</em> 62(2): 75–89. <a href="https://doi.org/10.1515/itit-2019-0042" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1515/itit-2019-0042</a></li>
            <li>Sansom, Stephen A. 2020. "Typhonic Voices: Sounds of Hesiod and Cosmic War in Lucan's Bellum civile 6.685–694." <em>Mnemosyne</em> 73(4): 609–632. <a href="https://doi.org/10.1163/1568525x-12342683" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1163/1568525x-12342683</a></li>
            <li>Manjavacas, Enrique, Brian Long, and Mike Kestemont. 2019. "On the Feasibility of Automated Detection of Allusive Text Reuse." <em>Proceedings of the 3rd Joint SIGHUM Workshop</em>, 104–114.</li>
            <li>Harris, Martyn, Mark Levene, Dell Zhang, and Dan Levene. 2019. "Comparing 'parallel passages' in digital archives." <em>Journal of Documentation</em> 76(1): 271–289. <a href="https://doi.org/10.1108/jd-10-2018-0175" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1108/jd-10-2018-0175</a></li>
            <li>Yolles, Julian. 2019. "Review: Discovering Intertextual Parallels in Latin and Greek Texts with Tesserae." <em>SCS Blog, Society for Classical Studies</em>, March 24, 2019. <a href="https://classicalstudies.org/scs-blog/2569701/review-discovering-intertextual-parallels-latin-and-greek-tesserae" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">classicalstudies.org</a> (open access)</li>
            <li>Franzini, Greta, Marco Passarotti, Maria Moritz, and Marco Büchler. 2018. "Using and evaluating TRACER for an Index fontium computatus of the Summa contra Gentiles of Thomas Aquinas." In <em>Proceedings of the Fifth Italian Conference on Computational Linguistics (CLiC-it 2018)</em>. Accademia University Press, 199–205. <a href="https://doi.org/10.4000/books.aaccademia.3354" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.4000/books.aaccademia.3354</a></li>
            <li>Sturgeon, Donald. 2018. "Unsupervised identification of text reuse in early Chinese literature." <em>Digital Scholarship in the Humanities</em> 33(3): 670–684. <a href="https://doi.org/10.1093/llc/fqx024" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1093/llc/fqx024</a></li>
            <li>Chaudhuri, Pramit, and Joseph P. Dexter. 2017. "Bioinformatics and Classical Literary Study." <em>Journal of Data Mining & Digital Humanities</em>, Special Issue.</li>
            <li>Nelis, Damien, Christopher Forstall, and Lavinia Galli Milic. 2017. "Intertextuality and Narrative Context: Digital Narratology?" HAL preprint hal-01480773.</li>
            <li>Dexter, Joseph P., Theodore Katz, Nilesh Tripuraneni, et al. 2017. "Quantitative criticism of literary relationships." <em>Proceedings of the National Academy of Sciences</em> 114(16): E3195–E3204. <a href="https://doi.org/10.1073/pnas.1611910114" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.1073/pnas.1611910114</a></li>
            <li>Burns, Patrick. 2016. "Measuring and Mapping Intergeneric Allusion in Latin Poetry Using Tesserae." <em>Journal of Data Mining and Digital Humanities</em>.</li>
            <li>Marmerola, Guilherme D., et al. 2016. "On the Reconstruction of Text Phylogeny Trees: Evaluation and Analysis of Textual Relationships." <em>PLoS ONE</em> 11(12): e0167822.</li>
            <li>Roe, Glenn, Clovis Gladstone, Robert Morrissey, et al. 2016. "Digging into ECCO: Identifying Commonplaces and Other Forms of Text Reuse at Scale." <em>Digital Humanities DH2016</em>. Krakow, Poland, pp. 336–339.</li>
            <li>Jänicke, Stefan, Greta Franzini, Muhammad Faisal Cheema, and Gerik Scheuermann. 2016. "Visual Text Analysis in Digital Humanities." <em>Computer Graphics Forum</em>. June.</li>
            <li>Verhaar, P. A. F. 2016. <em>Affordances and Limitations of Algorithmic Criticism</em>. Ph.D. dissertation, Leiden.</li>
            <li>Duhaime, Douglas Ernest. 2016. "Textual Reuse in the Eighteenth Century: Mining Eliza Haywood's Quotations." <em>Digital Humanities Quarterly</em> 10, no. 1.</li>
            <li>Montoro, Rocío. 2016. "The Year's Work in Stylistics 2015." <em>Language and Literature</em> 25(4): 380.</li>
            <li>Romanello, Matteo. 2016. "Exploring Citation Networks to Study Intertextuality in Classics." <em>Digital Humanities Quarterly</em> 10(2). <a href="https://doi.org/10.63744/623s27b2w6hp" className="text-amber-600 hover:underline" target="_blank" rel="noopener noreferrer">https://doi.org/10.63744/623s27b2w6hp</a></li>
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
