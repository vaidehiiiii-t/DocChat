import React from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { LogOut, MessageSquare, Files, RefreshCw } from "lucide-react";

import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { getDocumentsApi, deleteDocumentApi, DocumentItem } from "../api/documents";
import { UploadDropzone } from "../components/UploadDropzone";
import { DocumentList } from "../components/DocumentList";

export const Documents: React.FC = () => {
  const { user, logout } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();

  // Query documents with conditional polling
  const { data: documents = [], isLoading, isFetching } = useQuery<DocumentItem[]>({
    queryKey: ["documents"],
    queryFn: getDocumentsApi,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const hasUnfinished = data.some(
        (doc) => doc.status === "pending" || doc.status === "processing"
      );
      // Auto-poll every 2 seconds if any document is processing
      return hasUnfinished ? 2000 : false;
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: deleteDocumentApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast.success("Document removed successfully.");
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.error?.message || "Failed to delete document.");
    },
  });

  const handleUploadSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ["documents"] });
    toast.success("Document uploaded successfully. Processing started.");
  };

  const handleDelete = async (id: number) => {
    await deleteMutation.mutateAsync(id);
  };

  const totalChunks = documents.reduce((sum, d) => sum + (d.chunk_count || 0), 0);
  const readyCount = documents.filter((d) => d.status === "ready").length;

  return (
    <div className="min-h-screen bg-apple-parchment flex flex-col font-sans">
      {/* Global Apple-styled Nav Bar */}
      <header className="bg-black text-white h-11 px-3 sm:px-6 flex items-center justify-between text-xs sticky top-0 z-40 backdrop-blur-md">
        <div className="flex items-center gap-4 sm:gap-6">
          <Link to="/documents" className="font-semibold tracking-tight text-sm flex items-center gap-1.5 sm:gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-apple-blue inline-block shrink-0" />
            <span>DocChat</span>
          </Link>
          <nav className="flex items-center gap-3 sm:gap-4 text-neutral-400">
            <Link to="/documents" className="text-white hover:text-white transition-colors">
              Documents
            </Link>
            <Link to="/chat" className="hover:text-white transition-colors flex items-center gap-1">
              <MessageSquare className="w-3 h-3" />
              <span>Chat</span>
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-2 sm:gap-4">
          <span className="text-neutral-400 text-[11px] hidden md:inline truncate max-w-[150px]">
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

      {/* Main Workspace */}
      <main className="flex-1 max-w-5xl w-full mx-auto p-4 sm:p-6 md:p-8 space-y-6 sm:space-y-8">
        {/* Page Title & Stats */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl md:text-3xl font-semibold tracking-tight text-apple-ink">
              Knowledge Base
            </h1>
            <p className="text-xs md:text-sm text-neutral-500 mt-1">
              Upload documents to parse, embed, and query with verified source citations.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-apple-hairline rounded-xl text-xs text-apple-ink shadow-sm">
              <Files className="w-3.5 h-3.5 text-apple-blue" />
              <span>
                <strong>{documents.length}</strong> {documents.length === 1 ? "doc" : "docs"} ·{" "}
                <strong>{totalChunks}</strong> chunks
              </span>
            </div>

            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ["documents"] })}
              title="Refresh document status"
              className="p-2 bg-white hover:bg-neutral-50 border border-apple-hairline rounded-xl text-neutral-600 transition-colors shadow-sm"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin text-apple-blue" : ""}`} />
            </button>

            {readyCount > 0 && (
              <Link
                to="/chat"
                className="inline-flex items-center gap-1.5 px-3.5 sm:px-4 py-1.5 bg-apple-blue hover:bg-apple-primary-focus text-white rounded-pill text-xs font-medium transition-colors shadow-sm"
              >
                <MessageSquare className="w-3.5 h-3.5" />
                <span>Go to Chat</span>
              </Link>
            )}
          </div>
        </div>

        {/* Upload Dropzone */}
        <section className="space-y-2">
          <h2 className="text-xs font-semibold text-apple-muted-48 uppercase tracking-wider">
            Upload Document
          </h2>
          <UploadDropzone onUploadSuccess={handleUploadSuccess} />
        </section>

        {/* Documents Table */}
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold text-apple-muted-48 uppercase tracking-wider">
              Indexed Documents
            </h2>
          </div>
          <DocumentList
            documents={documents}
            onDeleteDocument={handleDelete}
            isLoading={isLoading}
          />
        </section>
      </main>

      {/* Footer */}
      <footer className="text-center py-5 text-xs text-apple-muted-48 border-t border-apple-hairline/60 bg-white/50">
        DocChat · Strict User & Document Isolation
      </footer>
    </div>
  );
};

export default Documents;
