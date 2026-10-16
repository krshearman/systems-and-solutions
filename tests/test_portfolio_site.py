from html.parser import HTMLParser
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


class Document(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.elements = []
        self.ids = []
        self.text = []
        self.links = []
        self.open_links = []
        self.has_nested_links = False
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a":
            self.has_nested_links |= bool(self.open_links)
            link = (attrs, [])
            self.links.append(link)
            self.open_links.append(link)

    def handle_endtag(self, tag):
        if tag == "a" and self.open_links:
            self.open_links.pop()

    def handle_data(self, data):
        self.text.append(data)
        for _, text in self.open_links:
            text.append(data)


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.home = Document(SITE / "index.html")
        self.resume = Document(SITE / "resume/index.html")

    def test_documents_have_unique_ids_and_a_single_named_main_heading(self):
        for document in (self.home, self.resume):
            with self.subTest(path=document.path):
                self.assertEqual(len(document.ids), len(set(document.ids)))
                self.assertEqual(sum(tag == "h1" for tag, _ in document.elements), 1)
                self.assertEqual(sum(tag == "main" for tag, _ in document.elements), 1)
                self.assertTrue(any(tag == "main" and attrs.get("id") == "main"
                                    and attrs.get("tabindex") == "-1"
                                    for tag, attrs in document.elements))
                self.assertIn(("html", {"lang": "en"}), document.elements)
                self.assertTrue(any(tag == "title" for tag, _ in document.elements))
                self.assertTrue(any(tag == "a" and attrs.get("href") == "#main"
                                    for tag, attrs in document.elements))
                self.assertTrue(any(tag == "meta" and attrs.get("name") == "description"
                                    for tag, attrs in document.elements))

    def test_relative_assets_links_and_fragments_resolve_under_the_project_prefix(self):
        for document in (self.home, self.resume):
            for tag, attrs in document.elements:
                for attribute in ("href", "src"):
                    value = attrs.get(attribute)
                    if value is None:
                        continue
                    parsed = urlsplit(value)
                    if parsed.scheme:
                        self.assertIn(parsed.scheme, {"https", "mailto"})
                        continue
                    self.assertFalse(value.startswith("/"), "Use project-relative paths")
                    target = (document.path.parent / unquote(parsed.path)).resolve()
                    self.assertTrue(target.is_relative_to(SITE.resolve()))
                    if target.is_dir():
                        target /= "index.html"
                    self.assertTrue(target.is_file(), f"Broken local link: {value}")
                    if parsed.fragment:
                        target_document = Document(target)
                        self.assertIn(parsed.fragment, target_document.ids)

    def test_repository_source_links_point_to_real_tracked_surfaces(self):
        prefix = "https://github.com/krshearman/systems-and-solutions/"
        for _, attrs in self.home.elements:
            href = attrs.get("href", "")
            for kind in ("blob/main/", "tree/main/"):
                if href.startswith(prefix + kind):
                    target = ROOT / href.removeprefix(prefix + kind)
                    self.assertTrue(target.exists(), f"Broken repository link: {href}")

    def test_brand_has_separate_repository_and_home_links(self):
        for class_name, href, label in (
            ("brand-home", "./", "Kendall Shearman"),
            ("brand-subtitle", "https://github.com/krshearman/systems-and-solutions",
             "Systems & solutions"),
        ):
            with self.subTest(link=class_name):
                links = [(attrs, "".join(text)) for attrs, text in self.home.links
                         if class_name in attrs.get("class", "").split()]
                self.assertEqual(len(links), 1)
                attrs, text = links[0]
                self.assertEqual(attrs["href"], href)
                self.assertEqual(text, label)
                self.assertNotIn("tabindex", attrs)
        self.assertFalse(self.home.has_nested_links)

    def test_github_advanced_security_is_present_in_both_public_pages(self):
        for document in (self.home, self.resume):
            self.assertIn("GitHub Advanced Security (GHAS)", "".join(document.text))

    def test_public_resume_asset_and_contact_links(self):
        for document in (self.home, self.resume):
            content = document.path.read_text()
            self.assertNotIn("tel:", content.lower())
            self.assertNotIn("Phone:", content)
            self.assertNotRegex(content, r"(?<!\d)\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)")
            self.assertIn("mailto:kendallshearman@gmail.com", content)
        pdfs = list(SITE.rglob("*.pdf"))
        self.assertEqual(pdfs, [SITE / "assets/kendall-shearman-resume.pdf"])
        data = pdfs[0].read_bytes()
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertTrue(data.rstrip().endswith(b"%%EOF"))
        self.assertNotIn(b"tel:", data.lower())
        self.assertLess(len(data), 2_000_000)

    def test_public_directory_contains_only_the_intended_assets(self):
        expected = {
            "index.html",
            "resume/index.html",
            "assets/favicon.svg",
            "assets/styles.css",
            "assets/site.js",
            "assets/kendall-shearman.webp",
            "assets/kendall-shearman-resume.pdf",
        }
        files = set()
        for path in SITE.rglob("*"):
            self.assertFalse(path.is_symlink(), f"Do not publish symlinks: {path}")
            if path.is_file():
                files.add(path.relative_to(SITE).as_posix())
        self.assertEqual(files, expected)

    def test_portrait_is_local_sized_and_accessibly_described(self):
        images = [attrs for tag, attrs in self.home.elements if tag == "img"]
        self.assertEqual(len(images), 1)
        image = images[0]
        self.assertTrue(image["alt"].strip())
        self.assertEqual((image["width"], image["height"]), ("800", "803"))
        self.assertLess((SITE / image["src"]).stat().st_size, 200_000)

    def test_all_five_projects_are_visible_without_javascript(self):
        projects = [attrs for _, attrs in self.home.elements if "data-category" in attrs]
        self.assertEqual(len(projects), 5)
        self.assertEqual(sum(attrs["data-category"] == "agents" for attrs in projects), 2)
        self.assertEqual(sum(attrs["data-category"] == "automation" for attrs in projects), 3)
        self.assertTrue(all("hidden" not in attrs for attrs in projects))
        content = self.home.path.read_text()
        for title in ("ADR", "Refactor", "post-mortem", "PR impact", "coordinator"):
            self.assertIn(title.lower(), content.lower())

    def test_local_only_scripts_and_no_inline_execution(self):
        for document in (self.home, self.resume):
            for tag, attrs in document.elements:
                self.assertTrue(all(not key.startswith("on") for key in attrs))
                if tag == "script":
                    self.assertIn("src", attrs)
                    self.assertFalse(urlsplit(attrs["src"]).scheme)

    def test_motion_and_focus_preferences_are_supported(self):
        stylesheet = (SITE / "assets/styles.css").read_text()
        self.assertIn("prefers-reduced-motion: reduce", stylesheet)
        self.assertIn(":focus-visible", stylesheet)
        self.assertIn("[hidden]", stylesheet)

    def test_pages_uploads_only_the_public_directory_with_scoped_deployment_permissions(self):
        workflow = (ROOT / ".github/workflows/pages.yml").read_text()
        self.assertIn("path: site", workflow)
        self.assertIn("needs: build", workflow)
        self.assertIn("github.event.repository.default_branch", workflow)
        self.assertNotIn("pull_request", workflow)
        self.assertNotIn("COPILOT_GITHUB_TOKEN", workflow)
        build, deploy = workflow.split("\n  deploy:", 1)
        self.assertNotIn("pages: write", build)
        self.assertIn("pages: write", deploy)
        self.assertIn("id-token: write", deploy)
        actions = re.findall(r"uses: [^@\s]+@([^\s]+)", workflow)
        self.assertTrue(actions)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in actions))


if __name__ == "__main__":
    unittest.main()
