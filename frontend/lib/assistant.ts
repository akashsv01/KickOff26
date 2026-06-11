import { API_URL, getToken } from "@/lib/api";

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
};

export type ChatStatus = {
  configured: boolean;
  model: string;
};

export const STARTER_PROMPTS_GUEST = [
  "Show Group A standings",
  "When does Mexico play next?",
  "Explain third-place qualification",
  "Who coaches Brazil?",
] as const;

export const STARTER_PROMPTS_USER = [
  "When does my team play next?",
  "Show Group A standings",
  "Explain qualification",
  "What did I predict for the final?",
] as const;

export async function fetchChatStatus(): Promise<ChatStatus> {
  const res = await fetch(`${API_URL}/api/chat/status`);
  if (!res.ok) throw new Error("Assistant unavailable");
  return res.json();
}

export async function streamChatReply(
  message: string,
  history: ChatMessage[],
  onDelta: (text: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_URL}/api/chat/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      message,
      history: history.map(({ role, content }) => ({ role, content })),
    }),
    signal,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : "Chat request failed");
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response stream");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      for (const line of part.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const data = line.slice(5).trim();
        if (data === "[DONE]") return;
        try {
          const parsed = JSON.parse(data) as { delta?: string };
          if (parsed.delta) onDelta(parsed.delta);
        } catch {
          /* ignore malformed chunks */
        }
      }
    }
  }
}

export function newMessageId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export type AssistantLine =
  | { kind: "text"; text: string }
  | { kind: "bullet"; text: string }
  | { kind: "spacer" };

/** Parse assistant markdown-lite into renderable lines. */
export function parseAssistantLines(text: string): AssistantLine[] {
  return text.split("\n").map((line) => {
    const trimmed = line.trim();
    const bullet = trimmed.match(/^[-•*]\s+(.*)/);
    const numbered = trimmed.match(/^\d+[.)]\s+(.*)/);
    if (bullet) return { kind: "bullet" as const, text: bullet[1] };
    if (numbered) return { kind: "bullet" as const, text: numbered[1] };
    if (!trimmed) return { kind: "spacer" as const };
    return { kind: "text" as const, text: trimmed };
  });
}
