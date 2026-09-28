import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { MessageBubble } from "../components/MessageBubble";
import { ChatMessageItem } from "../api/chat";

describe("Frontend Markdown Safety & XSS Prevention", () => {
  it("prevents script injection from raw <script> tags in assistant messages", () => {
    const maliciousMsg: ChatMessageItem = {
      id: 1,
      session_id: 1,
      role: "assistant",
      content: "Here is your data: <script>window.__xss_flag = true;</script>",
      created_at: "2026-09-28T00:00:00Z",
      sources: [],
      model: "test-model",
    };

    const { container } = render(<MessageBubble message={maliciousMsg} />);

    // Assert no <script> DOM element is rendered
    const scriptElement = container.querySelector("script");
    expect(scriptElement).toBeNull();

    // Verify window global was not polluted
    expect((window as any).__xss_flag).toBeUndefined();

    // Content should be safely rendered as text
    expect(container.textContent).toContain("Here is your data:");
  });

  it("prevents image onerror inline event injection", () => {
    const imgXssMsg: ChatMessageItem = {
      id: 2,
      session_id: 1,
      role: "assistant",
      content: 'Testing image: <img src="invalid.png" onerror="window.__img_xss = true" />',
      created_at: "2026-09-28T00:00:00Z",
      sources: [],
      model: "test-model",
    };

    const { container } = render(<MessageBubble message={imgXssMsg} />);

    // Raw HTML img tag must not be rendered into an active DOM img with onerror
    const imgElement = container.querySelector("img[onerror]");
    expect(imgElement).toBeNull();
    expect((window as any).__img_xss).toBeUndefined();
  });

  it("prevents iframe injection", () => {
    const iframeMsg: ChatMessageItem = {
      id: 3,
      session_id: 1,
      role: "assistant",
      content: '<iframe src="https://attacker.example.com"></iframe>',
      created_at: "2026-09-28T00:00:00Z",
      sources: [],
      model: "test-model",
    };

    const { container } = render(<MessageBubble message={iframeMsg} />);
    const iframeElement = container.querySelector("iframe");
    expect(iframeElement).toBeNull();
  });

  it("neutralizes javascript: URLs in markdown links", () => {
    const linkMsg: ChatMessageItem = {
      id: 4,
      session_id: 1,
      role: "assistant",
      content: "Check this [malicious link](javascript:alert('pwned')) out.",
      created_at: "2026-09-28T00:00:00Z",
      sources: [],
      model: "test-model",
    };

    const { container } = render(<MessageBubble message={linkMsg} />);

    const link = container.querySelector("a");
    // react-markdown sanitizes javascript: protocol by either omitting the href or rendering text
    if (link) {
      expect(link.getAttribute("href")).not.toBe("javascript:alert('pwned')");
    }
  });

  it("renders safe markdown structures (bold, code, lists) correctly", () => {
    const safeMsg: ChatMessageItem = {
      id: 5,
      session_id: 1,
      role: "assistant",
      content: "**Bold text** and `inline code`\n\n- Item 1\n- Item 2",
      created_at: "2026-09-28T00:00:00Z",
      sources: [],
      model: "test-model",
    };

    const { container } = render(<MessageBubble message={safeMsg} />);

    expect(container.querySelector("strong")).not.toBeNull();
    expect(container.querySelector("strong")?.textContent).toBe("Bold text");
    expect(container.querySelector("code")).not.toBeNull();
    expect(container.querySelector("code")?.textContent).toBe("inline code");
    expect(container.querySelectorAll("li").length).toBe(2);
  });
});
