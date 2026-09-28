import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, User, Sparkles } from "lucide-react";
import { ChatMessageItem } from "../api/chat";
import { SourceChip } from "./SourceChip";

interface MessageBubbleProps {
  message: ChatMessageItem;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end gap-2.5 my-3" data-testid="user-message">
        <div className="max-w-xl bg-apple-blue text-white rounded-2xl rounded-tr-sm px-4 py-2.5 shadow-sm text-sm leading-relaxed">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
        <div className="w-7 h-7 rounded-full bg-neutral-200 text-neutral-600 flex items-center justify-center shrink-0 mt-0.5">
          <User className="w-4 h-4" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start gap-3 my-4" data-testid="assistant-message">
      <div className="w-7 h-7 rounded-full bg-apple-blue text-white flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
        <Bot className="w-4 h-4" />
      </div>

      <div className="max-w-2xl w-full bg-white border border-apple-hairline rounded-2xl rounded-tl-sm p-4 shadow-sm space-y-3">
        {/* Markdown content */}
        <div
          className="
            prose prose-sm max-w-none text-apple-ink
            prose-headings:font-semibold prose-headings:text-apple-ink prose-headings:mt-4 prose-headings:mb-1
            prose-h1:text-base prose-h2:text-sm prose-h3:text-sm
            prose-p:text-sm prose-p:leading-relaxed prose-p:my-1.5
            prose-ul:my-2 prose-ul:pl-5 prose-ul:list-disc
            prose-ol:my-2 prose-ol:pl-5 prose-ol:list-decimal
            prose-li:text-sm prose-li:my-0.5 prose-li:leading-relaxed
            prose-strong:font-semibold prose-strong:text-apple-ink
            prose-em:italic prose-em:text-apple-ink
            prose-code:text-[12px] prose-code:bg-neutral-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:font-mono prose-code:text-neutral-700 prose-code:before:content-none prose-code:after:content-none
            prose-pre:bg-neutral-900 prose-pre:text-neutral-100 prose-pre:rounded-xl prose-pre:p-4 prose-pre:overflow-x-auto prose-pre:text-[12px] prose-pre:my-3
            prose-blockquote:border-l-4 prose-blockquote:border-apple-blue/40 prose-blockquote:pl-4 prose-blockquote:italic prose-blockquote:text-apple-muted-48 prose-blockquote:my-3
            prose-table:text-xs prose-table:w-full prose-table:border-collapse
            prose-th:bg-neutral-50 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:font-semibold prose-th:text-apple-ink prose-th:border prose-th:border-neutral-200
            prose-td:px-3 prose-td:py-2 prose-td:border prose-td:border-neutral-200 prose-td:align-top
            prose-a:text-apple-blue prose-a:underline prose-a:underline-offset-2 hover:prose-a:opacity-70
            prose-hr:border-apple-hairline prose-hr:my-4
          "
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Source chips below message */}
        {message.sources && message.sources.length > 0 && (
          <div className="pt-2 border-t border-apple-hairline/60 space-y-1.5">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-apple-muted-48 uppercase tracking-wider">
              <Sparkles className="w-3 h-3 text-apple-blue" />
              <span>Sources ({message.sources.length})</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {message.sources.map((src, idx) => (
                <SourceChip key={`${src.chunk_id}-${idx}`} source={src} index={idx + 1} />
              ))}
            </div>
          </div>
        )}


      </div>
    </div>
  );
};
