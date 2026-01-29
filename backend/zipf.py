"""
Tesserae V6 - Zipf Distribution Analysis
Finds the elbow in word frequency distribution for automatic stoplist cutoff
"""
from collections import Counter
import math

def find_zipf_elbow(freq_counter, min_stopwords=10, max_stopwords=100):
    """
    Find the elbow point in a Zipf frequency distribution.
    
    Uses the "maximum curvature" method:
    1. Sort words by frequency (descending)
    2. Plot log(rank) vs log(frequency)
    3. Find the point of maximum curvature (elbow)
    
    Returns: set of stopwords (words before the elbow)
    """
    if not freq_counter:
        return set()
    
    sorted_words = freq_counter.most_common()
    
    if len(sorted_words) < min_stopwords:
        return set(w for w, _ in sorted_words)
    
    log_ranks = []
    log_freqs = []
    
    for rank, (word, freq) in enumerate(sorted_words, 1):
        if freq > 0:
            log_ranks.append(math.log(rank))
            log_freqs.append(math.log(freq))
    
    if len(log_ranks) < 3:
        return set(w for w, _ in sorted_words[:min_stopwords])
    
    start_point = (log_ranks[0], log_freqs[0])
    end_idx = min(len(log_ranks) - 1, max_stopwords * 2)
    end_point = (log_ranks[end_idx], log_freqs[end_idx])
    
    line_vec = (end_point[0] - start_point[0], end_point[1] - start_point[1])
    line_len = math.sqrt(line_vec[0]**2 + line_vec[1]**2)
    
    if line_len == 0:
        return set(w for w, _ in sorted_words[:min_stopwords])
    
    line_unit = (line_vec[0] / line_len, line_vec[1] / line_len)
    
    max_distance = 0
    elbow_idx = min_stopwords
    
    for i in range(min_stopwords, min(end_idx, max_stopwords)):
        point = (log_ranks[i], log_freqs[i])
        
        point_vec = (point[0] - start_point[0], point[1] - start_point[1])
        
        proj_length = point_vec[0] * line_unit[0] + point_vec[1] * line_unit[1]
        proj_point = (start_point[0] + proj_length * line_unit[0],
                     start_point[1] + proj_length * line_unit[1])
        
        distance = math.sqrt((point[0] - proj_point[0])**2 + 
                           (point[1] - proj_point[1])**2)
        
        if distance > max_distance:
            max_distance = distance
            elbow_idx = i
    
    elbow_idx = max(min_stopwords, min(elbow_idx, max_stopwords))
    
    stopwords = set(word for word, _ in sorted_words[:elbow_idx])
    
    return stopwords

def analyze_frequency_distribution(units):
    """
    Analyze the frequency distribution of lemmas in text units.
    Returns frequency counter and distribution stats.
    """
    all_lemmas = []
    for unit in units:
        all_lemmas.extend(unit['lemmas'])
    
    freq = Counter(all_lemmas)
    
    sorted_freqs = [f for _, f in freq.most_common()]
    
    if not sorted_freqs:
        return freq, {}
    
    stats = {
        'total_tokens': len(all_lemmas),
        'unique_lemmas': len(freq),
        'max_frequency': sorted_freqs[0] if sorted_freqs else 0,
        'median_frequency': sorted_freqs[len(sorted_freqs)//2] if sorted_freqs else 0,
        'top_10': freq.most_common(10)
    }
    
    return freq, stats
