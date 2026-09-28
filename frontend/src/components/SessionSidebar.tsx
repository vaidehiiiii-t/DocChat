import React from "react";
import { Plus, MessageSquare, Trash2, FileText, Globe, X } from "lucide-react";
import { ChatSessionItem } from "../api/chat";
import { DocumentItem } from "../api/documents";

interface SessionSidebarProps {
  sessions: ChatSessionItem[];
  activeSessionId: number | null;
  onSelectSession: (id: number) => void;
  onNewChat: (documentId: number | null) => void;
  onDeleteSession: (id: number) => void;
  documents: DocumentItem[];
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export const SessionSidebar: React.FC<SessionSidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  documents,
  isMobileOpen,
  onCloseMobile,
}) => {
  const [selectedDocId, setSelectedDocId] = React.useState<number | null>(null);

  const readyDocs = documents.filter((d) => d.status === "ready");

  const getDocName = (docId: number | null) => {
    if (!docId) return "All Documents";
    const doc = documents.find((d) => d.id === docId);
    return doc ? doc.filename : "Scoped Document";
  };

  const handleSelectAndClose = (id: number) => {
    onSelectSession(id);
    if (onCloseMobile) onCloseMobile();
  };

  const handleNewChatAndClose = (docId: number | null) => {
    onNewChat(docId);
    if (onCloseMobile) onCloseMobile();
  };

  const sidebarContent = (
    <aside
      className={`bg-apple-parchment border-r border-apple-hairline flex flex-col h-full ${
        isMobileOpen !== undefined
          ? "w-72 md:w-64 lg:w-72"
          : "w-64 md:w-72 h-[calc(100vh-44px)]"
      }`}
    >
      {/* Top action section */}
      <div className="p-4 border-b border-apple-hairline space-y-3">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => handleNewChatAndClose(selectedDocId)}
            className="flex-1 flex items-center justify-center gap-2 py-2 px-4 bg-apple-blue hover:bg-apple-primary-focus text-white rounded-pill text-xs font-semibold shadow-sm transition-colors cursor-pointer"
            data-testid="new-chat-button"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Chat</span>
          </button>
          {onCloseMobile && (
            <button
              onClick={onCloseMobile}
              className="md:hidden ml-2 p-1.5 text-neutral-500 hover:text-apple-ink rounded-lg"
              aria-label="Close sidebar"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Scope selector */}
        <div className="space-y-1">
          <label className="text-[10px] font-semibold text-apple-muted-48 uppercase tracking-wider block">
            Scope
          </label>
          <select
            value={selectedDocId ?? ""}
            onChange={(e) =>
              setSelectedDocId(e.target.value ? Number(e.target.value) : null)
            }
            className="w-full text-xs bg-white border border-apple-hairline rounded-lg px-2.5 py-1.5 text-apple-ink focus:outline-none focus:ring-1 focus:ring-apple-blue"
            data-testid="scope-select"
          >
            <option value="">All Documents (Global)</option>
            {readyDocs.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.filename}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        <div className="text-[10px] font-semibold text-apple-muted-48 uppercase tracking-wider px-2 py-1">
          Recent Conversations
        </div>

        {sessions.length === 0 ? (
          <div className="p-4 text-center text-apple-muted-48 text-xs">
            No conversations yet. Start a new chat to begin.
          </div>
        ) : (
          sessions.map((session) => {
            const isActive = session.id === activeSessionId;
            return (
              <div
                key={session.id}
                data-testid={`session-item-${session.id}`}
                onClick={() => handleSelectAndClose(session.id)}
                className={`group flex items-center justify-between p-2.5 rounded-xl text-xs cursor-pointer transition-colors ${
                  isActive
                    ? "bg-white text-apple-ink shadow-sm border border-apple-hairline font-semibold"
                    : "text-neutral-600 hover:bg-white/60"
                }`}
              >
                <div className="flex items-center gap-2 overflow-hidden mr-1">
                  <MessageSquare
                    className={`w-3.5 h-3.5 shrink-0 ${
                      isActive ? "text-apple-blue" : "text-neutral-400"
                    }`}
                  />
                  <div className="overflow-hidden">
                    <p className="truncate text-xs">
                      {session.title || "Untitled Chat"}
                    </p>
                    <span className="text-[10px] text-apple-muted-48 flex items-center gap-1">
                      {session.document_id ? (
                        <>
                          <FileText className="w-2.5 h-2.5" />
                          <span className="truncate max-w-[130px]">
                            {getDocName(session.document_id)}
                          </span>
                        </>
                      ) : (
                        <>
                          <Globe className="w-2.5 h-2.5" />
                          <span>All Docs</span>
                        </>
                      )}
                    </span>
                  </div>
                </div>

                <button
                  type="button"
                  title="Delete chat"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(session.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 text-neutral-400 hover:text-rose-600 hover:bg-rose-50 rounded transition-all"
                  data-testid={`delete-session-${session.id}`}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );

  if (isMobileOpen !== undefined) {
    return (
      <>
        {/* Desktop permanent sidebar */}
        <div className="hidden md:flex flex-col h-[calc(100vh-44px)]">
          {sidebarContent}
        </div>

        {/* Mobile modal drawer */}
        {isMobileOpen && (
          <div className="fixed inset-0 z-50 md:hidden flex">
            <div
              className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
              onClick={onCloseMobile}
              aria-hidden="true"
            />
            <div className="relative z-10 w-72 max-w-[85vw] h-full shadow-2xl">
              {sidebarContent}
            </div>
          </div>
        )}
      </>
    );
  }

  return sidebarContent;
};
