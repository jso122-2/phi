# reservoir-maths (database export)

*Source: Notion — reservoir-maths database*
*Rows: 5 · all `status: active` · last_updated 2026-09-02*

Schema: `title`, `domain` (relevance / drift / traversal / resonance / valence), `equation`, `variables`, `inputs`, `output`, `python`, `sql`, `depends_on`, `status`, `last_updated`.

---

## 1. relevance :: a = |p - f/v| * x

**Domain:** relevance · **Depends on:** valence_multiplier, tfidf_cosine

**Equation**

```
a = |p - f/v| * x
```

**Variables**

- `p` = semantic match (TF-IDF cosine, 0.0–1.0)
- `f` = friction = 1 − p
- `v` = valence multiplier: same register = 2.0, adjacent = 1.0, distant = 0.5
- `x` = retrieval cost: position/total entries, range 0.1–1.0, deeper entries weighted higher
- `a` = relevance score (output). Lower = more relevant.

**Inputs**

- `p: float 0-1` — TF-IDF cosine similarity between active prompt and entry
- `f: float 0-1` — friction = 1 - p
- `v: float` — valence multiplier (2.0 same register / 1.0 adjacent / 0.5 distant)
- `x: float 0.1-1.0` — retrieval cost, depth position in shard (deeper = higher x)

**Output**

`a: float` — relevance score. Lower = more relevant. Sort ascending to rank.

**Python**

```python
def relevance(p: float, v: float, x: float) -> float:
    f = 1.0 - p
    if v == 0: v = 0.001
    return abs(p - (f / v)) * x
```

**SQL**

```sql
-- Score all entries in a shard against a query
-- p must be computed externally via TF-IDF cosine
-- Substitute p, v, x as computed values
SELECT
  title,
  content,
  date,
  ABS(p - ((1.0 - p) / v)) * x AS a
FROM reservoir
WHERE shard = :target_shard
ORDER BY a ASC
LIMIT 5;
```

---

## 2. drift :: drift = |a - z| / r

**Domain:** drift · **Depends on:** relevance, resonance

**Equation**

```
drift = |a - z| / r
```

**Variables**

- `a` = max cosine similarity of current prompt against full corpus
- `z` = max cosine similarity of previous prompt against full corpus
- `r` = mean cosine similarity of current prompt across corpus (resonance)
- `drift` = normalised distance between current and previous prompt positions

**Output**

- `drift: float` — magnitude of movement between prompts, normalised by resonance
- `quadrant: str` — NEW TERRITORY / CIRCLING / SHARP PIVOT / STUCK

**Python**

```python
def drift(current: str, prev: str, corpus_docs: list, vectorizer, matrix) -> dict:
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    cur_sims = cosine_similarity(vectorizer.transform([current]), matrix)[0]
    prv_sims = cosine_similarity(vectorizer.transform([prev]), matrix)[0]
    a = float(np.max(cur_sims))
    z = float(np.max(prv_sims))
    r = float(np.mean(cur_sims))
    if r < 0.001: r = 0.001
    d = abs(a - z) / r
    if d > 0.6 and r < 0.35:   q = 'NEW TERRITORY'
    elif d < 0.3 and r > 0.5:  q = 'CIRCLING FAMILIAR GROUND'
    elif d > 0.6 and r > 0.5:  q = 'SHARP PIVOT INSIDE KNOWN SPACE'
    else:                      q = 'STUCK ON SOMETHING RARE'
    return {'a': a, 'z': z, 'r': r, 'drift': d, 'quadrant': q}
```

**SQL**

```sql
-- Drift requires vector ops — SQL approximation only
-- Use full Python implementation for real computation
-- This query surfaces the best-matching entry for manual a/z estimation
SELECT title, content, shard, date
FROM reservoir
WHERE shard != 'inference-graph'
ORDER BY createdTime DESC;
```

---

## 3. resonance :: r = mean(cosine(query, corpus))

**Domain:** resonance · **Depends on:** tfidf_cosine, shard corpus

**Equation**

```
r = mean(cosine(query, entry)) across corpus
```

**Variables**

- `query` = active prompt string
- `corpus` = list of entry content strings (shard or full reservoir)
- `r` = mean cosine similarity across all corpus entries (output)

Higher r = more resonant = more typical for this corpus.

**Python**

```python
def resonance(query: str, corpus_docs: list, vectorizer=None) -> float:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    docs = corpus_docs if len(corpus_docs) >= 2 else corpus_docs + ['placeholder']
    if vectorizer is None:
        vectorizer = TfidfVectorizer(ngram_range=(1,2), min_df=1, sublinear_tf=True)
        matrix = vectorizer.fit_transform(docs)
    else:
        matrix = vectorizer.transform(docs)
    sims = cosine_similarity(vectorizer.transform([query]), matrix)[0]
    return float(np.mean(sims))

def resonance_field(query: str, shard_corpora: dict) -> dict:
    # shard_corpora: {shard_name: [content_strings]}
    return {shard: resonance(query, docs) for shard, docs in shard_corpora.items()}
```

