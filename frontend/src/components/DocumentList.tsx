import React, { useState } from "react";
import { Link } from "react-router-dom";
import {
  FileText,
  Trash2,
  MessageSquare,
  AlertCircle,
  Clock,
  Loader2,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { DocumentItem } from "../api/documents";

interface DocumentListProps {
  documents: DocumentItem[];
  onDeleteDocument: (id: number) => Promise<void>;
  isLoading?: boolean;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  onDeleteDocument,
  isLoading = false,
}) => {
  const [docToDelete, setDocToDelete] = useState<DocumentItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return "-";
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  const renderStatusBadge = (doc: DocumentItem) => {
    switch (doc.status) {
      case "pending":
        return (
          <span
            data-testid={`status-${doc.id}`}
            className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200"
          >
            <Clock className="w-3 h-3 text-amber-600" />
            <span>Pending</span>
          </span>
        );
      case "processing":
        return (
          <span
            data-testid={`status-${doc.id}`}
            className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-apple-blue border border-blue-200"
          >
            <Loader2 className="w-3 h-3 animate-spin text-apple-blue" />
            <span>Processing...</span>
          </span>
        );
      case "ready":
        return (
          <span
            data-testid={`status-${doc.id}`}
            className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-800 border border-emerald-200"
          >
            <CheckCircle className="w-3 h-3 text-emerald-600" />
            <span>Ready</span>
          </span>
        );
      case "failed":
        return (
          <div className="relative group inline-block">
            <span
              data-testid={`status-${doc.id}`}
              className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-800 border border-rose-200 cursor-help"
            >
              <XCircle className="w-3 h-3 text-rose-600" />
              <span>Failed</span>
            </span>
            {doc.error_message && (
              <div className="absolute left-0 bottom-full mb-1 hidden group-hover:block z-20 w-64 p-2 bg-neutral-900 text-white text-[11px] rounded-lg shadow-lg pointer-events-none">
                {doc.error_message}
              </div>
            )}
          </div>
        );
      default:
        return null;
    }
  };

  const confirmDelete = async () => {
    if (!docToDelete) return;
    setIsDeleting(true);
    try {
      await onDeleteDocument(docToDelete.id);
      setDocToDelete(null);
    } finally {
      setIsDeleting(false);
    }
  };

  if (isLoading && documents.length === 0) {
    return (
      <div data-testid="document-list-skeleton" className="bg-white border border-apple-hairline rounded-2xl overflow-hidden shadow-sm animate-pulse">
        <div className="p-4 border-b border-apple-hairline bg-apple-parchment/60 flex items-center justify-between">
          <div className="h-4 bg-neutral-200 rounded-pill w-32" />
          <div className="h-4 bg-neutral-200 rounded-pill w-16" />
        </div>
        <div className="divide-y divide-apple-hairline p-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="py-3.5 px-4 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 flex-1">
                <div className="w-8 h-8 rounded-lg bg-neutral-200 shrink-0" />
                <div className="space-y-1.5 flex-1 max-w-sm">
                  <div className="h-3.5 bg-neutral-200 rounded-pill w-3/4" />
                  <div className="h-2.5 bg-neutral-100 rounded-pill w-1/3" />
                </div>
              </div>
              <div className="h-5 bg-neutral-200 rounded-full w-20 shrink-0" />
              <div className="h-4 bg-neutral-100 rounded-pill w-12 shrink-0 hidden sm:block" />
              <div className="h-7 bg-neutral-200 rounded-pill w-16 shrink-0" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="bg-white border border-apple-hairline rounded-2xl p-8 sm:p-12 text-center space-y-4 shadow-sm">
        <div className="w-14 h-14 bg-apple-parchment border border-apple-hairline text-apple-blue rounded-full flex items-center justify-center mx-auto shadow-sm">
          <FileText className="w-7 h-7" />
        </div>
        <div className="space-y-1">
          <p className="text-base font-semibold text-apple-ink">No documents in your library</p>
          <p className="text-xs sm:text-sm text-neutral-500 max-w-md mx-auto">
            Drag & drop PDF, TXT, or Markdown documents above. Once parsed and embedded, you can query them with exact citations.
          </p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="bg-white border border-apple-hairline rounded-2xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs md:text-sm">
            <thead>
              <tr className="border-b border-apple-hairline bg-apple-parchment/60 text-apple-muted-48 text-[11px] uppercase tracking-wider">
                <th className="py-3 px-4 font-semibold">Document</th>
                <th className="py-3 px-4 font-semibold">Status</th>
                <th className="py-3 px-4 font-semibold">Chunks</th>
                <th className="py-3 px-4 font-semibold">Size</th>
                <th className="py-3 px-4 font-semibold">Uploaded</th>
                <th className="py-3 px-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-apple-hairline">
              {documents.map((doc) => (
                <tr
                  key={doc.id}
                  data-testid={`document-row-${doc.id}`}
                  className="hover:bg-apple-parchment/40 transition-colors"
                >
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2.5">
                      <FileText className="w-4 h-4 text-apple-blue shrink-0" />
                      <span className="font-medium text-apple-ink truncate max-w-xs md:max-w-md">
                        {doc.filename}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-4">{renderStatusBadge(doc)}</td>
                  <td className="py-3 px-4 text-apple-ink">
                    {doc.status === "ready" ? doc.chunk_count : "-"}
                  </td>
                  <td className="py-3 px-4 text-apple-muted-48">
                    {formatBytes(doc.size_bytes)}
                  </td>
                  <td className="py-3 px-4 text-apple-muted-48 whitespace-nowrap">
                    {formatDate(doc.created_at)}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {doc.status === "ready" && (
                        <Link
                          to={`/chat?doc=${doc.id}`}
                          className="inline-flex items-center gap-1 px-3 py-1 bg-apple-blue hover:bg-apple-primary-focus text-white rounded-pill text-xs font-medium transition-colors"
                        >
                          <MessageSquare className="w-3 h-3" />
                          <span>Chat</span>
                        </Link>
                      )}
                      <button
                        onClick={() => setDocToDelete(doc)}
                        data-testid={`delete-btn-${doc.id}`}
                        title="Delete document"
                        className="p-1.5 text-neutral-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {docToDelete && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm transition-opacity"
        >
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 space-y-4 shadow-xl border border-apple-hairline">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center shrink-0">
                <AlertCircle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-apple-ink">
                  Delete Document?
                </h3>
                <p className="text-xs text-apple-muted-48">
                  This action cannot be undone.
                </p>
              </div>
            </div>

            <p className="text-xs text-neutral-600">
              Are you sure you want to delete{" "}
              <strong className="text-apple-ink">"{docToDelete.filename}"</strong>?
              All associated chunks and vector embeddings will be permanently removed.
            </p>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setDocToDelete(null)}
                disabled={isDeleting}
                className="px-4 py-1.5 rounded-pill text-xs font-medium text-apple-ink bg-apple-parchment hover:bg-neutral-200 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDelete}
                disabled={isDeleting}
                data-testid="confirm-delete-button"
                className="px-4 py-1.5 rounded-pill text-xs font-medium text-white bg-rose-600 hover:bg-rose-700 transition-colors flex items-center gap-1.5"
              >
                {isDeleting && <Loader2 className="w-3 h-3 animate-spin" />}
                <span>Delete</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
