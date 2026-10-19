Steward issue, 2026-10-19. Goal: open-source; mailjail is tier 3.

From draft D1 of `docs/reviews/2026-10-19-architecture-review.md` (the review in mailjail [1]), which ranks it among the first to do. The draft follows as the reviewer wrote it; read the review's other sections only if this one points there.

## Draft

Evidence: README.md:48–54 puts `primary_account` after `[server]`, whereas
src/mailjail/config.py:172–175 requires a root key. Config path values at
src/mailjail/config.py:275–276, 285–287 and 307 become `Path` objects without
`expanduser()`. README.md:67 and DESIGN.md:618, 628 use literal `~` paths.
docs/QUICK_START.md:13–25 uses a quoted heredoc containing literal `$HOME`.
The config loader's own example repeats the root-key mistake at
src/mailjail/config.py:136–142.

Change if fixed: copying the setup example reaches account configuration;
operator paths resolve consistently instead of being treated as relative names.

Draft title: **Make config examples and user paths agree with the loader**.
Work: move the root key before the first table in examples; normalize the three
configured user-path fields with `expanduser()` at their consumption points;
replace literal `$HOME` in the quoted example with `~` once supported. Do not
add general environment interpolation. Document accepted path syntax.
Acceptance: parse the README TOML offline and assert its root key; use temporary
HOME/provider fixtures to exercise tilde paths without real credentials; retain
absolute-path behavior. No network calls. No open overlap.

## Steward's constraints

- Make no connection to a real mail server or account.

## Done when

The draft's acceptance holds, lint and tests pass, and the change is merged to `main` as the Rules describe. No push or deploy.
