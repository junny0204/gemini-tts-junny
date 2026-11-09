# AGENTS.md

AI agents asked to install or update this tool: read and follow [INSTALL_FOR_CLAUDE.md](INSTALL_FOR_CLAUDE.md) step by step (it is written in Traditional Chinese; talk to the user in their language).

Hard rules: never ask the user to paste the Gemini API key into the chat; never print the key or the files that hold it; let the user enter it themselves in the window opened by `scripts/set-gemini-key.ps1` (Windows) or `scripts/set-gemini-key.command` (macOS); verify only with `gemini_tts.py --verify-key`.

Developers: run the tests with `python -m unittest discover -s tests` using a Python that has the packages in `server/requirements.txt`.
