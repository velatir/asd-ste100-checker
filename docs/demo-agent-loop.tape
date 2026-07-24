# Terminal-style MCP/agent loop for docs/demo-agent-loop.gif
# Prefer regenerating with: python scripts/generate_demo_gifs.py
# (uses real docs/fixtures/before.txt + after.txt + ste100 summaries)
# Optional vhs: docker run --rm -v "$PWD:/vhs" -w /vhs ghcr.io/charmbracelet/vhs docs/demo-agent-loop.tape
#
# Story: show the example text → ste_check_text → ste_suggest_rewrite →
# host rewrite → ste_check_text recheck (length/passive cleared; vocab may remain).

Output docs/demo-agent-loop.gif
Set FontSize 14
Set Width 980
Set Height 560
Set Theme "Catppuccin Latte"
Set TypingSpeed 28ms
Set Padding 14

Type "# MCP agent loop on deploy-docs prose"
Enter
Type "user: check + rewrite this procedure for STE"
Enter
Sleep 400ms
Type "text = \"\"\""
Enter
Type "Three viable paths, in order of robustness, can be leveraged to facilitate deployment: implement containerized delivery so CI builds and pushes an image and the runtime pulls it; restore the pre-built environment and align infrastructure with the pipeline; or at minimum ensure that templates are synchronized and readiness is polled rather than slept."
Enter
Type "\"\"\""
Enter
Sleep 800ms

Type "tool → ste_check_text(text, text_type=\"procedure\")"
Enter
Sleep 600ms
Type "← compliant: false · 33 findings (27 error / 6 warning)"
Enter
Type "  [error] STE-SENTENCE-LENGTH — 54 words (max 20)"
Enter
Type "  [error] STE-VOCAB-UNAPPROVED — Word 'viable' is not approved"
Enter
Type "  [warning] STE-PASSIVE — Prefer active voice ('synchronized')"
Enter
Sleep 900ms

Type "tool → ste_suggest_rewrite(text, text_type=\"procedure\")"
Enter
Sleep 500ms
Type "← rewrite brief (prompt-return; no LLM API in MCP)"
Enter
Type "  constraints: split long sentences; one instruction each; active voice"
Enter
Sleep 800ms

Type "agent (host LLM): apply brief → draft rewrite"
Enter
Type "  Deploy the app with a container image."
Enter
Type "  1. Build the image in CI."
Enter
Type "  2. Push the image to the registry."
Enter
Type "  3. Configure the app to pull that image."
Enter
Type "  4. Do not install packages when the app starts."
Enter
Sleep 900ms

Type "tool → ste_check_text(rewrite, text_type=\"procedure\")"
Enter
Sleep 500ms
Type "← compliant: false · vocab remains without glossary"
Enter
Type "  STE-SENTENCE-LENGTH · STE-PASSIVE cleared"
Enter
Type "stop: structure fixed · recheck done · glossary optional next"
Enter
Sleep 2s
