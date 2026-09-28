import React, { useState, useRef, useEffect } from "react";
import { Send, Loader2, Sparkles, MessageSquare, Square } from "lucide-react";
import { ChatMessageItem } from "../api/chat";
import { MessageBubble } from "./MessageBubble";

interface ChatWindowProps {
  messages: ChatMessageItem[];
  isLoadingMessages: boolean;
  isSending: boolean;
  onSendMessage: (content: string) => void;
  onCancelStream?: () => void;
  scopeTitle?: string;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({
  messages,
  isLoadingMessages,
  isSending,
  onSendMessage,
  onCancelStream,
  scopeTitle = "All Documents",
}) => {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isSending) return;
    onSendMessage(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-44px)] bg-apple-parchment">
      {/* Scope Sub-Header */}
      <div className="h-10 px-6 bg-white/70 backdrop-blur-md border-b border-apple-hairline flex items-center justify-between text-xs text-apple-muted-48">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-apple-ink">Scope:</span>
          <span className="bg-apple-parchment px-2 py-0.5 rounded-full border border-apple-hairline text-apple-ink font-medium">
            {scopeTitle}
          </span>
        </div>
        <span className="text-[11px]">Citations strictly grounded</span>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
        {isLoadingMessages ? (
          <div data-testid="chat-loading-skeleton" className="space-y-4 max-w-2xl mx-auto py-6 animate-pulse">
            <div className="flex justify-end">
              <div className="h-10 bg-blue-100/70 rounded-2xl w-48" />
            </div>
            <div className="flex justify-start">
              <div className="space-y-2 bg-white border border-apple-hairline rounded-2xl p-4 w-72 shadow-sm">
                <div className="h-3.5 bg-neutral-200 rounded-pill w-3/4" />
                <div className="h-3 bg-neutral-200 rounded-pill w-1/2" />
                <div className="h-2.5 bg-neutral-100 rounded-pill w-5/6" />
              </div>
            </div>
            <div className="flex justify-end">
              <div className="h-10 bg-blue-100/70 rounded-2xl w-36" />
            </div>
          </div>
        ) : messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-4">
            <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center text-apple-blue border border-apple-hairline shadow-sm">
              <MessageSquare className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-apple-ink">
                Ask your documents anything
              </h3>
              <p className="text-xs text-apple-muted-48 mt-1 leading-relaxed">
                Answers are generated strictly from indexed chunks with inline source citations.
              </p>
            </div>
            <div className="w-full grid grid-cols-1 gap-2 pt-2 text-xs">
              <button
                type="button"
                onClick={() => setInput("What are the key points in the document?")}
                className="p-2.5 bg-white border border-apple-hairline rounded-xl text-left text-neutral-600 hover:border-apple-blue/50 hover:bg-blue-50/20 transition-all"
              >
                💡 "What are the key points in the document?"
              </button>
              <button
                type="button"
                onClick={() => setInput("Summarize the main conclusions.")}
                className="p-2.5 bg-white border border-apple-hairline rounded-xl text-left text-neutral-600 hover:border-apple-blue/50 hover:bg-blue-50/20 transition-all"
              >
                📝 "Summarize the main conclusions."
              </button>
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {/* Thinking / Streaming Indicator */}
            {isSending && (
              <div className="flex items-center gap-2.5 p-3.5 bg-white border border-apple-hairline rounded-2xl max-w-sm shadow-sm animate-pulse text-xs text-apple-muted-48">
                <Sparkles className="w-4 h-4 text-apple-blue animate-spin" />
                <span>Searching knowledge base and thinking...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Chat Input Bar */}
      <div className="p-4 bg-white border-t border-apple-hairline">
        <form
          onSubmit={handleSubmit}
          className="max-w-4xl mx-auto flex items-end gap-2 bg-apple-parchment rounded-2xl p-2 border border-apple-hairline focus-within:border-apple-blue/70 transition-all shadow-inner"
        >
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSending}
            placeholder={
              isSending
                ? "Waiting for response..."
                : "Ask a question about your documents... (Press Enter to send, Shift+Enter for newline)"
            }
            maxLength={2000}
            data-testid="chat-input"
            className="flex-1 bg-transparent px-3 py-1.5 text-xs md:text-sm text-apple-ink focus:outline-none resize-none max-h-32 placeholder:text-apple-muted-48"
          />

          {isSending && onCancelStream ? (
            <button
              type="button"
              onClick={onCancelStream}
              data-testid="cancel-stream-button"
              title="Stop generating"
              className="p-2 bg-neutral-800 hover:bg-neutral-900 text-white rounded-xl transition-all cursor-pointer shrink-0 shadow-sm flex items-center justify-center"
            >
              <Square className="w-4 h-4 fill-white" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim() || isSending}
              data-testid="send-message-button"
              className="p-2 bg-apple-blue hover:bg-apple-primary-focus disabled:bg-neutral-300 text-white rounded-xl transition-all disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed shrink-0"
            >
              {isSending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          )}
        </form>

        <div className="flex justify-between items-center max-w-4xl mx-auto pt-1.5 px-2 text-[10px] text-apple-muted-48">
          <span>AI answers may occasionally hallucinate. Verify with cited sources.</span>
          <span>{input.length} / 2000</span>
        </div>
      </div>
    </div>
  );
};
