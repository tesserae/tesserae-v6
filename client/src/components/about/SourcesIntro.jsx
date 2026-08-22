// Shared "text sources" prose paragraph, rendered at the end of the About page
// (Creation & Credits) and reusable elsewhere. Keeps the source hyperlinks intact.

const SOURCE_LINKS = {
  'The Latin Library': 'http://thelatinlibrary.com/',
  'The Perseus Project': 'http://www.perseus.tufts.edu/',
  'DigilibLT': 'https://digiliblt.uniupo.it/',
  'Open Greek and Latin Project': 'https://opengreekandlatin.org/',
  'Musisque Deoque': 'http://www.mqdq.it/',
  'Corpus Scriptorum Latinorum': 'https://web.archive.org/web/20220305141011/http://www.forumromanum.org/literature/index.html',
  'The Greek New Testament: SBL Edition': 'https://sblgnt.com',
  'Society of Biblical Literature': 'http://sbl-site.org',
  'Logos Bible Software': 'http://logos.com',
  'Coptic Scriptorium': 'https://copticscriptorium.org/',
  'Sefaria': 'https://www.sefaria.org/',
  'Miqra according to the Masorah': 'https://he.wikisource.org/wiki/%D7%9E%D7%A9%D7%AA%D7%9E%D7%A9:Dovi/%D7%9E%D7%A7%D7%A8%D7%90_%D7%A2%D7%9C_%D7%A4%D7%99_%D7%94%D7%9E%D7%A1%D7%95%D7%A8%D7%94',
  'BHSA': 'https://etcbc.github.io/bhsa/',
  'MiqraBERT': 'https://huggingface.co/davidmsmiley/MiqraBERT',
  'OpenBible.info': 'https://www.openbible.info/labs/cross-references/',
  'CATSS': 'https://ccat.sas.upenn.edu/rak/catss.html',
};

function IntroLink({ name, url }) {
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline font-medium">
      {name}
    </a>
  );
}

export default function SourcesIntro() {
  return (
    <p className="text-gray-700 leading-relaxed">
      The texts used in this project were gathered from many electronic text databases. Latin and Greek
      texts come from{' '}
      <IntroLink name="The Latin Library" url={SOURCE_LINKS['The Latin Library']} />,{' '}
      <IntroLink name="The Perseus Project" url={SOURCE_LINKS['The Perseus Project']} />,{' '}
      <IntroLink name="DigilibLT" url={SOURCE_LINKS['DigilibLT']} />,{' '}
      <IntroLink name="Open Greek and Latin Project" url={SOURCE_LINKS['Open Greek and Latin Project']} />,{' '}
      <IntroLink name="Musisque Deoque" url={SOURCE_LINKS['Musisque Deoque']} />, and{' '}
      <IntroLink name="Corpus Scriptorum Latinorum" url={SOURCE_LINKS['Corpus Scriptorum Latinorum']} />.
      {' '}The Greek New Testament is{' '}
      <IntroLink name="The Greek New Testament: SBL Edition" url={SOURCE_LINKS['The Greek New Testament: SBL Edition']} />{' '}
      (SBLGNT), edited by Michael W. Holmes, ©2010{' '}
      <IntroLink name="Society of Biblical Literature" url={SOURCE_LINKS['Society of Biblical Literature']} /> and{' '}
      <IntroLink name="Logos Bible Software" url={SOURCE_LINKS['Logos Bible Software']} />, used by permission
      under the SBLGNT End User License Agreement.
      {' '}Coptic texts (Sahidic and Bohairic) come from{' '}
      <IntroLink name="Coptic Scriptorium" url={SOURCE_LINKS['Coptic Scriptorium']} /> (CC-BY 4.0; the
      Sahidica New Testament is additionally subject to its own academic-use license, ©2000–2006
      J. Warren Wells). The Hebrew Bible text is the{' '}
      <IntroLink name="Miqra according to the Masorah" url={SOURCE_LINKS['Miqra according to the Masorah']} />{' '}
      (MAM) edition, based on the Aleppo Codex, obtained through{' '}
      <IntroLink name="Sefaria" url={SOURCE_LINKS['Sefaria']} /> (CC-BY-SA); Hebrew morphological
      lemmatization draws on the <IntroLink name="ETCBC/BHSA" url={SOURCE_LINKS['BHSA']} /> dataset
      (Biblia Hebraica Stuttgartensia Amstelodamensis; CC-BY-NC 4.0, DOI 10.17026/dans-z6y-skyh)
      via Text-Fabric. The Hebrew semantic channel uses{' '}
      <IntroLink name="MiqraBERT" url={SOURCE_LINKS['MiqraBERT']} /> (D. M. Smiley), fine-tuned
      in-house on <IntroLink name="OpenBible.info" url={SOURCE_LINKS['OpenBible.info']} /> cross-references
      (CC-BY, from the Treasury of Scripture Knowledge); Hebrew-to-Greek Septuagint matching uses the{' '}
      <IntroLink name="CATSS" url={SOURCE_LINKS['CATSS']} /> Masoretic-Septuagint parallel (E. Tov),
      bridged through Greek to the Latin Vulgate for Hebrew-to-Latin matching.
      {' '}We have modified the texts by changing the markup, and may have made superficial changes to
      orthography. During our searches, all punctuation and capitalization are removed.
    </p>
  );
}
