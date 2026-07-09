"""
Syntax Parser for Universal Dependencies Treebanks
Parses CoNLL-U format and provides syntactic similarity matching
Uses text-based matching to link treebank sentences to Tesserae results
Falls back to Stanza for on-the-fly parsing when treebank data unavailable
"""
import os
import re
import json
import hashlib
import sqlite3
from collections import defaultdict

DEPREL_CATEGORIES = {
    'core': ['nsubj', 'obj', 'iobj', 'csubj', 'ccomp', 'xcomp'],
    'non_core': ['obl', 'vocative', 'expl', 'dislocated'],
    'nominal': ['nmod', 'appos', 'nummod', 'amod', 'acl', 'det', 'case'],
    'coordination': ['conj', 'cc'],
    'mwe': ['fixed', 'flat', 'compound'],
    'loose': ['list', 'parataxis', 'orphan', 'goeswith', 'reparandum'],
    'special': ['punct', 'root', 'dep'],
    'modifier': ['advmod', 'discourse', 'aux', 'cop', 'mark', 'advcl'],
}

def get_deprel_category(deprel):
    """Map a UD dependency relation to its broad category (core, nominal, modifier, etc.)."""
    base_rel = deprel.split(':')[0] if ':' in deprel else deprel
    for category, rels in DEPREL_CATEGORIES.items():
        if base_rel in rels:
            return category
    return 'other'

def normalize_text_for_lookup(text):
    """Normalize text for treebank sentence lookup: lowercase, strip punctuation, collapse whitespace."""
    if not text:
        return ''
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = ' '.join(text.split())
    return text


class SyntaxToken:
    """A single token from a CoNLL-U parsed sentence with UD annotations."""

    def __init__(self, id, form, lemma, upos, xpos, feats, head, deprel, deps, misc):
        """Store CoNLL-U fields: word form, lemma, POS tags, features, dependency head/relation."""
        self.id = id
        self.form = form
        self.lemma = lemma.lower() if lemma else ''
        self.upos = upos
        self.xpos = xpos
        self.feats = self._parse_feats(feats)
        self.head = int(head) if head and head != '_' else 0
        self.deprel = deprel if deprel != '_' else ''
        self.deps = deps
        self.misc = misc
        
    def _parse_feats(self, feats_str):
        """Parse CoNLL-U feature string ('Case=Nom|Number=Sing') into a dict."""
        if not feats_str or feats_str == '_':
            return {}
        result = {}
        for pair in feats_str.split('|'):
            if '=' in pair:
                key, val = pair.split('=', 1)
                result[key] = val
        return result


class SyntaxSentence:
    """A parsed sentence with its tokens, dependency pattern, and role-extraction methods."""

    def __init__(self, sent_id, text, tokens):
        """Initialize with sentence ID, raw text, and list of SyntaxToken objects."""
        self.sent_id = sent_id
        self.text = text
        self.normalized_text = normalize_text_for_lookup(text)
        self.tokens = tokens
        self._dependency_pattern = None
        
    @property
    def dependency_pattern(self):
        """Lazy-computed tuple of (UPOS, deprel, category) for non-punctuation tokens."""
        if self._dependency_pattern is None:
            self._dependency_pattern = self._compute_pattern()
        return self._dependency_pattern
    
    def _compute_pattern(self):
        """Build the dependency pattern tuple from non-punctuation tokens."""
        pattern = []
        for tok in self.tokens:
            if tok.upos not in ['PUNCT']:
                pattern.append((tok.upos, tok.deprel, get_deprel_category(tok.deprel)))
        return tuple(pattern)
    
    def get_lemma_roles(self):
        """Return dict mapping each lemma to its syntactic role (deprel, category, UPOS, feats)."""
        roles = {}
        for tok in self.tokens:
            if tok.lemma and tok.upos not in ['PUNCT', 'X']:
                roles[tok.lemma] = {
                    'deprel': tok.deprel,
                    'category': get_deprel_category(tok.deprel),
                    'upos': tok.upos,
                    'feats': tok.feats
                }
        return roles
    
    def get_all_word_roles(self):
        """Get syntactic roles for ALL words (surface forms), not just lemmas."""
        roles = {}
        for tok in self.tokens:
            if tok.form and tok.upos not in ['PUNCT', 'X']:
                # Use lowercase form for matching
                word = tok.form.lower()
                roles[word] = {
                    'deprel': tok.deprel,
                    'category': get_deprel_category(tok.deprel),
                    'upos': tok.upos,
                    'lemma': tok.lemma
                }
        return roles
    
    def get_roles_set(self):
        """Get the set of all syntactic roles in this sentence."""
        return {tok.deprel for tok in self.tokens if tok.upos not in ['PUNCT', 'X']}
    
    def get_structure_signature(self):
        """Return sorted tuple of core dependency relations (nsubj, obj, etc.) as a structural fingerprint."""
        core_deps = []
        for tok in self.tokens:
            cat = get_deprel_category(tok.deprel)
            if cat == 'core':
                core_deps.append(tok.deprel)
        return tuple(sorted(core_deps))


