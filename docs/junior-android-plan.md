# Junior Android — three-screen plan

Approved screens (order): Talk, Conversation, Stories.

## 1. Talk
Primary compose surface. Voice and type. Default Listen voice is castor unless the user picks another. voice_id and schema.sql stay the source of truth for persistence. No extra screens in this sequence.

## 2. Conversation
Thread view of the current Junior chat. Messages in order. Does not replace Talk. Does not invent mail, calendar, or other chats.

## 3. Stories
StoryKeep / RSS / notes surface as planned for Android. Read and navigate stories. Does not implement Kotlin in this sequence.

Out of scope for #66
Kotlin, Compose UI, git add -A, push main, tree search, extra docs.
