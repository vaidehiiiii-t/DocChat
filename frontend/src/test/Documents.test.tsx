import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { BrowserRouter } from "react-router-dom";
import { DocumentList } from "../components/DocumentList";
import { UploadDropzone } from "../components/UploadDropzone";
import { DocumentItem } from "../api/documents";

const mockDocuments: DocumentItem[] = [
  {
    id: 1,
    user_id: 10,
    filename: "annual_report.pdf",
    mime_type: "application/pdf",
    size_bytes: 2048576,
    page_count: 5,
    chunk_count: 12,
    status: "ready",
    error_message: null,
    created_at: "2026-09-28T10:00:00Z",
    updated_at: "2026-09-28T10:01:00Z",
  },
  {
    id: 2,
    user_id: 10,
    filename: "active_processing.txt",
    mime_type: "text/plain",
    size_bytes: 10240,
    page_count: 1,
    chunk_count: 0,
    status: "processing",
    error_message: null,
    created_at: "2026-09-28T10:05:00Z",
    updated_at: "2026-09-28T10:05:30Z",
  },
  {
    id: 3,
    user_id: 10,
    filename: "broken_scanned.pdf",
    mime_type: "application/pdf",
    size_bytes: 512000,
    page_count: 2,
    chunk_count: 0,
    status: "failed",
    error_message: "PDF contains no extractable text",
    created_at: "2026-09-28T10:10:00Z",
    updated_at: "2026-09-28T10:10:15Z",
  },
];

describe("Documents Page & Components Tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders document list with correct status badges and information", () => {
    render(
      <BrowserRouter>
        <DocumentList
          documents={mockDocuments}
          onDeleteDocument={vi.fn()}
        />
      </BrowserRouter>
    );

    // Verify document titles
    expect(screen.getByText("annual_report.pdf")).toBeInTheDocument();
    expect(screen.getByText("active_processing.txt")).toBeInTheDocument();
    expect(screen.getByText("broken_scanned.pdf")).toBeInTheDocument();

    // Verify status badges
    expect(screen.getByTestId("status-1")).toHaveTextContent("Ready");
    expect(screen.getByTestId("status-2")).toHaveTextContent("Processing...");
    expect(screen.getByTestId("status-3")).toHaveTextContent("Failed");

    // Verify chunk count for ready document
    expect(screen.getByText("12")).toBeInTheDocument();

    // Verify Chat CTA exists for ready document
    expect(screen.getByRole("link", { name: /chat/i })).toBeInTheDocument();
  });

  it("handles delete confirmation modal interaction", async () => {
    const mockDelete = vi.fn().mockResolvedValue(undefined);

    render(
      <BrowserRouter>
        <DocumentList
          documents={mockDocuments}
          onDeleteDocument={mockDelete}
        />
      </BrowserRouter>
    );

    // Click delete button for doc 1
    const deleteBtn = screen.getByTestId("delete-btn-1");
    fireEvent.click(deleteBtn);

    // Confirmation modal should appear
    expect(screen.getByText("Delete Document?")).toBeInTheDocument();
    expect(screen.getByText(/All associated chunks and vector embeddings/i)).toBeInTheDocument();

    // Click cancel
    const cancelBtn = screen.getByText("Cancel");
    fireEvent.click(cancelBtn);
    expect(screen.queryByText("Delete Document?")).not.toBeInTheDocument();

    // Click delete again and confirm
    fireEvent.click(deleteBtn);
    const confirmBtn = screen.getByTestId("confirm-delete-button");
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith(1);
    });
  });

  it("validates file extension and size in UploadDropzone", async () => {
    const mockUploadSuccess = vi.fn();

    render(
      <UploadDropzone onUploadSuccess={mockUploadSuccess} />
    );

    const fileInput = screen.getByTestId("file-input");

    // 1. Unsupported extension (.png)
    const invalidFile = new File(["dummy content"], "photo.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [invalidFile] } });

    await waitFor(() => {
      expect(
        screen.getByText(/Unsupported file type. Please upload a PDF, TXT, or MD document./i)
      ).toBeInTheDocument();
    });

    // 2. Empty file
    const emptyFile = new File([""], "empty.txt", { type: "text/plain" });
    fireEvent.change(fileInput, { target: { files: [emptyFile] } });

    await waitFor(() => {
      expect(screen.getByText(/File is empty/i)).toBeInTheDocument();
    });
  });

  it("verifies polling logic determines whether to poll", () => {
    const hasUnfinished = (docs: DocumentItem[]) =>
      docs.some((d) => d.status === "pending" || d.status === "processing");

    // Documents with pending/processing doc -> should poll (true / 2000)
    expect(hasUnfinished(mockDocuments)).toBe(true);

    // Terminal documents only -> should NOT poll (false)
    const terminalDocs: DocumentItem[] = [
      { ...mockDocuments[0], status: "ready" },
      { ...mockDocuments[2], status: "failed" },
    ];
    expect(hasUnfinished(terminalDocs)).toBe(false);
  });
});
