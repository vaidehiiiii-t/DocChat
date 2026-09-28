import { apiClient } from "./client";

export interface ChatSource {
  chunk_id: number;
  document_id: number;
  filename: string;
  page: number;
  snippet: string;
  score: number;
}

export interface ChatMessageItem {
  id: number;
  session_id: number;
  role: "user" | "assistant";
  content: string;
  sources: ChatSource[];
  model: string | null;
  created_at: string | null;
}

export interface ChatSessionItem {
  id: number;
  user_id: number;
  document_id: number | null;
  title: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export const createSessionApi = async (data: {
  document_id?: number | null;
  title?: string;
}): Promise<ChatSessionItem> => {
  const res = await apiClient.post<ChatSessionItem>("/chat/sessions", data);
  return res.data;
};

export const listSessionsApi = async (): Promise<ChatSessionItem[]> => {
  const res = await apiClient.get<ChatSessionItem[]>("/chat/sessions");
  return res.data;
};

export const getSessionMessagesApi = async (
  sessionId: number
): Promise<ChatMessageItem[]> => {
  const res = await apiClient.get<ChatMessageItem[]>(
    `/chat/sessions/${sessionId}/messages`
  );
  return res.data;
};

export const deleteSessionApi = async (
  sessionId: number
): Promise<{ message: string }> => {
  const res = await apiClient.delete<{ message: string }>(
    `/chat/sessions/${sessionId}`
  );
  return res.data;
};

export const postMessageApi = async (
  sessionId: number,
  content: string
): Promise<{
  user_message: ChatMessageItem;
  assistant_message: ChatMessageItem;
}> => {
  const res = await apiClient.post<{
    user_message: ChatMessageItem;
    assistant_message: ChatMessageItem;
  }>(`/chat/sessions/${sessionId}/messages`, { content });
  return res.data;
};

export interface StreamMessageOptions {
  sessionId: number;
  content: string;
  onSources?: (sources: ChatSource[]) => void;
  onToken?: (token: string) => void;
  onDone?: (data: {
    user_message_id: number;
    assistant_message_id: number;
    model?: string;
  }) => void;
  onError?: (err: Error) => void;
  signal?: AbortSignal;
}

export const streamMessageApi = async ({
  sessionId,
  content,
  onSources,
  onToken,
  onDone,
  onError,
  signal,
}: StreamMessageOptions): Promise<void> => {
  const token = localStorage.getItem("docchat_token");
  const baseUrl = import.meta.env.VITE_API_BASE_URL || "/api";

  const response = await fetch(
    `${baseUrl}/chat/sessions/${sessionId}/messages/stream`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content }),
      signal,
    }
  );

  if (!response.ok) {
    let errMsg = "Failed to stream message";
    try {
      const errJson = await response.json();
      errMsg = errJson.error?.message || errMsg;
    } catch {
      // ignore
    }
    const err = new Error(errMsg);
    onError?.(err);
    throw err;
  }

  if (!response.body) {
    throw new Error("No response body received from server");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const block of parts) {
      if (!block.trim()) continue;
      const lines = block.split("\n");
      let eventType = "message";
      let dataText = "";

      for (const line of lines) {
        if (line.startsWith("event:")) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataText += line.slice(5).trim();
        }
      }

      if (eventType === "sources") {
        try {
          const parsed = JSON.parse(dataText);
          onSources?.(parsed);
        } catch (e) {
          console.error("Failed to parse sources event", e);
        }
      } else if (eventType === "token") {
        try {
          const parsed = JSON.parse(dataText);
          if (parsed.token) {
            onToken?.(parsed.token);
          }
        } catch (e) {
          console.error("Failed to parse token event", e);
        }
      } else if (eventType === "done") {
        try {
          const parsed = JSON.parse(dataText);
          onDone?.(parsed);
        } catch (e) {
          console.error("Failed to parse done event", e);
        }
      } else if (eventType === "error") {
        try {
          const parsed = JSON.parse(dataText);
          const err = new Error(parsed.message || "Streaming error occurred");
          onError?.(err);
        } catch {
          onError?.(new Error("Streaming error occurred"));
        }
      }
    }
  }
};
