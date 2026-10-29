The fixture holds seven items from the public HZZ RSS feeds observed on 2026-10-29:

http://burzarada.hzz.hr/rss/rsszup1.xml (Bjelovarsko-bilogorska, six items)
http://burzarada.hzz.hr/rss/rsszup2.xml (Brodsko-posavska, one item)

The channel header and each `<item>` block are byte-for-byte copies of the
responses, so the iso-8859-2 declaration, CRLF line endings, repeated entity
escaping and 512-character description truncation are preserved. Only the
item selection is ours; no text was edited.

Items were chosen to cover: an empty title, a title with a vacancy number, a
description cut inside an HTML tag, a triple-escaped `NBSP`, a deadline in the
`, Kategorija: …, Rok za prijavu: …` suffix, a short description without HTML,
and a 150-character title. Items whose text contained an e-mail address, a
phone number, "OIB" or a contact phrase were excluded.

Measurements of all 22 feeds are summarised in `docs/hzz-feed-measurement.md`.