class SyntaxIndex:
    """Index of parsed sentences for fast lookup by normalized text or content words."""

    def __init__(self):
        self.sentences_by_text = {}
        self.sentences_by_words = defaultdict(list)
        
    def add_sentence(self, sentence):
        """Add a sentence to both the exact-text and word-based lookup indexes."""
        if sentence.normalized_text:
            self.sentences_by_text[sentence.normalized_text] = sentence
            
            words = sentence.normalized_text.split()
            for word in words:
                if len(word) >= 4:
                    self.sentences_by_words[word].append(sentence)
        
    def find_sentence(self, text):
        """Find a matching sentence by exact text or fuzzy word overlap (>50% Jaccard)."""
        normalized = normalize_text_for_lookup(text)
        
        if normalized in self.sentences_by_text:
            return self.sentences_by_text[normalized]
        
        words = normalized.split()
        content_words = [w for w in words if len(w) >= 4]
        
        if not content_words:
            return None
        
        candidate_counts = defaultdict(int)
        candidate_sents = {}
        
        for word in content_words:
            for sent in self.sentences_by_words.get(word, []):
                sent_id = id(sent)
                candidate_counts[sent_id] += 1
                candidate_sents[sent_id] = sent
        
        if candidate_counts:
            best_id = max(candidate_counts.keys(), key=lambda x: candidate_counts[x])
            best_count = candidate_counts[best_id]
            best_sent = candidate_sents[best_id]
            
            if best_count >= min(3, len(content_words)):
                sent_words = set(best_sent.normalized_text.split())
                text_words = set(normalized.split())
                overlap = len(sent_words & text_words)
                if overlap / max(len(sent_words), len(text_words)) > 0.5:
                    return best_sent
        
        return None
    
    def __len__(self):
        """Return the number of indexed sentences."""
        return len(self.sentences_by_text)


def parse_conllu_file(filepath):
    """Parse a CoNLL-U file into a list of SyntaxSentence objects."""
    sentences = []
    current_sent_id = None
    current_text = None
    current_tokens = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            if line.startswith('# sent_id'):
                if current_sent_id and current_tokens:
                    sentences.append(SyntaxSentence(current_sent_id, current_text or '', current_tokens))
                current_sent_id = line.split('=', 1)[1].strip() if '=' in line else None
                current_tokens = []
                current_text = None
                
            elif line.startswith('# text ='):
                current_text = line.split('=', 1)[1].strip()
                
            elif line.startswith('#'):
                continue
                
            elif line == '':
                if current_sent_id and current_tokens:
                    sentences.append(SyntaxSentence(current_sent_id, current_text or '', current_tokens))
                    current_sent_id = None
                    current_tokens = []
                    current_text = None
                    
            else:
                parts = line.split('\t')
                if len(parts) >= 10:
                    tok_id = parts[0]
                    if '-' in tok_id or '.' in tok_id:
                        continue
                    try:
                        token = SyntaxToken(
                            id=int(tok_id),
                            form=parts[1],
                            lemma=parts[2],
                            upos=parts[3],
                            xpos=parts[4],
                            feats=parts[5],
                            head=parts[6],
                            deprel=parts[7],
                            deps=parts[8],
                            misc=parts[9]
                        )
                        current_tokens.append(token)
                    except (ValueError, IndexError):
                        continue
    
    if current_sent_id and current_tokens:
        sentences.append(SyntaxSentence(current_sent_id, current_text or '', current_tokens))
        
    return sentences


