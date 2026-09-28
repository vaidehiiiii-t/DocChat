import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MessageBubble } from "../components/MessageBubble";
import { SourceChip } from "../components/SourceChip";
import { SessionSidebar } from "../components/SessionSidebar";
import { ChatWindow } from "../components/ChatWindow";
import { ChatMessageItem, ChatSource, ChatSessionItem } from "../api/chat";
import { DocumentItem } from "../api/documents";

describe("Chat Frontend Component Tests", () => {
  const sampleSource: ChatSource = {
    chunk_id: 101,
    document_id: 1,
    filename: "ai_overview.pdf",
    page: 2,
    snippet: "Deep learning models scale with compute and data volume.",
    score: 0.92,
  };

  const sampleAssistantMsg: ChatMessageItem = {
    id: 1,
    session_id: 10,
    role: "assistant",
    content: "Deep learning scales effectively with data, as shown in [1].",
    sources: [sampleSource],
    model: "google/gemma-4-31b-it:free",
    created_at: "2026-09-28T12:00:00Z",
  };

  const sampleUserMsg: ChatMessageItem = {
    id: 2,
    session_id: 10,
    role: "user",
    content: "How does deep learning scale?",
    sources: [],
    model: null,
    created_at: "2026-09-28T12:00:05Z",
  };

  it("renders user and assistant messages with markdown and source chips", () => {
    render(
      <div>
        <MessageBubble message={sampleUserMsg} />
        <MessageBubble message={sampleAssistantMsg} />
      </div>
    );

    // User message
    expect(screen.getByText("How does deep learning scale?")).toBeInTheDocument();

    // Assistant message content
    expect(
      screen.getByText(/Deep learning scales effectively with data/i)
    ).toBeInTheDocument();

    // Source chip
    expect(screen.getByText("ai_overview.pdf")).toBeInTheDocument();
    expect(screen.getByText("· p.2")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
  });

  it("expands source snippet on chip click", () => {
    render(<SourceChip source={sampleSource} index={1} />);

    // Snippet initially hidden
    expect(
      screen.queryByTestId("source-snippet-101")
    ).not.toBeInTheDocument();

    // Click chip
    const chipBtn = screen.getByTestId("source-chip-101");
    fireEvent.click(chipBtn);

    // Snippet visible
    expect(screen.getByTestId("source-snippet-101")).toBeInTheDocument();
    expect(
      screen.getByText(/Deep learning models scale with compute/i)
    ).toBeInTheDocument();

    // Click again to collapse
    fireEvent.click(chipBtn);
    expect(screen.queryByTestId("source-snippet-101")).not.toBeInTheDocument();
  });

  it("renders session sidebar with document scopes and triggers callbacks", () => {
    const mockSessions: ChatSessionItem[] = [
      {
        id: 1,
        user_id: 1,
        document_id: null,
        title: "Global Chat",
        created_at: "2026-09-28T10:00:00Z",
        updated_at: "2026-09-28T10:00:00Z",
      },
      {
        id: 2,
        user_id: 1,
        document_id: 5,
        title: "Doc Scoped Chat",
        created_at: "2026-09-28T10:05:00Z",
        updated_at: "2026-09-28T10:05:00Z",
      },
    ];

    const mockDocs: DocumentItem[] = [
      {
        id: 5,
        user_id: 1,
        filename: "manual.pdf",
        mime_type: "application/pdf",
        size_bytes: 1024,
        page_count: 3,
        chunk_count: 6,
        status: "ready",
        error_message: null,
        created_at: "2026-09-28T09:00:00Z",
        updated_at: "2026-09-28T09:05:00Z",
      },
    ];

    const handleSelect = vi.fn();
    const handleNew = vi.fn();
    const handleDelete = vi.fn();

    render(
      <SessionSidebar
        sessions={mockSessions}
        activeSessionId={1}
        onSelectSession={handleSelect}
        onNewChat={handleNew}
        onDeleteSession={handleDelete}
        documents={mockDocs}
      />
    );

    expect(screen.getByText("Global Chat")).toBeInTheDocument();
    expect(screen.getByText("Doc Scoped Chat")).toBeInTheDocument();
    expect(screen.getByText("All Docs")).toBeInTheDocument();
    expect(screen.getAllByText("manual.pdf").length).toBe(2);

    // New chat button
    const newChatBtn = screen.getByTestId("new-chat-button");
    fireEvent.click(newChatBtn);
    expect(handleNew).toHaveBeenCalled();

    // Select session
    const sessionItem = screen.getByTestId("session-item-2");
    fireEvent.click(sessionItem);
    expect(handleSelect).toHaveBeenCalledWith(2);

    // Delete session
    const deleteBtn = screen.getByTestId("delete-session-1");
    fireEvent.click(deleteBtn);
    expect(handleDelete).toHaveBeenCalledWith(1);
  });

  it("handles ChatWindow empty state and message sending", () => {
    const handleSend = vi.fn();

    render(
      <ChatWindow
        messages={[]}
        isLoadingMessages={false}
        isSending={false}
        onSendMessage={handleSend}
        scopeTitle="All Documents"
      />
    );

    expect(
      screen.getByText("Ask your documents anything")
    ).toBeInTheDocument();

    const input = screen.getByTestId("chat-input");
    fireEvent.change(input, { target: { value: "Tell me about quantum theory" } });

    const sendBtn = screen.getByTestId("send-message-button");
    fireEvent.click(sendBtn);

    expect(handleSend).toHaveBeenCalledWith("Tell me about quantum theory");
  });

  it("renders cancel button and triggers onCancelStream when streaming", () => {
    const handleSend = vi.fn();
    const handleCancel = vi.fn();

    render(
      <ChatWindow
        messages={[]}
        isLoadingMessages={false}
        isSending={true}
        onSendMessage={handleSend}
        onCancelStream={handleCancel}
        scopeTitle="All Documents"
      />
    );

    const cancelBtn = screen.getByTestId("cancel-stream-button");
    expect(cancelBtn).toBeInTheDocument();
    fireEvent.click(cancelBtn);
    expect(handleCancel).toHaveBeenCalledTimes(1);
  });
});
