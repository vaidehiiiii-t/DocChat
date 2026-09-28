import { apiClient } from "./client";

export interface DocumentItem {
  id: number;
  user_id: number;
  filename: string;
  mime_type: string;
  size_bytes: number;
  page_count: number | null;
  chunk_count: number;
  status: "pending" | "processing" | "ready" | "failed";
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export const getDocumentsApi = async (): Promise<DocumentItem[]> => {
  const res = await apiClient.get<DocumentItem[]>("/documents");
  return res.data;
};

export const getDocumentApi = async (id: number): Promise<DocumentItem> => {
  const res = await apiClient.get<DocumentItem>(`/documents/${id}`);
  return res.data;
};

export const uploadDocumentApi = async (
  file: File,
  onUploadProgress?: (progressEvent: { loaded: number; total?: number }) => void
): Promise<DocumentItem> => {
  const formData = new FormData();
  formData.append("file", file);

  const res = await apiClient.post<DocumentItem>("/documents", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    onUploadProgress: (progressEvent) => {
      if (onUploadProgress && progressEvent.total) {
        onUploadProgress({ loaded: progressEvent.loaded, total: progressEvent.total });
      }
    },
  });

  return res.data;
};

export const deleteDocumentApi = async (id: number): Promise<{ message: string }> => {
  const res = await apiClient.delete<{ message: string }>(`/documents/${id}`);
  return res.data;
};
