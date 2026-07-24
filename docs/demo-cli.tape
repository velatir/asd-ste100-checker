# Scripted CLI demo for docs/demo-cli.gif
# Prefer regenerating with: docker run --rm -v "$PWD:/vhs" -w /vhs ghcr.io/charmbracelet/vhs docs/demo-cli.tape
# This repo also ships scripts/generate_demo_gifs.py (host render from real fixtures).

Output docs/demo-cli.gif
Set FontSize 15
Set Width 980
Set Height 520
Set Theme "Catppuccin Latte"
Set TypingSpeed 45ms
Set PlaybackSpeed 1.0
Set Padding 16

Type "ste100 check docs/fixtures/before.txt --text-type procedure | jq '{compliant,summary,rules:[.findings[].rule_id]|unique}'"
Enter
Sleep 2.5s

Type "ste100 check docs/fixtures/after.txt --text-type procedure | jq '{compliant,summary,rules:[.findings[].rule_id]|unique}'"
Enter
Sleep 2.5s
