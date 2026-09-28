import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter, MemoryRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "../context/AuthContext";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { Login } from "../pages/Login";
import { Register } from "../pages/Register";

// Mock API calls
vi.mock("../api/auth", () => ({
  loginApi: vi.fn(),
  registerApi: vi.fn(),
  getMeApi: vi.fn().mockRejectedValue(new Error("No token")),
}));

describe("Authentication Frontend Tests", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("renders login form and validates empty submission", async () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByText("Sign in to DocChat")).toBeInTheDocument();
    const submitBtn = screen.getByRole("button", { name: /sign in/i });

    // Submit with empty inputs
    fireEvent.click(submitBtn);

    // Should prompt required fields or show error
    expect(screen.getByPlaceholderText("name@example.com")).toBeRequired();
  });

  it("validates password length and mismatch on register form", async () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <Register />
        </AuthProvider>
      </BrowserRouter>
    );

    const emailInput = screen.getByPlaceholderText("name@example.com");
    const passwordInputs = screen.getAllByPlaceholderText("••••••••");
    const submitBtn = screen.getByRole("button", { name: /create account/i });

    // 1. Password too short (< 8 chars)
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(passwordInputs[0], { target: { value: "short" } });
    fireEvent.change(passwordInputs[1], { target: { value: "short" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText("Password must be at least 8 characters long.")
      ).toBeInTheDocument();
    });

    // 2. Passwords mismatch
    fireEvent.change(passwordInputs[0], { target: { value: "password123" } });
    fireEvent.change(passwordInputs[1], { target: { value: "password456" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();
    });
  });

  it("redirects unauthenticated user away from protected route", async () => {
    render(
      <MemoryRouter initialEntries={["/documents"]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>Login Page Redirected</div>} />
            <Route
              path="/documents"
              element={
                <ProtectedRoute>
                  <div>Secret Documents Page</div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    // Unauthenticated user should not see protected content and should be redirected
    await waitFor(() => {
      expect(screen.getByText("Login Page Redirected")).toBeInTheDocument();
      expect(screen.queryByText("Secret Documents Page")).not.toBeInTheDocument();
    });
  });
});