EQUIVALENT_DEPRELS = {
    'case': 'case/mark',
    'mark': 'case/mark',
    'nsubj': 'subject',
    'nsubj:pass': 'subject',
    'csubj': 'subject',
    'obj': 'object',
    'iobj': 'object',
    'obl': 'oblique',
    'obl:arg': 'oblique',
    'acl': 'clause',
    'acl:relcl': 'clause',
    'advcl': 'clause',
}

def normalize_deprel(deprel):
    """Normalize dependency relation for comparison"""
    return EQUIVALENT_DEPRELS.get(deprel, deprel)

def features_match(feats1, feats2):
    """Check if morphological features match (case, number, gender for nouns/adj)"""
    if not feats1 or not feats2:
        return False
    # Key features for Latin/Greek syntax
    key_features = ['Case', 'Number', 'Gender', 'Tense', 'Voice', 'Mood']
    matches = 0
    comparisons = 0
    for feat in key_features:
        if feat in feats1 and feat in feats2:
            comparisons += 1
            if feats1[feat] == feats2[feat]:
                matches += 1
    # If we compared at least 2 features and most match, features agree
    return comparisons >= 2 and matches >= comparisons - 1

def compute_syntax_similarity(sent1, sent2, matched_lemmas=None):
    """Score syntactic similarity (0.0–1.0) based on shared lemma roles and structural overlap."""
    if not sent1 or not sent2:
        return 0.0
    
    roles1 = sent1.get_lemma_roles()
    roles2 = sent2.get_lemma_roles()
    
    if matched_lemmas:
        matching_lemmas = [l for l in matched_lemmas if l in roles1 and l in roles2]
    else:
        matching_lemmas = list(set(roles1.keys()) & set(roles2.keys()))
    
    if not matching_lemmas:
        return 0.0
    
    score = 0.0
    max_score = 0.0
    
    for lemma in matching_lemmas:
        role1 = roles1[lemma]
        role2 = roles2[lemma]
        max_score += 1.0
        
        deprel1 = role1['deprel']
        deprel2 = role2['deprel']
        feats1 = role1.get('feats', {})
        feats2 = role2.get('feats', {})
        
        # Same dependency relation = full match
        if deprel1 == deprel2:
            score += 1.0
        # Same normalized relation (case/mark, nsubj/csubj, etc.)
        elif normalize_deprel(deprel1) == normalize_deprel(deprel2):
            score += 0.95
        # MORPHOLOGICAL AGREEMENT: same lemma + same features = syntactically parallel
        # This handles cases like "clauso" in ablative in both texts but with different heads
        elif features_match(feats1, feats2):
            score += 0.9
        elif role1['category'] == role2['category']:
            score += 0.7
        elif role1['upos'] == role2['upos']:
            score += 0.4
    
    sig1 = sent1.get_structure_signature()
    sig2 = sent2.get_structure_signature()
    
    if sig1 and sig2:
        overlap = len(set(sig1) & set(sig2))
        union = len(set(sig1) | set(sig2))
        if union > 0:
            struct_sim = overlap / union
            score += struct_sim * 0.5
            max_score += 0.5
    
    return score / max_score if max_score > 0 else 0.0