**SQL**

```sql
-- Pull corpus for resonance computation (Python handles the vector math)
SELECT shard, content
FROM reservoir
WHERE shard != 'inference-graph'
  AND content IS NOT NULL
ORDER BY shard, date;
```

---

## 4. valence :: v = 2.0 / 1.0 / 0.5 by register match

**Domain:** valence · **Depends on:** detect_register

**Equation**

```
v = 2.0 if r1 == r2 else 1.0 if adjacent else 0.5
```

**Variables**

- `r1` = register of active prompt: charged / architectural / narrative / recursive / essay / flat
- `r2` = register of target entry or shard
- `v` = multiplier output: 2.0 (same) / 1.0 (adjacent) / 0.5 (distant)

**Output**

`v: float` — multiplier used in relevance equation.
2.0 = same register (amplifies relevance) · 1.0 = adjacent register (neutral) · 0.5 = distant register (dampens relevance)

**Python**

```python
ADJACENCY = {
    ('charged','narrative'), ('narrative','charged'),
    ('architectural','recursive'), ('recursive','architectural'),
    ('recursive','essay'), ('essay','recursive'),
    ('essay','charged'), ('charged','essay'),
    ('narrative','recursive'), ('recursive','narrative'),
}

def detect_register(text: str) -> str:
    t = text.lower()
    rules = {
        'charged':      ['grief','longing','frustrated','elated','defiant','love','fear','want','miss','anger','woman','raw','vulnerable'],
        'architectural':['architecture','system','loop','substrate','tick','design','build','dawn','distributed','node','shard','fork','mycelial'],
        'narrative':    ['ben','2300','scene','character','story','novel','fragmented','future','gift','tense'],
        'recursive':    ['again','keep','return','circle','revisit','before','same','meta','examining','prior','pattern','circling'],
        'essay':        ['schema','essay','baudrillard','borges','pessoa','tunnel','rave','dispatch','theoretical','hyperreality'],
    }
    scores = {r: sum(1 for w in words if w in t) for r, words in rules.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'flat'

def valence_multiplier(r1: str, r2: str) -> float:
    if r1 == r2: return 2.0
    if (r1,r2) in ADJACENCY: return 1.0
    return 0.5
```

**SQL**

```sql
-- No SQL implementation — register detection requires NLP
-- Use detect_register() in Python before querying
-- Example: filter entries by expected register tags
SELECT title, content, tags
FROM reservoir
WHERE shard = :target_shard
  AND tags LIKE '%architectural%'  -- substitute detected register
ORDER BY date DESC;
```

---

## 5. traversal :: t = w * axis_bonus * recency_bonus

**Domain:** traversal · **Depends on:** inference-graph edges, valence_register

**Equation**

```
t = w * axis_bonus * recency_bonus
```

**Variables**

- `w` = edge weight score: high = 3.0, medium = 2.0, low = 1.0
- `axis_bonus` = 1.3 if edge axis matches active prompt register, else 1.0
- `recency_bonus` = 1.2 if edge declared most recently, else 1.0
- `t` = traversal priority score (output)

**Output**

`t: float` — traversal priority score. Higher = pull from this shard first.
Pull count: high t (≥3.5) → 2 entries, medium (2.0–3.4) → 1 entry, low (<2.0) → 0.

**Python**

```python
def traversal_score(edge: dict, active_register: str, max_date: str) -> float:
    weight_map = {'high': 3.0, 'medium': 2.0, 'low': 1.0}
    axis_register_map = {
        'valence': 'charged', 'structural': 'architectural',
        'recursive': 'recursive', 'semantic': 'flat', 'biographical': 'flat'
    }
    w = weight_map.get(edge.get('weight', 'low'), 1.0)
    axis_reg = axis_register_map.get(edge.get('axis', ''), 'flat')
    axis_bonus = 1.3 if axis_reg == active_register else 1.0
    recency_bonus = 1.2 if edge.get('date', '') >= max_date else 1.0
    return w * axis_bonus * recency_bonus
```

**SQL**

```sql
-- Rank connected shards by traversal score for a given seed shard
-- axis_bonus and recency_bonus computed outside SQL
SELECT
  edge_to AS connected_shard,
  axis,
  weight,
  CASE weight
    WHEN 'high'   THEN 3.0
    WHEN 'medium' THEN 2.0
    WHEN 'low'    THEN 1.0
    ELSE 1.0
  END AS w
FROM reservoir
WHERE shard = 'inference-graph'
  AND (edge_from = :seed OR edge_to = :seed)
ORDER BY w DESC;
```
