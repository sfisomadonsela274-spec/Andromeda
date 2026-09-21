/**
 * =============================================================================
 *           🌌 ANDROMEDA CLIENT VECTOR MEMORY VAULT (INDEXEDDB)
 * =============================================================================
 * Standalone, private in-browser vector memory store running completely on
 * the viewer's machine. Provides semantic memory retrieval, document chunking,
 * and cosine similarity search with ZERO server transmission or storage.
 * =============================================================================
 */

export interface StoredMemory {
  id: string;
  text: string;
  category: 'conversation' | 'preference' | 'code' | 'workspace' | 'document';
  embedding: number[];
  timestamp: number;
  sessionId?: string;
  tags?: string[];
  metadata?: Record<string, any>;
}

export interface MemoryMatch {
  memory: StoredMemory;
  score: number; // Cosine similarity 0.0 - 1.0
}

const DB_NAME = 'andromeda_client_memory';
const DB_VERSION = 1;
const STORE_NAME = 'memories';
const VECTOR_DIM = 128;

const STOP_WORDS = new Set([
  'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
  'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
  'to', 'was', 'were', 'will', 'with'
]);

function fnv1a(str: string): number {
  let hash = 2166136261;
  for (let i = 0; i < str.length; i++) {
    hash ^= str.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

class ClientVectorMemoryVault {
  private db: IDBDatabase | null = null;
  private dbPromise: Promise<IDBDatabase> | null = null;

  constructor() {
    if (typeof window !== 'undefined' && 'indexedDB' in window) {
      this.initDB();
    }
  }

  private initDB(): Promise<IDBDatabase> {
    if (this.db) return Promise.resolve(this.db);
    if (this.dbPromise) return this.dbPromise;

    this.dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
          store.createIndex('timestamp', 'timestamp', { unique: false });
          store.createIndex('category', 'category', { unique: false });
          store.createIndex('sessionId', 'sessionId', { unique: false });
        }
      };

      request.onsuccess = (event) => {
        this.db = (event.target as IDBOpenDBRequest).result;
        resolve(this.db);
      };

      request.onerror = (event) => {
        reject((event.target as IDBOpenDBRequest).error);
      };
    });

    return this.dbPromise;
  }

  /**
   * Generates a normalized high-entropy semantic embedding vector (128-dim)
   * Uses FNV-1a word hashing + subword n-grams and stop-word downweighting
   */
  public generateEmbedding(text: string): number[] {
    const vector = new Array(VECTOR_DIM).fill(0);
    const cleaned = text.toLowerCase().replace(/[^a-z0-9\s]/g, ' ');
    const tokens = cleaned.split(/\s+/).filter((t) => t.length > 1 && !STOP_WORDS.has(t));

    if (tokens.length === 0) {
      return vector;
    }

    tokens.forEach((token) => {
      // 1. Primary Word Token Hash
      const wordHash = fnv1a(token);
      const idx = wordHash % VECTOR_DIM;
      const wordWeight = token.length >= 4 ? 2.5 : 1.2;
      vector[idx] += wordWeight;

      // 2. Subword 3-grams for morphological similarity
      for (let i = 0; i <= token.length - 3; i++) {
        const gram = token.substring(i, i + 3);
        const gIdx = fnv1a(gram) % VECTOR_DIM;
        vector[gIdx] += 0.8;
      }
    });

    // 3. L2 Unit Normalization
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

  /**
   * Calculate Cosine Similarity between vectors A and B
   */
  public cosineSimilarity(a: number[], b: number[]): number {
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

  /**
   * Store a text chunk or memory into IndexedDB
   */
  public async memorize(
    text: string,
    category: StoredMemory['category'] = 'conversation',
    metadata: Record<string, any> = {}
  ): Promise<string> {
    if (!text || !text.trim()) return '';

    const db = await this.initDB();
    const id = `mem_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const embedding = this.generateEmbedding(text);

    const record: StoredMemory = {
      id,
      text: text.trim(),
      category,
      embedding,
      timestamp: Date.now(),
      sessionId: metadata.sessionId || 'client_session',
      tags: metadata.tags || [],
      metadata
    };

    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORE_NAME], 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const req = store.put(record);

      req.onsuccess = () => resolve(id);
      req.onerror = () => reject(req.error);
    });
  }

  /**
   * Semantically search memories matching query with cosine similarity
   */
  public async retrieve(query: string, topK = 3, threshold = 0.3): Promise<MemoryMatch[]> {
    if (!query || !query.trim()) return [];

    const queryVec = this.generateEmbedding(query);
    const allMemories = await this.getAllMemories();

    const scored: MemoryMatch[] = allMemories.map((mem) => ({
      memory: mem,
      score: this.cosineSimilarity(queryVec, mem.embedding)
    }));

    return scored
      .filter((match) => match.score >= threshold)
      .sort((a, b) => b.score - a.score)
      .slice(0, topK);
  }

  /**
   * Retrieve all memories stored in IndexedDB
   */
  public async getAllMemories(): Promise<StoredMemory[]> {
    const db = await this.initDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORE_NAME], 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.getAll();

      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  }

  /**
   * Delete a single memory by ID
   */
  public async deleteMemory(id: string): Promise<boolean> {
    const db = await this.initDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORE_NAME], 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const req = store.delete(id);

      req.onsuccess = () => resolve(true);
      req.onerror = () => reject(req.error);
    });
  }

  /**
   * Clear all memories from IndexedDB
   */
  public async clearAllMemories(): Promise<boolean> {
    const db = await this.initDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORE_NAME], 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const req = store.clear();

      req.onsuccess = () => resolve(true);
      req.onerror = () => reject(req.error);
    });
  }

  /**
   * Calculate memory storage statistics
   */
  public async getStorageStats(): Promise<{ count: number; estimatedKB: number }> {
    const memories = await this.getAllMemories();
    const count = memories.length;
    let bytes = 0;

    memories.forEach((m) => {
      bytes += m.text.length * 2; // UTF-16
      bytes += m.embedding.length * 4; // float32
      bytes += 128; // metadata overhead
    });

    return {
      count,
      estimatedKB: Math.round(bytes / 1024)
    };
  }

  /**
   * Formats retrieved memory snippets for system prompt injection
   */
  public formatRetrievedContext(matches: MemoryMatch[]): string {
    if (matches.length === 0) return '';
    const formatted = matches
      .map((m, idx) => `• [Memory #${idx + 1} (${Math.round(m.score * 100)}% match)]: ${m.memory.text}`)
      .join('\n');

    return `\n🧠 [Andromeda Local Vector Memory Context]:\n${formatted}\n`;
  }
}

export const clientVectorMemory = new ClientVectorMemoryVault();