class StanzaParser:
    """On-the-fly parser using Stanza for texts not in treebanks"""
    
    def __init__(self, cache_dir=None):
        """Initialize with optional cache directory for persisting Stanza parse results."""
        self.pipelines = {}
        self.cache = {}
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'data', 'syntax_cache'
        )
        self._load_cache()
        
    def _load_cache(self):
        """Load cached parses from disk"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
            return
            
        cache_file = os.path.join(self.cache_dir, 'syntax_cache.json')
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                print(f"Loaded {len(self.cache)} cached syntax parses")
            except Exception as e:
                print(f"Error loading syntax cache: {e}")
                self.cache = {}
    
    def _save_cache(self):
        """Save cached parses to disk"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
            
        cache_file = os.path.join(self.cache_dir, 'syntax_cache.json')
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f)
        except Exception as e:
            print(f"Error saving syntax cache: {e}")
    
    def _get_cache_key(self, text, language):
        """Generate cache key from text and language"""
        normalized = normalize_text_for_lookup(text)
        return hashlib.md5(f"{language}:{normalized}".encode()).hexdigest()  # nosec B324
    
    def _get_pipeline(self, language):
        """Get or create Stanza pipeline for language"""
        if language not in self.pipelines:
            try:
                import stanza
                lang_code = 'grc' if language == 'grc' else 'la'
                stanza.download(lang_code, verbose=False)
                self.pipelines[language] = stanza.Pipeline(
                    lang_code, 
                    processors='tokenize,pos,lemma,depparse',
                    verbose=False,
                    use_gpu=False
                )
                print(f"Stanza {lang_code} pipeline loaded")
            except Exception as e:
                print(f"Error loading Stanza pipeline for {language}: {e}")
                self.pipelines[language] = None
        return self.pipelines[language]
    
    def parse(self, text, language):
        """Parse text and return SyntaxSentence"""
        if not text or not text.strip():
            return None
            
        cache_key = self._get_cache_key(text, language)
        
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            tokens = [
                SyntaxToken(
                    id=t['id'],
                    form=t['form'],
                    lemma=t['lemma'],
                    upos=t['upos'],
                    xpos=t.get('xpos', '_'),
                    feats=t.get('feats', '_'),
                    head=t['head'],
                    deprel=t['deprel'],
                    deps='_',
                    misc='_'
                )
                for t in cached['tokens']
            ]
            return SyntaxSentence(cache_key, text, tokens)
        
        pipeline = self._get_pipeline(language)
        if not pipeline:
            return None
            
        try:
            doc = pipeline(text)
            
            if not doc.sentences:
                return None
                
            tokens = []
            token_data = []
            
            for sent in doc.sentences:
                for word in sent.words:
                    token = SyntaxToken(
                        id=word.id,
                        form=word.text,
                        lemma=word.lemma or word.text,
                        upos=word.upos or 'X',
                        xpos=word.xpos or '_',
                        feats=word.feats or '_',
                        head=word.head,
                        deprel=word.deprel or 'dep',
                        deps='_',
                        misc='_'
                    )
                    tokens.append(token)
                    token_data.append({
                        'id': word.id,
                        'form': word.text,
                        'lemma': word.lemma or word.text,
                        'upos': word.upos or 'X',
                        'xpos': word.xpos or '_',
                        'feats': word.feats or '_',
                        'head': word.head,
                        'deprel': word.deprel or 'dep'
                    })
            
            self.cache[cache_key] = {'tokens': token_data}
            
            if len(self.cache) % 100 == 0:
                self._save_cache()
                
            return SyntaxSentence(cache_key, text, tokens)
            
        except Exception as e:
            print(f"Stanza parse error: {e}")
            return None
    
    def save(self):
        """Explicitly save cache to disk"""
        self._save_cache()


