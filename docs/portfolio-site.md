# Portfolio site

The public portfolio is a small static site under [`site/`](../site/).
HTML contains the content; CSS provides the responsive layout; a local script
adds project filters, a mobile navigation toggle, and command copying.
No framework, package install, external fonts, tracking, or model credential
is required to serve it. It is not a web interface for running the SDK tools.

## Preview and check

From the repository root:

```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory site
```

Open <http://127.0.0.1:8000/>. Stop the server with Ctrl+C.
For deployed-path verification, serve `site/` beneath a
`systems-and-solutions/` prefix and check both the home page and `resume/`.
All local page links and assets are relative so the same files work at
<https://krshearman.github.io/systems-and-solutions/>.

The contract checks use only Python 3.11 or later:

```sh
python3 -B -m unittest discover -s tests -p 'test_portfolio_site.py' -v
```

These checks cover local links, anchors, basic document structure, project
visibility, local-only scripts, public asset boundaries, and workflow scope.
They are not a full accessibility audit or a substitute for inspecting a PDF.
Before publishing layout or interaction changes, check:

- Desktop and narrow mobile layouts, keyboard focus, and navigation Escape handling.
- All/agents/automation filters showing 5/2/3 projects and announcing the count.
- Command copying, including visible feedback when clipboard access fails.
- The HTML résumé and PDF download from the deployed project prefix.
- Useful content and navigation with JavaScript disabled, reduced motion, and zoom.

## Publish with GitHub Pages

The expected URL is <https://krshearman.github.io/systems-and-solutions/>.
In **Settings → Pages → Build and deployment**, choose **GitHub Actions**
as the source. This is separate from the Copilot credential environment.

Merge the site and [Pages workflow](../.github/workflows/pages.yml) into `main`.
That push runs **Deploy portfolio to GitHub Pages**. Its build job checks the
site and uploads **only `site/`**; the deployment job has Pages and OIDC write
permissions and uses the `github-pages` environment. A failed check prevents
deployment. Action versions are pinned to full commit SHAs.

The workflow also supports **Actions → Deploy portfolio to GitHub Pages →
Run workflow**, selecting `main`. Non-default-branch runs are skipped.
There is no pull-request preview deployment and no Copilot token dependency.
Normal repository CI continues to check the engineering examples separately.
Wait for a successful Pages deployment before sharing the public URL.
The deployment's environment link is the authoritative published address.

## Update content safely

Edit the home page and [`site/resume/index.html`](../site/resume/index.html)
together when experience, skills, or certifications change. Keep employer
experience separate from the repository's personal synthetic examples.
Project cards link to source walkthroughs and verified execution records;
do not turn a replay or an authored example into a claim of live execution,
model accuracy, or production adoption. Revisit evidence links as the showcase
changes. No credential badge or verification URL is invented.

The public PDF is
[`site/assets/kendall-shearman-resume.pdf`](../site/assets/kendall-shearman-resume.pdf).
It was derived from the updated supplied résumé with the phone line removed
by actual PDF content redaction, not a white overlay. Professional email was
explicitly retained. The original attachment is not a public site asset.

For a replacement, work outside the repository until it is safe to publish.
Apply true redactions, remove overlapping telephone links, clear original
document metadata, and save a fresh file with discarded objects removed.
Verify extracted text, link annotations, metadata, and the visible page;
then replace the public asset. HTML and raw-file contract checks cannot prove
that a compressed PDF contains no private text. Never commit an unredacted
original, even temporarily: deleting it later does not erase Git history.

The portrait is an optimized, metadata-free local WebP. Keep replacement
images local, include meaningful alternative text and intrinsic dimensions,
and remove unnecessary source metadata. Only public assets belong in `site/`:
never logs, generated model reports, credentials, or source attachments.
