---
description: "Beğenilen bir videoyu sahnelere böler ve her sahne için video istemi (prompt) çıkarır (referans skill'i). Videoyu üretmez."
argument-hint: "<video dosyası> [--esik 0.30]"
---

`referans` skill'ini izle (`.claude/skills/referans/SKILL.md`). Video: $ARGUMENTS

Sırayla: `sahne_bul.py` (sahneler ve kareler) → kareleri gör → `istemler.json` → `html_yap.py` → `referanslar/<ad>/istemler.html`.
Çıktıyı ve sınırları (ses/konuşma görülmez, telif) kullanıcıya kısaca söyle.
