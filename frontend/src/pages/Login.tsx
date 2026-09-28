import React, { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ArrowRight, Loader2, Lock, Mail, AlertCircle, Sparkles } from "lucide-react";
import axios from "axios";
import { TestimonialCarousel } from "../components/TestimonialCarousel";

export function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/documents";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!email.trim() || !password) {
      setErrorMsg("Please enter both email and password.");
      return;
    }

    try {
      setIsSubmitting(true);
      await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.data?.error) {
        setErrorMsg(err.response.data.error.message || "Invalid email or password");
      } else {
        setErrorMsg("Failed to connect to server. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-apple-parchment flex flex-col justify-between">
      {/* Top Global Bar */}
      <header className="bg-black text-white h-11 px-6 flex items-center justify-between text-xs">
        <Link to="/" className="font-semibold tracking-tight text-sm hover:opacity-80 transition-opacity">
          DocChat
        </Link>
        <Link to="/register" className="text-neutral-300 hover:text-white transition-colors">
          Create Account
        </Link>
      </header>

      {/* Main Container */}
      <main className="flex-1 flex items-center justify-center p-6 my-auto">
        <div className="max-w-4xl w-full grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
          {/* Left Column: Form */}
          <div className="space-y-6">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-pill bg-blue-50 border border-blue-200/60 text-apple-blue text-xs font-semibold">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Grounded AI Knowledge Engine</span>
              </div>
              <h1 className="text-3xl font-semibold tracking-tight text-apple-ink">
                Sign in to DocChat
              </h1>
              <p className="text-sm text-neutral-600">
                Access your personal grounded document workspace
              </p>
            </div>

            <div className="bg-white border border-apple-hairline rounded-2xl p-6 sm:p-8 shadow-sm space-y-6">
              {errorMsg && (
                <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-start gap-2.5">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>{errorMsg}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="block text-xs font-medium text-apple-ink">
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-neutral-400 absolute left-3.5 top-3" />
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="name@example.com"
                      autoComplete="email"
                      className="w-full pl-10 pr-3.5 py-2.5 text-sm bg-neutral-50/50 border border-neutral-300 rounded-xl text-apple-ink placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-apple-blue-focus focus:border-transparent transition-all"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="block text-xs font-medium text-apple-ink">
                      Password
                    </label>
                  </div>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-neutral-400 absolute left-3.5 top-3" />
                    <input
                      type="password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      autoComplete="current-password"
                      className="w-full pl-10 pr-3.5 py-2.5 text-sm bg-neutral-50/50 border border-neutral-300 rounded-xl text-apple-ink placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-apple-blue-focus focus:border-transparent transition-all"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full mt-2 py-2.5 px-4 bg-apple-blue hover:bg-blue-700 text-white text-sm font-medium rounded-pill flex items-center justify-center gap-2 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Signing in...</span>
                    </>
                  ) : (
                    <>
                      <span>Sign In</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </form>

              <div className="border-t border-apple-hairline pt-4 text-center">
                <p className="text-xs text-neutral-500">
                  Don't have an account?{" "}
                  <Link to="/register" className="text-apple-blue font-medium hover:underline">
                    Create one now
                  </Link>
                </p>
              </div>
            </div>
          </div>

          {/* Right Column: Testimonial & Features */}
          <div className="space-y-6">
            <TestimonialCarousel />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center py-4 text-xs text-apple-muted-48">
        DocChat · Strict User Isolation
      </footer>
    </div>
  );
}

export default Login;
