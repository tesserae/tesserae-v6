import useCollections from './useCollections';
import { DOCUMENT_COLLECTIONS } from '../collections/collectionsConfig';

/**
 * Whether the documents collection (inscriptions and papyri) is on for this
 * visitor. Kept under its old name for existing callers; the answer now
 * comes from Collections, where ?documents=1 still switches it on for the
 * visit. It does not check the SERVER switch (`documents_enabled` from
 * /api/languages) -- callers that need that fetch it themselves.
 */
export default function useDocumentsTrial() {
  return useCollections().anyOn(DOCUMENT_COLLECTIONS);
}
