import React, { useState, useRef } from "react";
import { UploadCloud, AlertCircle, ShieldAlert, CheckCircle2 } from "lucide-react";
import { uploadDocumentApi, DocumentItem } from "../api/documents";

interface UploadDropzoneProps {
  onUploadSuccess: (doc: DocumentItem) => void;
}

const MAX_BYTES = 20 * 1024 * 1024; // 20 MB
const ALLOWED_EXTENSIONS = [".pdf", ".txt", ".md"];

export const UploadDropzone: React.FC<UploadDropzoneProps> = ({ onUploadSuccess }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndUpload = async (file: File) => {
    setErrorMsg(null);
    setSuccessMsg(null);

    // 1. Extension check
    const lowerName = file.name.toLowerCase();
    const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
    if (!hasValidExt) {
      setErrorMsg(`Unsupported file type. Please upload a PDF, TXT, or MD document.`);
      return;
    }

    // 2. Size check
    if (file.size === 0) {
      setErrorMsg("File is empty (0 bytes).");
      return;
    }
    if (file.size > MAX_BYTES) {
      setErrorMsg("File size exceeds 20 MB limit.");
      return;
    }

    // 3. Upload
    setIsUploading(true);
    setUploadProgress(0);

    try {
      const doc = await uploadDocumentApi(file, (progress) => {
        if (progress.total) {
          const pct = Math.round((progress.loaded / progress.total) * 100);
          setUploadProgress(pct);
        }
      });
      setSuccessMsg(`"${file.name}" uploaded successfully. Indexing started.`);
      onUploadSuccess(doc);
    } catch (err: any) {
      const apiMsg =
        err.response?.data?.error?.message || err.message || "Failed to upload document.";
      setErrorMsg(apiMsg);
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndUpload(e.target.files[0]);
    }
  };

  return (
    <div className="space-y-3">
      <div
        data-testid="upload-dropzone"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-2xl p-8 md:p-10 text-center cursor-pointer transition-all duration-200 ${
          isDragging
            ? "border-apple-blue bg-blue-50/50 scale-[1.005]"
            : "border-apple-hairline bg-white hover:border-neutral-300"
        } ${isUploading ? "opacity-75 cursor-not-allowed" : ""}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.md"
          className="hidden"
          onChange={handleFileChange}
          disabled={isUploading}
          data-testid="file-input"
        />

        <div className="flex flex-col items-center justify-center space-y-3">
          <div
            className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${
              isDragging
                ? "bg-apple-blue text-white"
                : "bg-apple-parchment text-apple-ink"
            }`}
          >
            {isUploading ? (
              <div className="w-5 h-5 border-2 border-apple-blue border-t-transparent rounded-full animate-spin" />
            ) : (
              <UploadCloud className="w-6 h-6" />
            )}
          </div>

          <div>
            <p className="text-sm md:text-base font-medium text-apple-ink">
              {isUploading
                ? "Uploading document..."
                : isDragging
                ? "Drop document here"
                : "Click to upload or drag and drop"}
            </p>
            <p className="text-xs text-apple-muted-48 mt-1">
              PDF, TXT, or MD · Max 20 MB
            </p>
          </div>

          {/* Upload Progress Bar */}
          {isUploading && (
            <div className="w-full max-w-xs mt-3 space-y-1">
              <div className="w-full bg-apple-parchment rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-apple-blue h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <span className="text-[11px] text-apple-muted-48">{uploadProgress}%</span>
            </div>
          )}
        </div>
      </div>

      {/* Error Feedback */}
      {errorMsg && (
        <div
          role="alert"
          className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700"
        >
          <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Success Feedback */}
      {successMsg && (
        <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-700">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Privacy Notice per Section 11 */}
      <div className="flex items-center gap-2 px-3 py-2 bg-amber-50/70 border border-amber-200/60 rounded-xl text-[11px] text-amber-900/80">
        <ShieldAlert className="w-3.5 h-3.5 shrink-0 text-amber-700" />
        <span>
          <strong>Privacy Notice:</strong> Document excerpts are sent to a third-party AI provider. Do not upload confidential files.
        </span>
      </div>
    </div>
  );
};
