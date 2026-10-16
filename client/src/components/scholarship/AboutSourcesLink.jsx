/**
 * The small "About these sources" link shown at the head of every place the
 * site lists scholarship. It opens the page /scholarship-sources at the
 * section that explains what is shown there: commentaries, journals, online
 * or methods.
 */
export const SOURCES_PATH = '/scholarship-sources';

export default function AboutSourcesLink({ anchor = 'methods', className = '' }) {
  return (
    <a
      href={`${SOURCES_PATH}#${anchor}`}
      className={`text-[11px] text-red-700 hover:underline ${className}`}
      data-testid="about-these-sources"
    >
      About these sources
    </a>
  );
}
