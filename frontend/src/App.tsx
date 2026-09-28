import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { Documents } from "./pages/Documents";
import { Chat } from "./pages/Chat";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "./api/client";
import { CheckCircle2, AlertCircle, RefreshCw, Database, Server, Cpu } from "lucide-react";

interface HealthResponse {
  status: string;
  db: string;
  vector_store: string;
}

function HealthPage() {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: async () => {
      const res = await apiClient.get<HealthResponse>("/health");
      return res.data;
    },
    refetchInterval: 10000,
  });

  return (
    <div className="min-h-screen bg-apple-parchment flex flex-col justify-between">
      <header className="bg-black text-white h-11 px-6 flex items-center justify-between text-xs">
        <span className="font-semibold tracking-tight text-sm">DocChat</span>
        <span className="text-neutral-400">System Health</span>
      </header>

      <main className="flex-1 flex items-center justify-center p-6">
        <div className="max-w-xl w-full bg-white border border-apple-hairline rounded-2xl p-6 shadow-sm space-y-5">
          <div className="flex items-center justify-between border-b border-apple-hairline pb-4">
            <div>
              <h2 className="text-base font-semibold text-apple-ink">System Status</h2>
              <p className="text-xs text-neutral-500">Live Health Check</p>
            </div>
            <button
              onClick={() => refetch()}
              disabled={isFetching}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-pill text-xs font-medium bg-neutral-100 hover:bg-neutral-200 text-apple-ink transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
              <span>Refresh</span>
            </button>
          </div>

          {isLoading ? (
            <div className="py-8 flex flex-col items-center justify-center space-y-2 text-neutral-500">
              <RefreshCw className="w-6 h-6 animate-spin text-apple-blue" />
              <span className="text-sm">Connecting to backend...</span>
            </div>
          ) : isError ? (
            <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="font-semibold">Backend Unreachable</p>
                <p className="text-xs text-red-600 mt-1">
                  {(error as Error)?.message || "Failed to fetch health check from /api/health"}
                </p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-3.5 rounded-xl bg-apple-parchment border border-neutral-200/60 flex flex-col justify-between space-y-2">
                <div className="flex items-center gap-2 text-neutral-600 text-xs font-medium">
                  <Server className="w-4 h-4 text-apple-blue" />
                  <span>API Server</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span className="text-sm font-semibold text-emerald-700 capitalize">
                    {data?.status}
                  </span>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-apple-parchment border border-neutral-200/60 flex flex-col justify-between space-y-2">
                <div className="flex items-center gap-2 text-neutral-600 text-xs font-medium">
                  <Database className="w-4 h-4 text-apple-blue" />
                  <span>TiDB Cloud</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {data?.db === "ok" ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <span className="text-sm font-semibold text-emerald-700">Connected</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-4 h-4 text-red-600" />
                      <span className="text-sm font-semibold text-red-700">Error</span>
                    </>
                  )}
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-apple-parchment border border-neutral-200/60 flex flex-col justify-between space-y-2">
                <div className="flex items-center gap-2 text-neutral-600 text-xs font-medium">
                  <Cpu className="w-4 h-4 text-apple-blue" />
                  <span>ChromaDB</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {data?.vector_store === "ok" ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <span className="text-sm font-semibold text-emerald-700">Connected</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-4 h-4 text-red-600" />
                      <span className="text-sm font-semibold text-red-700">{data?.vector_store || "Disconnected"}</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      <footer className="text-center py-4 text-xs text-apple-muted-48">
        DocChat · Strict User Isolation
      </footer>
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/documents"
            element={
              <ProtectedRoute>
                <Documents />
              </ProtectedRoute>
            }
          />
          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <Chat />
              </ProtectedRoute>
            }
          />
          <Route path="/health" element={<HealthPage />} />
          <Route path="/" element={<Navigate to="/documents" replace />} />
          <Route path="*" element={<Navigate to="/documents" replace />} />
        </Routes>
      </ToastProvider>
    </AuthProvider>
  );
}

export default App;