class SyntaxMatcher:
    """Main interface for syntax-based matching. Loads UD treebanks and scores sentence pairs."""

    def __init__(self, treebank_dir=None):
        """Initialize with per-language SyntaxIndex objects and optional treebank directory."""
        self.index = {'la': SyntaxIndex(), 'grc': SyntaxIndex(), 'en': SyntaxIndex()}
        self.loaded = False
        self.treebank_dir = treebank_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'data', 'treebanks'
        )
        self.stanza_parser = None
        self._db_parse_cache = {}

    def _get_syntax_db_path(self, language):
        """Return the syntax DB path for a supported language, if any."""
        base_dir = os.path.dirname(os.path.dirname(__file__))
        if language == 'la':
            return os.path.join(base_dir, 'data', 'inverted_index', 'syntax_latin.db')
        if language == 'grc':
            return os.path.join(base_dir, 'data', 'inverted_index', 'syntax_greek.db')
        return None

    def _load_db_syntax_for_text(self, db_path, text_filename):
        """Load syntax parses for one text from the syntax DB."""
        cache_key = (db_path, text_filename)
        if cache_key in self._db_parse_cache:
            return self._db_parse_cache[cache_key]

        if not db_path or not os.path.exists(db_path):
            return {}

        try:
            conn = sqlite3.connect(db_path, timeout=5)
        except sqlite3.OperationalError:
            uri = f"file:{db_path}?mode=ro&immutable=1"
            conn = sqlite3.connect(uri, uri=True)

        cur = conn.cursor()
        try:
            cur.execute("SELECT text_id FROM texts WHERE filename = ?", (text_filename,))
        except sqlite3.OperationalError:
            conn.close()
            uri = f"file:{db_path}?mode=ro&immutable=1"
            conn = sqlite3.connect(uri, uri=True)
            cur = conn.cursor()
            cur.execute("SELECT text_id FROM texts WHERE filename = ?", (text_filename,))

        row = cur.fetchone()
        if not row:
            conn.close()
            return {}

        text_id = row[0]
        cur.execute(
            "SELECT ref, tokens, lemmas, upos, heads, deprels, feats "
            "FROM syntax WHERE text_id = ?",
            (text_id,),
        )

        parses = {}
        for ref, tokens, lemmas, upos, heads, deprels, feats in cur.fetchall():
            parses[ref] = {
                'tokens': json.loads(tokens) if tokens else [],
                'lemmas': json.loads(lemmas) if lemmas else [],
                'upos': json.loads(upos) if upos else [],
                'heads': json.loads(heads) if heads else [],
                'deprels': json.loads(deprels) if deprels else [],
                'feats': json.loads(feats) if feats else [],
            }

        conn.close()
        self._db_parse_cache[cache_key] = parses
        return parses

    def _expand_ref_candidates(self, ref, line_refs=None):
        """Expand a unit ref into candidate line refs for syntax DB lookup."""
        candidates = []
        if line_refs:
            candidates.extend(r for r in line_refs if r)
        if ref:
            candidates.append(ref)
            if '-' in ref:
                left, right = ref.split('-', 1)
                if left:
                    candidates.append(left)
                if right:
                    candidates.append(right)

        seen = set()
        ordered = []
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                ordered.append(candidate)
        return ordered

    def _stringify_feats(self, feats):
        """Convert DB-stored features into CoNLL-U-style feature strings."""
        if isinstance(feats, dict):
            if not feats:
                return '_'
            return '|'.join(f'{k}={v}' for k, v in sorted(feats.items()))
        if isinstance(feats, list):
            if not feats:
                return '_'
            if all(isinstance(item, str) for item in feats):
                return '|'.join(item for item in feats if item) or '_'
        if isinstance(feats, str):
            return feats or '_'
        return '_'

    def _build_sentence_from_db_parse(self, ref, parse_data):
        """Build a SyntaxSentence from one syntax DB row."""
        tokens = parse_data.get('tokens', [])
        lemmas = parse_data.get('lemmas', [])
        upos = parse_data.get('upos', [])
        heads = parse_data.get('heads', [])
        deprels = parse_data.get('deprels', [])
        feats_list = parse_data.get('feats', [])

        syntax_tokens = []
        for i, form in enumerate(tokens):
            lemma = lemmas[i] if i < len(lemmas) else form
            upos_tag = upos[i] if i < len(upos) else ''
            head = heads[i] if i < len(heads) else 0
            deprel = deprels[i] if i < len(deprels) else ''
            feats = feats_list[i] if i < len(feats_list) else '_'
            syntax_tokens.append(SyntaxToken(
                id=i + 1,
                form=form,
                lemma=lemma,
                upos=upos_tag,
                xpos='_',
                feats=self._stringify_feats(feats),
                head=head,
                deprel=deprel,
                deps='_',
                misc='_',
            ))

        return SyntaxSentence(ref, ' '.join(tokens), syntax_tokens)

    def get_syntax_score_by_ref(self, source_id, source_ref, target_id, target_ref,
                                language, matched_lemmas=None,
                                source_line_refs=None, target_line_refs=None):
        """Get syntax similarity from syntax DB rows using text filename + line refs."""
        db_path = self._get_syntax_db_path(language)
        if not db_path:
            return 0.0, None, None, False

        source_parses = self._load_db_syntax_for_text(db_path, source_id)
        target_parses = self._load_db_syntax_for_text(db_path, target_id)
        if not source_parses or not target_parses:
            return 0.0, None, None, False

        source_candidates = [
            ref for ref in self._expand_ref_candidates(source_ref, source_line_refs)
            if ref in source_parses
        ]
        target_candidates = [
            ref for ref in self._expand_ref_candidates(target_ref, target_line_refs)
            if ref in target_parses
        ]
        if not source_candidates or not target_candidates:
            return 0.0, None, None, False

        best_score = 0.0
        best_source = None
        best_target = None

        for src_candidate in source_candidates:
            src_sent = self._build_sentence_from_db_parse(src_candidate, source_parses[src_candidate])
            for tgt_candidate in target_candidates:
                tgt_sent = self._build_sentence_from_db_parse(tgt_candidate, target_parses[tgt_candidate])
                score = compute_syntax_similarity(src_sent, tgt_sent, matched_lemmas)
                if score > best_score:
                    best_score = score
                    best_source = src_sent
                    best_target = tgt_sent

        return best_score, best_source, best_target, True
        
    def load_treebanks(self):
        """Load all UD treebank .conllu files for Latin, Greek, and English into the index."""
        if self.loaded:
            return
            
        treebank_paths = {
            'la': [
                'UD_Latin-Perseus',
                'UD_Latin-PROIEL',
            ],
            'grc': [
                'UD_Ancient_Greek-Perseus',
                'UD_Ancient_Greek-PROIEL',
            ],
            'en': [
                'UD_English-EWT',
                'UD_English-GUM',
            ]
        }
        
        for lang, dirs in treebank_paths.items():
            for tb_dir in dirs:
                full_path = os.path.join(self.treebank_dir, tb_dir)
                if not os.path.exists(full_path):
                    continue
                    
                for filename in os.listdir(full_path):
                    if filename.endswith('.conllu'):
                        filepath = os.path.join(full_path, filename)
                        try:
                            sentences = parse_conllu_file(filepath)
                            for sent in sentences:
                                if sent.text:
                                    self.index[lang].add_sentence(sent)
                        except Exception as e:
                            print(f"Error parsing {filepath}: {e}")
                            
        self.loaded = True
        print(f"Syntax treebanks loaded: {len(self.index['la'])} Latin, {len(self.index['grc'])} Greek, {len(self.index['en'])} English sentences")
    
    def _get_stanza_parser(self):
        """Lazy load Stanza parser"""
        if self.stanza_parser is None:
            self.stanza_parser = StanzaParser()
        return self.stanza_parser
        
    def get_syntax_score(self, source_text, target_text, language, matched_lemmas=None, treebank_only=True):
        """
        Get syntax similarity score between two texts.
        
        Args:
            treebank_only: If True, only return scores when BOTH texts have verified treebank data.
                          This avoids unreliable Stanza parses for classical poetry.
        """
        if not self.loaded:
            self.load_treebanks()
        
        lang_key = language if language in ('la', 'grc', 'en') else 'la'
        
        # Try to find in verified treebank data first
        sent1 = self.index[lang_key].find_sentence(source_text)
        sent2 = self.index[lang_key].find_sentence(target_text)
        
        # Track whether we have treebank data for both
        sent1_from_treebank = sent1 is not None
        sent2_from_treebank = sent2 is not None
        
        if treebank_only:
            # Only score if BOTH have treebank data - Stanza is unreliable for classical poetry
            if not sent1_from_treebank or not sent2_from_treebank:
                return 0.0, None, None, False  # False = not from treebank
        else:
            # Fallback to Stanza (unreliable, kept for backwards compatibility)
            if not sent1 or not sent2:
                parser = self._get_stanza_parser()
                if not sent1:
                    sent1 = parser.parse(source_text, lang_key)
                if not sent2:
                    sent2 = parser.parse(target_text, lang_key)
        
        if not sent1 or not sent2:
            return 0.0, None, None, False
            
        score = compute_syntax_similarity(sent1, sent2, matched_lemmas)
        from_treebank = sent1_from_treebank and sent2_from_treebank
        return score, sent1, sent2, from_treebank
    
    def get_sentence_info(self, text, language):
        """Return structural info (roles, signature) for a sentence, using treebank or Stanza fallback."""
        if not self.loaded:
            self.load_treebanks()
        
        lang_key = language if language in ('la', 'grc', 'en') else 'la'
        sent = self.index[lang_key].find_sentence(text)
        
        if not sent:
            parser = self._get_stanza_parser()
            sent = parser.parse(text, lang_key)
        
        if not sent:
            return None
            
        return {
            'text': sent.text,
            'structure': list(sent.get_structure_signature()),
            'roles': sent.get_lemma_roles()
        }
    
    def save_cache(self):
        """Save Stanza parse cache"""
        if self.stanza_parser:
            self.stanza_parser.save()


syntax_matcher = SyntaxMatcher()


def get_syntax_matcher():
    """Return the module-level SyntaxMatcher singleton."""
    return syntax_matcher
