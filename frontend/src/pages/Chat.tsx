import React, { useState, useEffect, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { LogOut, Files, AlertCircle, MessageSquare } from "lucide-react";

import { useAuth } from "../context/AuthContext";
import {
  listSessionsApi,
  createSessionApi,
  deleteSessionApi,
  getSessionMessagesApi,
  streamMessageApi,
  ChatSource,
  ChatSessionItem,
  ChatMessageItem,
} from "../api/chat";
import { getDocumentsApi, DocumentItem } from "../api/documents";
import { SessionSidebar } from "../components/SessionSidebar";
import { ChatWindow } from "../components/ChatWindow";

export const Chat: React.FC = () => {
  const { user, logout } = useAuth();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  // 1. Fetch user's documents
  const { data: documents = [] } = useQuery<DocumentItem[]>({
    queryKey: ["documents"],
    queryFn: getDocumentsApi,
  });

  // 2. Fetch sessions
  const { data: sessions = [] } = useQuery<ChatSessionItem[]>({
    queryKey: ["chat_sessions"],
    queryFn: listSessionsApi,
  });

  // 3. Handle URL query param: ?doc=<doc_id> -> auto-create or select session
  const docParam = searchParams.get("doc");
  useEffect(() => {
    if (docParam && documents.length > 0) {
      const docId = Number(docParam);
      // Create a new session for this doc
      createSessionApi({ document_id: docId })
        .then((newSession) => {
          queryClient.invalidateQueries({ queryKey: ["chat_sessions"] });
          setActiveSessionId(newSession.id);
          setSearchParams({});
        })
        .catch((err) => {
          setErrorMessage(err.response?.data?.error?.message || "Failed to initialize scoped chat.");
        });
    } else if (sessions.length > 0 && activeSessionId === null) {
      // Default to first active session if none selected
      setActiveSessionId(sessions[0].id);
    }
  }, [docParam, documents, sessions]);

  // 4. Fetch messages for active session
  const {
    data: messages = [],
    isLoading: isLoadingMessages,
  } = useQuery<ChatMessageItem[]>({
    queryKey: ["messages", activeSessionId],
    queryFn: () =>
      activeSessionId ? getSessionMessagesApi(activeSessionId) : Promise.resolve([]),
    enabled: !!activeSessionId,
  });

  // 5. Send message mutation with streaming and cancellation
  const [isSending, setIsSending] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleCancelStream = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsSending(false);
    if (activeSessionId) {
      queryClient.invalidateQueries({ queryKey: ["messages", activeSessionId] });
    }
  };

  const sendMessage = async (content: string) => {
    if (!activeSessionId) {
      // If no active session, create a global one first
      try {
        const newSession = await createSessionApi({});
        queryClient.invalidateQueries({ queryKey: ["chat_sessions"] });
        setActiveSessionId(newSession.id);
        await postMessage(newSession.id, content);
      } catch (err: any) {
        setErrorMessage(err.response?.data?.error?.message || "Failed to start chat.");
      }
      return;
    }

    await postMessage(activeSessionId, content);
  };

  const postMessage = async (sessionId: number, content: string) => {
    setIsSending(true);
    setErrorMessage(null);

    const tempUserId = Date.now();
    const tempAssistantId = Date.now() + 1;

    // Optimistic user message append in UI
    const optimisticUserMsg: ChatMessageItem = {
      id: tempUserId,
      session_id: sessionId,
      role: "user",
      content,
      sources: [],
      model: null,
      created_at: new Date().toISOString(),
    };

    const optimisticAssistantMsg: ChatMessageItem = {
      id: tempAssistantId,
      session_id: sessionId,
      role: "assistant",
      content: "",
      sources: [],
      model: null,
      created_at: new Date().toISOString(),
    };

    queryClient.setQueryData<ChatMessageItem[]>(
      ["messages", sessionId],
      (prev = []) => [...prev, optimisticUserMsg, optimisticAssistantMsg]
    );

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let accumulatedContent = "";
    let accumulatedSources: ChatSource[] = [];

    try {
      await streamMessageApi({
        sessionId,
        content,
        signal: controller.signal,
        onSources: (sources) => {
          accumulatedSources = sources;
          queryClient.setQueryData<ChatMessageItem[]>(
            ["messages", sessionId],
            (prev = []) =>
              prev.map((m) =>
                m.id === tempAssistantId ? { ...m, sources } : m
              )
          );
        },
        onToken: (token) => {
          accumulatedContent += token;
          queryClient.setQueryData<ChatMessageItem[]>(
            ["messages", sessionId],
            (prev = []) =>
              prev.map((m) =>
                m.id === tempAssistantId ? { ...m, content: accumulatedContent } : m
              )
          );
        },
        onDone: (data) => {
          queryClient.setQueryData<ChatMessageItem[]>(
            ["messages", sessionId],
            (prev = []) =>
              prev.map((m) => {
                if (m.id === tempAssistantId) {
                  return {
                    ...m,
                    id: data.assistant_message_id,
                    content: accumulatedContent,
                    sources: accumulatedSources,
                    model: data.model || null,
                  };
                }
                if (m.id === tempUserId) {
                  return { ...m, id: data.user_message_id };
                }
                return m;
              })
          );
          queryClient.invalidateQueries({ queryKey: ["chat_sessions"] });
        },
        onError: (err) => {
          setErrorMessage(err.message || "Streaming error occurred.");
        },
      });
    } catch (err: any) {
      if (err.name !== "AbortError") {
        const msg =
          err.response?.data?.error?.message ||
          err.message ||
          "The AI model is busy. Please try again in a minute.";
        setErrorMessage(msg);
      }
      queryClient.invalidateQueries({ queryKey: ["messages", sessionId] });
    } finally {
      setIsSending(false);
      abortControllerRef.current = null;
    }
  };

  // 6. New chat handler
  const handleNewChat = async (documentId: number | null) => {
    try {
      const newSession = await createSessionApi({ document_id: documentId });
      queryClient.invalidateQueries({ queryKey: ["chat_sessions"] });
      setActiveSessionId(newSession.id);
    } catch (err: any) {
      setErrorMessage(err.response?.data?.error?.message || "Failed to create session.");
    }
  };

  // 7. Delete session handler
  const deleteMutation = useMutation({
    mutationFn: deleteSessionApi,
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ["chat_sessions"] });
      if (activeSessionId === deletedId) {
        setActiveSessionId(null);
      }
    },
  });

  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const activeDoc = activeSession?.document_id
    ? documents.find((d) => d.id === activeSession.document_id)
    : null;
  const scopeTitle = activeDoc ? activeDoc.filename : "All Documents";

  return (
    <div className="min-h-screen bg-apple-parchment flex flex-col font-sans">
      {/* Global Apple Navigation */}
      <header className="bg-black text-white h-11 px-3 sm:px-6 flex items-center justify-between text-xs sticky top-0 z-40 backdrop-blur-md">
        <div className="flex items-center gap-4 sm:gap-6">
          <Link to="/documents" className="font-semibold tracking-tight text-sm flex items-center gap-1.5 sm:gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-apple-blue inline-block shrink-0" />
            <span>DocChat</span>
          </Link>
          <nav className="flex items-center gap-3 sm:gap-4 text-neutral-400">
            <Link to="/documents" className="hover:text-white transition-colors flex items-center gap-1">
              <Files className="w-3 h-3" />
              <span>Documents</span>
            </Link>
            <Link to="/chat" className="text-white hover:text-white transition-colors">
              Chat
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-2 sm:gap-4">
          {/* Mobile Sessions Toggle */}
          <button
            onClick={() => setIsMobileSidebarOpen(true)}
            className="md:hidden flex items-center gap-1 px-2.5 py-1 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 rounded-pill text-[11px] transition-colors"
            title="Open conversations"
          >
            <MessageSquare className="w-3 h-3 text-apple-blue" />
            <span>Chats ({sessions.length})</span>
          </button>

          <span className="text-neutral-400 text-[11px] hidden lg:inline truncate max-w-[150px]">
            {user?.email}
          </span>
          <button
            onClick={logout}
            className="flex items-center gap-1 px-2.5 sm:px-3 py-1 bg-neutral-800 hover:bg-neutral-700 text-white rounded-pill text-[11px] transition-colors"
          >
            <LogOut className="w-3 h-3" />
            <span className="hidden xs:inline">Sign Out</span>
          </button>
        </div>
      </header>

      {/* Error alert toast if present */}
      {errorMessage && (
        <div className="bg-red-50 border-b border-red-200 px-4 sm:px-6 py-2 flex items-center justify-between text-xs text-red-700">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-red-500 hover:text-red-800 font-bold px-1"
          >
            ✕
          </button>
        </div>
      )}

      {/* Chat Workspace */}
      <div className="flex-1 flex overflow-hidden">
        <SessionSidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={setActiveSessionId}
          onNewChat={handleNewChat}
          onDeleteSession={(id) => deleteMutation.mutate(id)}
          documents={documents}
          isMobileOpen={isMobileSidebarOpen}
          onCloseMobile={() => setIsMobileSidebarOpen(false)}
        />

        <ChatWindow
          messages={messages}
          isLoadingMessages={isLoadingMessages}
          isSending={isSending}
          onSendMessage={sendMessage}
          onCancelStream={handleCancelStream}
          scopeTitle={scopeTitle}
        />
      </div>
    </div>
  );
};

export default Chat;
