# erza Chat Surfaces Spec

## Purpose

This document defines the reusable chat TUI surface in `erza`.

The goal is to let apps such as Slack, Telegram, Gmail-style thread views, and
internal support consoles reuse one terminal-native interaction model instead
of re-implementing curses paint loops for every app.

## Product Rule

The chat runtime follows `erza` visual rules first:

- transparent or terminal-default background
- boxed content only where it carries hierarchy
- `>` focus marker instead of full-line highlight
- fixed-dimension modals
- `hjkl` as the primary movement model
- readable text surfaces over decorative chrome

If an app-specific preference conflicts with these rules, the app should adapt
to `erza` rather than forking the renderer.

## Current API

The first implementation is a Python runtime API:

```python
from erza.chat import (
    ChatCallbacks,
    ChatConversation,
    ChatFile,
    ChatMessage,
    run_chat_app,
)


callbacks = ChatCallbacks(
    load_conversations=lambda: [
        ChatConversation("D1", "maanas", "2026-04-27 10:00", kind="dm"),
    ],
    load_messages=lambda conversation: [
        ChatMessage("D1:1", "Maanas", "2026-04-27 10:00", "hello"),
    ],
    send_message=lambda conversation, text: None,
    mark_read=lambda conversation, messages: None,
    open_file=lambda conversation, message, file: "/tmp/file.txt",
)

run_chat_app(callbacks, title="slack tui")
```

The API is intentionally data-first. The app owns API calls, auth, downloads,
and persistence. `erza` owns the terminal UI, loading overlay, normal/insert
mode behavior, navigation, modal behavior, and file opening.

## Data Model

### `ChatConversation`

Fields:

- `conversation_id`
- `label`
- `date`
- `kind`
- `unread`
- `metadata`

Use `label` for the human-readable conversation name. Do not expose raw user ids
when the app can resolve names.

### `ChatMessage`

Fields:

- `message_id`
- `sender`
- `date`
- `text`
- `files`
- `embeds`
- `unread`
- `metadata`

The message header should show sender name and date. Email ids or raw ids belong
in metadata, not in the visible header unless the app has no better label.

### `ChatFile`

Fields:

- `name`
- `file_id`
- `kind`
- `metadata`

Files render behind a `<<<X Files>>>` button inside the message box. Pressing
`l` on that button opens the fixed-height file picker.

### `ChatEmbed`

Fields:

- `title`
- `url`
- `text`
- `metadata`

Embeds render inline as text boxes inside the message. They are not file-picker
items.

## Interaction Model

Conversation list:

- `j` / `k`: move down / up
- `l` / Enter: open selected conversation
- `g`: first conversation
- `G`: latest visible conversation
- `r`: refresh
- `q` / Esc: quit

Chat view:

- default mode is normal mode
- `i` enters insert mode
- insert-mode Enter sends through `send_message`
- insert-mode Esc returns to normal mode and focuses the latest message
- insert mode uses Erza's shared input editor
- Ctrl-A / Ctrl-E move to composer start / end
- Ctrl-B / Ctrl-F move backward / forward by character
- Alt-B / Alt-F move backward / forward by word
- Ctrl-W / Ctrl-H delete the previous word / character
- Ctrl-D / Ctrl-K / Ctrl-U delete next character / through end / full composer
- `h` returns to the conversation list
- `j` / `k` move line by line in normal mode
- Ctrl-N / Ctrl-P move message by message
- `g` / `gg` jump to the first message
- `G` jumps to the latest message
- `,mra` marks all loaded conversations read from the conversation list or an open conversation when `mark_all_read` is provided
- `l` on `<<<X Files>>>` opens the file picker
- `r` refreshes the selected conversation

File picker:

- fixed visible body height of seven rows where the terminal allows it
- `j` / `k` move within the file list
- `l` / Enter opens the selected file
- `h` / Esc closes the picker

File opening defaults:

- PDFs use `$ERZA_PDF_VIEWER` when set, then `zathura`, `evince`, then `xdg-open`
- images use `$ERZA_IMAGE_VIEWER` when set, then `swayimg`, `imv`, `feh`, then `xdg-open`
- other files use `$VISUAL`, then `$EDITOR`, then `vim`

Global:

- `?` toggles shortcuts
- `q` quits

Loading:

- conversation, message, send, mark-read, and file-open callbacks
  use the same Erza matrix loading overlay as the main runtime
- switching back from an open conversation to the conversation list also uses
  the loading overlay so screen transitions have visible feedback

## Slack Adapter Direction

For Slack, the adapter should map existing Slack data functions into
`ChatCallbacks`:

- `load_conversations`: latest 100 DM/GDM-derived conversation summaries
- `load_messages`: latest 100 messages for the selected DM/GDM
- `mark_read`: Slack `conversations.mark`
- `mark_all_read`: Slack `conversations.mark` over the loaded DM/GDM list
- `send_message`: Slack `chat.postMessage`
- `open_file`: download the file through Slack, then return the local path

Slack-specific scope, token, and API failure handling should remain in the Slack
app. `erza.chat` should not import Slack libraries or know Slack token shapes.

## Future `.erza` Syntax

The Python API is the first stable surface because chat needs stateful
callbacks and persistent composer behavior. The eventual declarative syntax
should preserve the same runtime semantics:

```erza
<ChatSurface title="Slack">
  <ConversationList source="slack.conversations" />
  <ChatThread source="slack.messages" mark-read="slack.mark_read">
    <Composer action="/messages/send" />
  </ChatThread>
  <FilePicker source="slack.files" open-action="slack.open_file" />
</ChatSurface>
```

Do not add this syntax until the Python API has proven the right data and
navigation model.
