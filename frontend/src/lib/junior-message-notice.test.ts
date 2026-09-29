import assert from "node:assert/strict";
import test from "node:test";

import { juniorNotice, messagesNewerThan, shouldShowJuniorNotice } from "./junior-message-notice.ts";

test("a user message tells Junior received it", () => {
  const notice = juniorNotice({
    conversationId: "chat-1",
    conversationTitle: "Storykeep",
    messages: [{ id: "m1", role: "user", content: "Start the next step" }],
  });
  assert.equal(notice?.title, "Junior received a message");
  assert.equal(notice?.body, "Start the next step");
  assert.equal(notice?.conversationId, "chat-1");
});

test("a user message and a reply stay one notice", () => {
  const notice = juniorNotice({
    conversationId: "chat-1",
    messages: [
      { id: "m1", role: "user", content: "Check the mail list" },
      { id: "m2", role: "assistant", content: "The pin order is fixed." },
    ],
  });
  assert.equal(notice?.title, "Junior received a message");
  assert.match(notice?.body || "", /Check the mail list/);
  assert.match(notice?.body || "", /pin order/);
});

test("an assistant follow-up uses the chat title", () => {
  const notice = juniorNotice({
    conversationId: "chat-1",
    conversationTitle: "Storykeep",
    messages: [{ id: "m2", role: "assistant", content: "Finished. The result is in this chat." }],
  });
  assert.equal(notice?.title, "Storykeep");
  assert.match(notice?.body || "", /Finished/);
});

test("the open chat you are reading does not notify", () => {
  assert.equal(
    shouldShowJuniorNotice({
      panelOpen: true,
      documentHidden: false,
      focusedConversationId: "chat-1",
      conversationId: "chat-1",
      liveStream: true,
    }),
    false,
  );
  assert.equal(
    shouldShowJuniorNotice({
      panelOpen: true,
      documentHidden: false,
      focusedConversationId: "chat-1",
      conversationId: "chat-1",
      liveStream: false,
    }),
    false,
  );
});

test("a closed chat or another pane notifies", () => {
  assert.equal(
    shouldShowJuniorNotice({
      panelOpen: false,
      documentHidden: false,
      focusedConversationId: "chat-1",
      conversationId: "chat-1",
      liveStream: false,
    }),
    true,
  );
  assert.equal(
    shouldShowJuniorNotice({
      panelOpen: true,
      documentHidden: true,
      focusedConversationId: "chat-1",
      conversationId: "chat-1",
      liveStream: false,
    }),
    true,
  );
  assert.equal(
    shouldShowJuniorNotice({
      panelOpen: true,
      documentHidden: false,
      focusedConversationId: "chat-1",
      conversationId: "chat-2",
      liveStream: false,
    }),
    true,
  );
});

test("only messages after the last seen update count", () => {
  const rows = messagesNewerThan(
    [
      { id: "old", created_at: "2026-09-29T23:00:00Z" },
      { id: "new", created_at: "2026-09-29T23:40:00Z" },
    ],
    "2026-09-29T23:10:00Z",
  );
  assert.deepEqual(rows.map((row) => row.id), ["new"]);
});
