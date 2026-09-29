export type IncomingMessage = {
  id: string;
  role: string;
  content: string;
  created_at?: string;
};

export type JuniorNotice = {
  conversationId: string;
  title: string;
  body: string;
};

export function previewLine(content: string, limit = 140): string {
  const text = (content || "").replace(/\s+/g, " ").trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, limit - 1).trimEnd()}…`;
}

export function juniorNotice(input: {
  conversationId: string;
  conversationTitle?: string | null;
  messages: IncomingMessage[];
}): JuniorNotice | null {
  const fresh = input.messages.filter((item) => (item.content || "").trim() && item.id);
  if (!fresh.length || !input.conversationId) return null;
  const user = [...fresh].reverse().find((item) => item.role === "user");
  const assistant = [...fresh].reverse().find((item) => item.role === "assistant");
  const titleBase = (input.conversationTitle || "").trim() || "Junior";
  if (user) {
    const received = previewLine(user.content);
    const reply = assistant ? previewLine(assistant.content, 80) : "";
    return {
      conversationId: input.conversationId,
      title: "Junior received a message",
      body: reply ? `${received} — ${reply}` : received,
    };
  }
  if (assistant) {
    return {
      conversationId: input.conversationId,
      title: titleBase,
      body: previewLine(assistant.content),
    };
  }
  return null;
}

export function shouldShowJuniorNotice(input: {
  panelOpen: boolean;
  documentHidden: boolean;
  focusedConversationId: string | null;
  conversationId: string;
  liveStream: boolean;
}): boolean {
  if (
    input.liveStream &&
    input.panelOpen &&
    !input.documentHidden &&
    input.focusedConversationId === input.conversationId
  ) {
    return false;
  }
  if (input.documentHidden || !input.panelOpen) return true;
  return input.focusedConversationId !== input.conversationId;
}

export function messagesNewerThan<T extends { created_at?: string }>(messages: T[], previousUpdatedAt: string): T[] {
  const cut = Date.parse(previousUpdatedAt);
  if (Number.isNaN(cut)) return [];
  return messages.filter((item) => {
    const stamp = Date.parse(item.created_at || "");
    return !Number.isNaN(stamp) && stamp > cut;
  });
}
