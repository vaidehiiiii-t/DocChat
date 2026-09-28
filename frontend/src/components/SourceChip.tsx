import React, { useState } from "react";
import { FileText, ChevronDown, ChevronUp } from "lucide-react";
import { ChatSource } from "../api/chat";

interface SourceChipProps {
  source: ChatSource;
  index: number;
}

export const SourceChip: React.FC<SourceChipProps> = ({ source, index }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  // Trim long filenames nicely
  const displayName = source.filename.replace(/\.[^/.]+$/, ""); // strip extension

  return (
    <div className="inline-block text-left">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-blue-50 hover:bg-blue-100 border border-blue-200/70 text-apple-blue transition-all cursor-pointer"
        data-testid={`source-chip-${source.chunk_id}`}
      >
        {/* Citation number badge */}
        <span className="w-4 h-4 rounded-full bg-apple-blue text-white font-bold flex items-center justify-center text-[9px] shrink-0">
          {index}
        </span>
        <FileText className="w-3 h-3 shrink-0" />
        <span className="font-medium truncate max-w-[150px]">{displayName}</span>
        <span className="text-blue-400">· p.{source.page}</span>
        {isExpanded ? (
          <ChevronUp className="w-3 h-3 ml-0.5 shrink-0" />
        ) : (
          <ChevronDown className="w-3 h-3 ml-0.5 shrink-0" />
        )}
      </button>

      {/* Expanded snippet */}
      {isExpanded && (
        <div
          data-testid={`source-snippet-${source.chunk_id}`}
          className="mt-1.5 p-3 bg-blue-50/50 border border-blue-100 rounded-xl text-xs text-neutral-700 shadow-sm max-w-sm animate-in fade-in duration-150"
        >
          <p className="text-[10px] text-apple-muted-48 font-medium mb-1.5">
            From {source.filename} — page {source.page}
          </p>
          <p className="leading-relaxed whitespace-pre-wrap text-neutral-800">
            {source.snippet}
          </p>
        </div>
      )}
    </div>
  );
};
