Steward issue, 2026-10-19. Draft D6 of [1]'s review, `docs/reviews/2026-10-19-architecture-review.md`; its first three drafts are done and accepted. Read the report's section for the evidence and line references.

Evidence: DESIGN.md:193–195 documents three get arguments, but
src/mailjail/models/email.py:177–183 only reads ids and properties.
src/mailjail/imap/fetch.py:134–201 builds all body content before filtering
properties. `bodyStructure` is documented at DESIGN.md:190 but never produced.
`hasAttachment` is omitted from the body-needing set at
src/mailjail/models/email.py:182, despite depending on attachments at
src/mailjail/imap/fetch.py:153.

Change if fixed: get options have one meaning from request to fetch to
serialization, and a requested projection does not silently choose an
inadequate fetch mode.

Draft title: **Implement Email/get body controls through a single options value**.
Work: validate the documented fetch booleans and byte limit at the handler;
pass those options to conversion and derive fetch mode from required data.
Implement UTF-8 byte truncation and accurate `isTruncated`. Explicitly document
`bodyStructure` as unsupported for now rather than adding a MIME tree API.
Acceptance: offline HTML-only and multipart fixtures cover both booleans,
multibyte truncation, default behavior and `hasAttachment` alone. Preserve
non-marking fetches. No open overlap.

## Implementation, 2026-10-19

`EmailGetOptions` in `src/mailjail/imap/fetch.py` is validated by the handler
and supplies both fetch requirements and conversion controls. Both value
switches default to false; zero bytes means unlimited. Part descriptors remain
available independently of the value switches, including the synthetic text
part for HTML-only mail. UTF-8 truncation applies separately to each selected
value and reports whether bytes were removed. `hasAttachment` requires a full
non-marking fetch. Header projections avoid body conversion. `bodyStructure`
remains unsupported and omitted; README.md and DESIGN.md describe the contract.

Offline MIME tests cover all switch combinations, defaults, byte boundaries
inside accented characters and emoji, exact limits, invalid option types,
attachment-only projection, and body access forbidden during header projection.
The initial focused run reproduced 33 failures before implementation.
