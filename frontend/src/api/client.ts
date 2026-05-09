import type { DocumentInfo, Interaction } from '../types';

const BASE = '';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, options);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── Sessions ──────────────────────────────────────────────────────────────────

export interface SessionInfo {
  name: string;
  active: boolean;
}

export function listSessions(): Promise<SessionInfo[]> {
  return request('/sessions');
}

export function loadSession(): Promise<Interaction[]> {
  return request('/session');
}

export function createSession(name: string): Promise<unknown> {
  return request(`/session?name=${encodeURIComponent(name)}`, { method: 'POST' });
}

export function activateSession(name: string): Promise<unknown> {
  return request(`/session/activate?name=${encodeURIComponent(name)}`, { method: 'POST' });
}

export function deleteSession(name: string): Promise<unknown> {
  return request(`/session?name=${encodeURIComponent(name)}`, { method: 'DELETE' });
}

// ── Documents ─────────────────────────────────────────────────────────────────

export function listDocuments(): Promise<DocumentInfo[]> {
  return request('/documents/list');
}

export function uploadDocument(
  name: string,
  description: string,
  file: File
): Promise<unknown> {
  const form = new FormData();
  form.append('name', name);
  form.append('description', description);
  form.append('file', file);
  return request('/documents', { method: 'POST', body: form });
}

export function deleteDocument(name: string): Promise<unknown> {
  return request(`/documents?name=${encodeURIComponent(name)}`, { method: 'DELETE' });
}

export function documentPageUrl(documentName: string, page: number): string {
  return `${BASE}/documents/${encodeURIComponent(documentName)}/pages/${page}`;
}

// ── Chat ─────────────────────────────────────────────────────────────────────

export async function streamChat(
  query: string,
  onChunk: (text: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${BASE}/chat/stream?query=${encodeURIComponent(query)}`, { signal });
  if (!res.ok) throw new Error(`Chat error: HTTP ${res.status}`);
  if (!res.body) throw new Error('No response body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk(decoder.decode(value, { stream: true }));
  }
}
