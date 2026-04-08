# Response & Safety Guidelines

Preserved from CLAUDE.md during the technical rewrite. These are operational
guidelines for how Claude should respond and handle sensitive data in this project.

---

## How to Respond

Every response includes:
- **What I just did** — plain English
- **What you need to do** — step by step
- **Why** — one sentence on what it does or why it matters
- **Next step** — one clear action
- **Errors** — if something broke, explain simply and say how to fix it

---

## Secrets & Safety

- All API keys and credentials live in `.env` only
- Never hardcode secrets anywhere in the codebase
- Never commit `.env` or `credentials.json` to version control
- If a script needs a key, it reads from environment variables
- Ask before deleting or renaming any important files

---

## Testing Protocol

Before marking any task as done:
1. Run the relevant script and confirm it exits successfully
2. Check for errors, warnings, or unexpected output
3. Verify existing behavior wasn't broken by the change
4. Test the happy path AND the error path
5. Confirm data passes correctly between steps
6. If it uses paid API calls, check with me before rerunning

Never say "done" if the code is untested.
