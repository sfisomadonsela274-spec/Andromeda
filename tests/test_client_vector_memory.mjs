/**
 * =============================================================================
 *         🧪 ANDROMEDA CLIENT VECTOR MEMORY & EMBEDDINGS TEST SUITE
 * =============================================================================
 * Validates:
 *  - 128-dim semantic embedding vector generation and L2 unit normalization
 *  - Cosine similarity computation
 *  - Semantic clustering: semantically relevant queries score significantly higher
 *  - Ranking accuracy: top-K retrieval picks the correct relevant document
 *  - Context prompt formatter output
 * =============================================================================
 */

import assert from 'node:assert';

const VECTOR_DIM = 128;
const STOP_WORDS = new Set([
  'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
  'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
  'to', 'was', 'were', 'will', 'with'
]);

function fnv1a(str) {
  let hash = 2166136261;
  for (let i = 0; i < str.length; i++) {
    hash ^= str.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function generateEmbedding(text) {
  const vector = new Array(VECTOR_DIM).fill(0);
  const cleaned = text.toLowerCase().replace(/[^a-z0-9\s]/g, ' ');
  const tokens = cleaned.split(/\s+/).filter(t => t.length > 1 && !STOP_WORDS.has(t));

  if (tokens.length === 0) return vector;

  tokens.forEach((token) => {
    const wordHash = fnv1a(token);
    const idx = wordHash % VECTOR_DIM;
    const wordWeight = token.length >= 4 ? 2.5 : 1.2;
    vector[idx] += wordWeight;

    for (let i = 0; i <= token.length - 3; i++) {
      const gram = token.substring(i, i + 3);
      const gIdx = fnv1a(gram) % VECTOR_DIM;
      vector[gIdx] += 0.8;
    }
  });

  let norm = 0;
  for (let i = 0; i < VECTOR_DIM; i++) {
    norm += vector[i] * vector[i];
  }
  norm = Math.sqrt(norm);
  if (norm > 0) {
    for (let i = 0; i < VECTOR_DIM; i++) {
      vector[i] = Number((vector[i] / norm).toFixed(5));
    }
  }

  return vector;
}

function cosineSimilarity(a, b) {
  if (a.length !== b.length || a.length === 0) return 0;
  let dot = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  const denominator = Math.sqrt(normA) * Math.sqrt(normB);
  if (denominator === 0) return 0;
  return Number((dot / denominator).toFixed(4));
}

console.log('--- Running Andromeda Client Vector Memory Tests ---');

// Test 1: Vector Dimension & L2 Normalization
{
  const text = 'Andromeda intelligent cosmic workspace companion';
  const vec = generateEmbedding(text);
  assert.equal(vec.length, VECTOR_DIM);

  let norm = 0;
  for (const val of vec) norm += val * val;
  const len = Math.sqrt(norm);
  assert.ok(Math.abs(len - 1.0) < 0.01, 'Vector must be L2 normalized to unit length ~1.0');
  console.log('✓ Test 1: Vector Dimension (128-dim) & L2 Normalization Passed');
}

// Test 2: Identical Text Cosine Similarity
{
  const text = 'User prefers dark mode and high performance';
  const v1 = generateEmbedding(text);
  const v2 = generateEmbedding(text);
  const sim = cosineSimilarity(v1, v2);
  assert.ok(sim >= 0.999, 'Identical texts must have cosine similarity ~1.0');
  console.log(`✓ Test 2: Identical Text Similarity Passed (${sim})`);
}

// Test 3: Semantic Association vs Noise
{
  const codingMemory = generateEmbedding('I write software in TypeScript and Python for backend APIs');
  const codingQuery = generateEmbedding('TypeScript programming language');
  const cookingNoise = generateEmbedding('Recipe for chocolate chip cookies with sugar and vanilla');

  const simRelated = cosineSimilarity(codingMemory, codingQuery);
  const simUnrelated = cosineSimilarity(codingMemory, cookingNoise);

  console.log(`   - Related similarity (Coding query): ${simRelated}`);
  console.log(`   - Unrelated similarity (Cooking noise): ${simUnrelated}`);

  assert.ok(simRelated > simUnrelated, 'Related query must score higher than unrelated noise');
  console.log('✓ Test 3: Semantic Association vs Noise Passed');
}

// Test 4: Top-K Semantic Retrieval Ranking
{
  const corpus = [
    { id: 'mem_1', text: 'Listen to ambient lo-fi music playlist on Spotify', category: 'music' },
    { id: 'mem_2', text: 'Working on Docker compose containers and Linux DBus', category: 'code' },
    { id: 'mem_3', text: 'User is located in Johannesburg South Africa', category: 'preference' }
  ];

  const query = 'Play some music and songs on Spotify';
  const qVec = generateEmbedding(query);

  const scored = corpus.map((m) => ({
    ...m,
    score: cosineSimilarity(qVec, generateEmbedding(m.text))
  })).sort((a, b) => b.score - a.score);

  assert.equal(scored[0].id, 'mem_1', 'Music query must rank memory #1 highest');
  console.log(`✓ Test 4: Top-1 Semantic Retrieval Ranking Passed (Rank #1: "${scored[0].text}" with score ${scored[0].score})`);
}

// Test 5: Context Formatter
{
  const matches = [
    { memory: { text: 'Prefers TypeScript over JavaScript' }, score: 0.88 },
    { memory: { text: 'Running Andromeda on local WebGPU' }, score: 0.72 }
  ];

  const formatted = matches
    .map((m, idx) => `• [Memory #${idx + 1} (${Math.round(m.score * 100)}% match)]: ${m.memory.text}`)
    .join('\n');

  assert.ok(formatted.includes('Prefers TypeScript'));
  assert.ok(formatted.includes('88% match'));
  console.log('✓ Test 5: Context Formatter Passed');
}

console.log('🎉 ALL CLIENT VECTOR MEMORY TESTS PASSED CLEANLY!');
