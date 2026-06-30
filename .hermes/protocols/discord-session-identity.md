# Discord Session Identity Protocol

When answering or acting on Discord thread/session identity, do not use terminal environment variables such as `HERMES_SESSION_ID`, `HERMES_SESSION_CHAT_ID`, or `HERMES_SESSION_THREAD_ID` as authoritative evidence for another Discord thread. Terminal sessions and cached shell environments can retain stale values from a different thread.

Use gateway/session routing metadata instead:

1. Read `$HERMES_HOME/sessions/sessions.json`.
2. Look up the exact key `agent:main:discord:thread:<thread_id>:<thread_id>`.
3. Report that entry's `session_id` for the thread.
4. If needed, cross-check with gateway logs or session database metadata.

Prefer `sessions.json` / gateway metadata over shell env for thread-to-session mapping.
