export type FuzzyMatch = {
  item: string;
  score: number;
  /** Positions in `item` of the matched characters, ascending. */
  indices: number[];
};

export type Segment = { text: string; match: boolean };

const BOUNDARY_CHARACTERS = new Set(['.', '-', '_', ' ', '/']);

function scoreIndices(text: string, indices: number[]): number {
  let score = 0;
  indices.forEach((index, position) => {
    score += 1;
    // Reward matches at the start of a word, e.g. the "f" in "Deploy.fe-dev".
    if (index === 0 || BOUNDARY_CHARACTERS.has(text[index - 1])) score += 8;
    if (position > 0) {
      const gap = index - indices[position - 1] - 1;
      // Reward contiguous runs and penalize gaps, so substrings outrank scattered letters.
      score += gap === 0 ? 10 : -Math.min(gap, 5) * 1.5;
    }
  });
  // Prefer matches that begin early in the text.
  return score - Math.min(indices[0], 10) * 0.5;
}

/** Best in-order (subsequence) match of `token` in `text`, or null. Both must be lowercase. */
function matchToken(text: string, token: string): { indices: number[]; score: number } | null {
  let best: { indices: number[]; score: number } | null = null;

  for (
    let start = text.indexOf(token[0]);
    start !== -1;
    start = text.indexOf(token[0], start + 1)
  ) {
    const indices = [start];
    let cursor = start + 1;
    for (let i = 1; i < token.length; i++) {
      const next = text.indexOf(token[i], cursor);
      if (next === -1) break;
      indices.push(next);
      cursor = next + 1;
    }
    if (indices.length < token.length) break; // later starts cannot fit either

    const score = scoreIndices(text, indices);
    if (!best || score > best.score) best = { indices, score };
  }

  return best;
}

function matchItem(item: string, tokens: string[]): FuzzyMatch | null {
  const text = item.toLowerCase();
  const indices = new Set<number>();
  let score = 0;

  for (const token of tokens) {
    const match = matchToken(text, token);
    if (!match) return null;
    match.indices.forEach((index) => indices.add(index));
    score += match.score;
  }

  return { item, score, indices: [...indices].sort((a, b) => a - b) };
}

/**
 * Case-insensitive fuzzy filter. Each whitespace-separated token must appear in order
 * (not necessarily adjacent) in the item. Results are best match first; ties keep input order.
 * An empty query returns every item unchanged.
 */
export function fuzzyFilter(items: readonly string[], query: string): FuzzyMatch[] {
  const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return items.map((item) => ({ item, score: 0, indices: [] }));

  return items
    .map((item, order) => ({ match: matchItem(item, tokens), order }))
    .filter((entry): entry is { match: FuzzyMatch; order: number } => entry.match !== null)
    .sort((a, b) => b.match.score - a.match.score || a.order - b.order)
    .map((entry) => entry.match);
}

/** Splits `text` into runs of matched and unmatched characters, for highlighting. */
export function highlightSegments(text: string, indices: readonly number[]): Segment[] {
  const matched = new Set(indices);
  const segments: Segment[] = [];

  [...text].forEach((character, index) => {
    const match = matched.has(index);
    const last = segments[segments.length - 1];
    if (last && last.match === match) last.text += character;
    else segments.push({ text: character, match });
  });

  return segments;
}
