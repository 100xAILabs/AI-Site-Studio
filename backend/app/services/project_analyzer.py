import os
import re
import zipfile
import shutil
import uuid
import json
import logging
import tempfile
import asyncio
import io
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_PAGE_SCAN_SKIP_DIRS = {
    "node_modules", ".git", ".next", ".nuxt", ".output", "dist", "build",
    ".venv", "venv", "vendor", "coverage", ".cache",
}
_PAGE_SOURCE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".astro"}


def _page_name_from_route(route: str) -> Optional[str]:
    """Turn a URL or file-based route into a readable page name."""
    clean = str(route or "").split("?", 1)[0].split("#", 1)[0].strip().strip("/")
    if not clean or clean.lower() in {"index", "*"}:
        return "Home"
    parts = []
    for segment in clean.split("/"):
        if not segment or (segment.startswith("(") and segment.endswith(")")):
            continue
        if segment.startswith(":") or (segment.startswith("[") and segment.endswith("]")) or segment in {"*", "[...slug]", "[[...slug]]"}:
            parts.append("Detail")
        else:
            parts.append(re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", segment.replace("-", " ").replace("_", " ")).strip().title())
    return " ".join(part for part in parts if part) or "Home"


def _discover_framework_pages(root_path: Path, framework: str) -> List[str]:
    """Discover file-based pages and declared client-side routes for supported frameworks."""
    framework = (framework or "html").lower()
    discovered: List[str] = []
    route_files: List[tuple[Path, tuple[str, ...]]] = []

    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [name for name in dirnames if name not in _PAGE_SCAN_SKIP_DIRS]
        directory = Path(dirpath)
        try:
            relative_parts = directory.relative_to(root_path).parts
        except ValueError:
            continue
        lower_parts = tuple(part.lower() for part in relative_parts)

        for filename in filenames:
            path = Path(filename)
            suffix = path.suffix.lower()
            stem = path.stem.lower()
            if suffix not in _PAGE_SOURCE_EXTS:
                continue

            if framework in {"nextjs", "react", "vue", "nuxt", "astro"} and "pages" in lower_parts:
                if stem not in {"_app", "_document", "_error", "404", "500", "middleware", "layout"}:
                    route_parts = list(lower_parts[lower_parts.index("pages") + 1:]) + [path.stem]
                    if route_parts and route_parts[-1].lower() == "index":
                        route_parts.pop()
                    discovered.append(_page_name_from_route("/".join(route_parts)))
            elif framework == "nextjs" and stem == "page" and "app" in lower_parts:
                route_parts = list(lower_parts[len(lower_parts) - 1 - lower_parts[::-1].index("app") + 1:])
                discovered.append(_page_name_from_route("/".join(route_parts)))
            elif framework == "svelte" and filename.lower() == "+page.svelte":
                route_parts = list(lower_parts[lower_parts.index("routes") + 1:]) if "routes" in lower_parts else list(lower_parts)
                discovered.append(_page_name_from_route("/".join(route_parts)))
            elif framework == "astro" and "src" in lower_parts and "pages" in lower_parts:
                route_parts = list(lower_parts[lower_parts.index("pages") + 1:]) + [path.stem]
                discovered.append(_page_name_from_route("/".join(route_parts)))

            if suffix in {".js", ".jsx", ".ts", ".tsx", ".vue"}:
                route_files.append((directory / filename, lower_parts + (filename.lower(),)))

    path_pattern = re.compile(r"\bpath\s*[:=]\s*['\"]([^'\"]+)['\"]")
    jsx_route_pattern = re.compile(r"<Route\b[^>]*\bpath\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
    for route_file, path_parts in route_files:
        filename = path_parts[-1]
        in_route_config = any("route" in part or "router" in part or "routing" in part for part in path_parts)
        is_router_source = filename in {"app.jsx", "app.tsx", "app.js", "app.ts", "main.jsx", "main.tsx"}
        try:
            if route_file.stat().st_size > 1024 * 1024:
                continue
            source = route_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        routes = []
        if framework in {"react", "nextjs"}:
            routes.extend(jsx_route_pattern.findall(source))
            if in_route_config or (is_router_source and any(marker in source for marker in ("createBrowserRouter", "<Routes", "createRoutesFromElements"))):
                routes.extend(path_pattern.findall(source))
        elif framework in {"vue", "nuxt"} and (in_route_config or "createRouter" in source or "RouterView" in source):
            routes.extend(path_pattern.findall(source))
        elif framework == "angular" and (in_route_config or "Routes" in source):
            routes.extend(path_pattern.findall(source))
        elif framework == "svelte" and in_route_config:
            routes.extend(path_pattern.findall(source))

        for route in routes:
            page_name = _page_name_from_route(route)
            if page_name:
                discovered.append(page_name)

    unique: List[str] = []
    seen = set()
    for name in discovered:
        if not name:
            continue
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(name)
    return unique

class ProjectAnalyzer:
    """
    Analyzes website template project files (extracted ZIPs).
    Runs automated file tree scanning, parses package.json, analyzes CSS,
    and runs Gemini API for content generation, scores, and tag extraction.
    """

    def _safe_cleanup(self, path: Path):
        """Safely removes a directory tree, handling Windows read-only file issues (common with .git)."""
        import stat
        def remove_readonly(func, p, excinfo):
            try:
                os.chmod(p, stat.S_IWRITE)
                func(p)
            except Exception:
                pass
        
        if path.exists():
            try:
                shutil.rmtree(path, onerror=remove_readonly)
            except Exception as e:
                logger.warning(f"Failed to delete directory {path}: {e}")

    def analyze_zip_stream_quick(self, source, filename: str = "template.zip") -> Dict[str, Any]:
        """Inspect a large archive in place without buffering or extracting it."""
        from app.services.security_scanner import security_scanner
        source.seek(0)
        if not zipfile.is_zipfile(source):
            if Path(filename).suffix.lower() in {".html", ".htm", ".js", ".css"}:
                findings = security_scanner.scan_code_stream(source, filename)
                if any(item.get("severity") in {"CRITICAL", "HIGH"} for item in findings):
                    return {"success": False, "is_security_violation": True, "error": "Uploaded code failed security inspection", "security_findings": findings}
            return {"success": True, "framework_detected": "HTML", "pages": ["Home"], "color_palette": [], "dark_mode": False, "responsive_analysis": {"desktop": True, "tablet": True, "mobile": True}, "quick_scan": True}
        report = security_scanner.scan_zip_stream(source, filename)
        if not report.get("is_safe") or report.get("purged_files"):
            return {"success": False, "is_security_violation": True, "error": report.get("reason") or "Archive contains blocked executable files", "security_findings": report.get("findings", [])}

        pages: list[str] = []
        dependencies: dict[str, Any] = {}
        has_typescript_source = False
        source.seek(0)
        with zipfile.ZipFile(source, "r") as archive:
            for item in archive.infolist():
                path = item.filename.replace("\\", "/")
                lower = path.lower()
                if item.is_dir() or any(part in {"node_modules", ".git", "dist", "build", ".next", ".nuxt"} for part in lower.split("/")):
                    continue
                if lower.endswith((".html", ".htm")):
                    pages.append(Path(path).stem.replace("-", " ").replace("_", " ").title())
                if lower.endswith((".ts", ".tsx")):
                    has_typescript_source = True
                if Path(lower).name == "package.json" and item.file_size <= 2 * 1024 * 1024:
                    try:
                        package = json.loads(archive.read(item).decode("utf-8", errors="replace"))
                        dependencies.update(package.get("dependencies") or {})
                        dependencies.update(package.get("devDependencies") or {})
                    except Exception:
                        continue

        frameworks = [("next", "Next.js"), ("@angular/core", "Angular"), ("nuxt", "Nuxt"), ("vue", "Vue"), ("astro", "Astro"), ("svelte", "Svelte"), ("react", "React")]
        framework = next((label for package, label in frameworks if package in dependencies), "HTML")
        package_name = {"Next.js": "next", "Angular": "@angular/core", "Nuxt": "nuxt", "Vue": "vue", "Astro": "astro", "Svelte": "svelte", "React": "react"}.get(framework, "")
        language = "TypeScript" if "typescript" in dependencies or has_typescript_source else "JavaScript"
        return {
            "success": True, "framework_detected": framework,
            "language": language,
            "version": str(dependencies.get(package_name, "1.0.0")).lstrip("^~") or "1.0.0",
            "pages": list(dict.fromkeys(pages)) or ["Home"],
            "components": ["Navbar", "Main Content", "Footer"], "categories": {}, "industry": [],
            "color_palette": [], "typography": [], "responsive_analysis": {"desktop": True, "tablet": True, "mobile": True},
            "dark_mode": False, "seo_analysis": {}, "assets_count": {}, "quick_scan": True,
        }

    async def analyze_zip_bytes(self, zip_bytes: bytes, filename: str = "template.zip") -> Dict[str, Any]:
        """Alias for analyze_zip accepting raw zip file bytes."""
        return await self.analyze_zip(zip_bytes, filename)

    async def analyze_zip(self, file_content: bytes, original_filename: str = "template.zip") -> Dict[str, Any]:
        # If raw HTML/HTM was uploaded or not a ZIP archive, auto-wrap into in-memory ZIP
        if original_filename.lower().endswith((".html", ".htm")) or not zipfile.is_zipfile(io.BytesIO(file_content)):
            try:
                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr("index.html", file_content)
                file_content = zip_buf.getvalue()
                original_filename = "index.html.zip"
            except Exception as e:
                logger.warning(f"Failed to auto-wrap raw HTML file into ZIP: {e}")

        temp_id = uuid.uuid4().hex
        temp_dir = Path(tempfile.gettempdir()) / "ai_site_studio" / "temp_zips" / temp_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        # 0. Run Instant Live Security & Malware Scan
        from app.services.security_scanner import security_scanner
        sec_result = security_scanner.scan_zip_bytes(file_content, original_filename)
        if not sec_result["is_safe"] or sec_result.get("purged_files"):
            logger.warning(f"🚨 Security check failed for {original_filename}: {sec_result.get('findings')}")
            return {
                "success": False,
                "is_security_violation": True,
                "error": f"Security verification failed: {sec_result.get('reason') or 'Malicious or dangerous pattern detected.'}",
                "security_findings": sec_result.get("findings", []),
                "framework_detected": "Untrusted",
                "pages": [],
                "components": [],
                "categories": {},
                "color_palette": [],
                "assets_count": {"images": 0, "svg": 0, "icons": 0, "videos": 0, "fonts": 0},
            }

        try:
            # 1. Extract zip file safely — auto-purges any unsafe binary files while preserving website template assets
            extract_dir = temp_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)
            purged_files = security_scanner.sanitize_extract_zip(file_content, extract_dir)
            if purged_files:
                logger.info(f"🛡️ Auto-sanitized {len(purged_files)} unsafe binary file(s) from template: {purged_files}")

            # 3. Locate root folder (sometimes ZIP extracts into a subfolder or contains package.json recursively)
            root_path = extract_dir
            
            # Find directory of package.json if it exists recursively
            package_json_found = None
            for r, d, f in os.walk(extract_dir):
                if "package.json" in f:
                    package_json_found = Path(r)
                    break
            
            if package_json_found:
                root_path = package_json_found
            else:
                # Find directory of index.html if it exists recursively
                index_html_found = None
                for r, d, f in os.walk(extract_dir):
                    if "index.html" in f:
                        index_html_found = Path(r)
                        break
                if index_html_found:
                    root_path = index_html_found
                else:
                    # Fallback to single subdirectory check
                    extracted_items = [item for item in os.listdir(extract_dir) if item != "__MACOSX" and not item.startswith(".")]
                    if len(extracted_items) == 1 and os.path.isdir(extract_dir / extracted_items[0]):
                        root_path = extract_dir / extracted_items[0]

            # 4. Guard: reject backend/server projects — only web templates allowed
            backend_check = self._detect_backend_project(root_path)
            if backend_check["is_backend"]:
                return {
                    "success": False,
                    "is_backend_project": True,
                    "backend_type": backend_check.get("backend_type", "Backend"),
                    "error": backend_check["reason"],
                    "framework_detected": backend_check.get("backend_type", "Backend"),
                    "pages": [],
                    "components": [],
                    "categories": {},
                    "color_palette": [],
                    "assets_count": {"images": 0, "svg": 0, "icons": 0, "videos": 0, "fonts": 0},
                }

            # 5. Scan files recursively
            scan_results = self._scan_project_files(root_path)

            # 5. Get AI analysis using Gemini API (or fallback to OpenAI or Mock)
            ai_analysis = await self._run_ai_analysis(scan_results)

            # Combine and return
            return {
                "success": True,
                "project_name": ai_analysis.get("project_name") or Path(original_filename).stem.replace(".html", "").replace("-", " ").title(),
                "framework_detected": scan_results["framework"],
                "version": scan_results["version"],
                "framework_version": scan_results.get("framework_version"),
                "code_version": scan_results.get("code_version"),
                "is_html_only": scan_results.get("is_html_only", False),
                "language": scan_results["language"],
                "css_system": scan_results["css_system"],
                "ui_library": scan_results["ui_library"],
                "animation_library": scan_results["animation_library"],
                "pages": scan_results["pages"] or ["Home"],
                "components": scan_results["components"] or (["Navbar", "Hero", "Footer"] if scan_results["framework"] != "html" else ["Header", "Content", "Footer"]),
                "categories": ai_analysis.get("categories") or {"Business": 90, "Agency": 85},
                "industry": ai_analysis.get("industry") or ["Marketing", "Software", "SaaS"],
                "color_palette": scan_results["color_palette"] or ["#7C3AED", "#2563EB", "#FFFFFF", "#111827"],
                "typography": scan_results["typography"] or ["Inter"],
                "responsive_analysis": {
                    "desktop": True,
                    "tablet": scan_results["is_responsive"],
                    "mobile": scan_results["is_responsive"],
                },
                "dark_mode": scan_results["has_dark_mode"],
                "seo_analysis": scan_results["seo"],
                "performance_scores": ai_analysis.get("performance_scores") or {
                    "performance": 95,
                    "accessibility": 98,
                    "seo": 96,
                    "best_practices": 98
                },
                "accessibility": scan_results["accessibility"],
                "features_detected": ai_analysis.get("features_detected") or scan_results["features_detected"] or ["Responsive Layout", "CSS Grid"],
                "ai_description": ai_analysis.get("ai_description") or (f"Modern and clean HTML5 website template." if scan_results["framework"] == "html" else f"Modern and fully responsive template built with {scan_results['framework']}."),
                "ai_tags": ai_analysis.get("ai_tags") or ["template", scan_results["framework"]],
                "ai_selling_points": ai_analysis.get("ai_selling_points") or ["Clean codebase", "Fully responsive", "SEO optimized"],
                "ai_score": ai_analysis.get("ai_score") or 95,
                "ai_suggestions": ai_analysis.get("ai_suggestions") or ["Optimize loading speed", "Ensure alt attributes are set"],
                "dependencies": scan_results["dependencies"],
                "assets_count": scan_results["assets_count"],
            }

        except Exception as e:
            logger.exception("Error in project analysis")
            return {
                "success": False,
                "error": str(e),
                "framework_detected": "HTML",
                "pages": ["Home"],
                "components": ["Navbar", "Hero"],
                "categories": {"HTML": 100},
                "color_palette": ["#7C3AED", "#2563EB"],
                "assets_count": {"images": 0, "svg": 0, "icons": 0, "videos": 0, "fonts": 0},
            }
        finally:
            # Clean up temporary directory
            self._safe_cleanup(temp_dir)

    async def analyze_git_repo(self, git_url: str, token: Optional[str] = None) -> Dict[str, Any]:
        """
        Clones a Git repository, packages it into a clean ZIP file
        (automatically filtering out .git, node_modules, .venv, etc.),
        runs technical scan & AI audit, and returns the analysis results
        along with the clean ZIP bytes for saving.
        """
        temp_id = uuid.uuid4().hex
        temp_dir = Path(tempfile.gettempdir()) / "ai_site_studio" / "temp_git" / temp_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        clone_dir = temp_dir / "repo"

        try:
            # 1. Run a shallow Git clone without putting credentials in the URL
            import subprocess
            import base64
            cmd = ["git", "clone", "--depth", "1", "--single-branch", "--no-tags", git_url, str(clone_dir)]
            clone_env = {
                "PATH": os.environ.get("PATH", ""),
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
                "WINDIR": os.environ.get("WINDIR", os.environ.get("SYSTEMROOT", "C:\\Windows")),
                "TEMP": os.environ.get("TEMP", tempfile.gettempdir()),
                "TMP": os.environ.get("TMP", tempfile.gettempdir()),
                "HOME": str(temp_dir),
                "USERPROFILE": str(temp_dir),
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_NOSYSTEM": "1",
            }
            if token and urlparse(git_url).hostname == "github.com":
                auth_header = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
                clone_env.update({
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
                    "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {auth_header}",
                })
            
            def run_clone():
                return subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=settings.GIT_CLONE_TIMEOUT_SECONDS,
                    env=clone_env,
                )
            
            try:
                res = await asyncio.to_thread(run_clone)
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError(
                    f"Git clone exceeded the {settings.GIT_CLONE_TIMEOUT_SECONDS}-second limit. "
                    "Retry, or use a smaller repository."
                ) from exc
            if res.returncode != 0:
                raise RuntimeError("Git clone failed. Check the repository URL and access permissions.")

            # Scan the full repository root. Framework packages can be under
            # frontend/, client/, apps/web/, or a workspace beside the root manifest.
            root_path = clone_dir

            # 3. Create a clean ZIP archive of the cloned repository in memory
            # Excluding .git, node_modules, .venv, .next, dist, build, etc.
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for r, d, f in os.walk(clone_dir):
                    rel_dir = Path(r).relative_to(clone_dir)
                    if any(x in rel_dir.parts for x in [".git", "node_modules", ".venv", ".next", "dist", "build"]):
                        continue
                    for file in f:
                        file_path = Path(r) / file
                        arcname = file_path.relative_to(clone_dir)
                        zip_file.write(file_path, arcname)

            zip_bytes = zip_buffer.getvalue()

            # 4. Scan files recursively using rule-based scanner
            scan_results = self._scan_project_files(root_path)

            # 5. Get AI analysis using Gemini/OpenAI
            ai_analysis = await self._run_ai_analysis(scan_results)

            # 6. Extract repository name to name the ZIP file
            repo_name = git_url.rstrip("/").split("/")[-1]
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]
            filename = f"{repo_name}.zip"

            return {
                "success": True,
                "project_name": ai_analysis.get("project_name") or repo_name.replace("-", " ").title(),
                "framework_detected": scan_results["framework"],
                "version": scan_results["version"],
                "framework_version": scan_results.get("framework_version"),
                "code_version": scan_results.get("code_version"),
                "is_html_only": scan_results.get("is_html_only", False),
                "language": scan_results["language"],
                "css_system": scan_results["css_system"],
                "ui_library": scan_results["ui_library"],
                "animation_library": scan_results["animation_library"],
                "pages": scan_results["pages"] or ["Home"],
                "components": scan_results["components"] or (["Navbar", "Hero", "Footer"] if scan_results["framework"] != "html" else ["Header", "Content", "Footer"]),
                "categories": ai_analysis.get("categories") or {"Business": 90, "Agency": 85},
                "industry": ai_analysis.get("industry") or ["Marketing", "Software", "SaaS"],
                "color_palette": scan_results["color_palette"] or ["#7C3AED", "#2563EB", "#FFFFFF", "#111827"],
                "typography": scan_results["typography"] or ["Inter"],
                "responsive_analysis": {
                    "desktop": True,
                    "tablet": scan_results["is_responsive"],
                    "mobile": scan_results["is_responsive"],
                },
                "dark_mode": scan_results["has_dark_mode"],
                "seo_analysis": scan_results["seo"],
                "performance_scores": ai_analysis.get("performance_scores") or {
                    "performance": 95,
                    "accessibility": 98,
                    "seo": 96,
                    "best_practices": 98
                },
                "accessibility": scan_results["accessibility"],
                "features_detected": ai_analysis.get("features_detected") or scan_results["features_detected"] or ["Responsive Layout", "CSS Grid"],
                "ai_description": ai_analysis.get("ai_description") or (f"Modern and clean HTML5 website template." if scan_results["framework"] == "html" else f"Modern and fully responsive template built with {scan_results['framework']}."),
                "ai_tags": ai_analysis.get("ai_tags") or ["template", scan_results["framework"]],
                "ai_selling_points": ai_analysis.get("ai_selling_points") or ["Clean codebase", "Fully responsive", "SEO optimized"],
                "ai_score": ai_analysis.get("ai_score") or 95,
                "ai_suggestions": ai_analysis.get("ai_suggestions") or ["Optimize loading speed", "Ensure alt attributes are set"],
                "dependencies": scan_results["dependencies"],
                "assets_count": scan_results["assets_count"],
                # Internals for the api layer
                "_zip_bytes": zip_bytes,
                "_filename": filename,
            }

        finally:
            self._safe_cleanup(temp_dir)

    def _scan_project_files(self, root_path: Path) -> Dict[str, Any]:
        """Runs rule-based scanning over the directory code structures."""
        def clean_ver(v_str: Any) -> str:
            if not v_str:
                return ""
            return re.sub(r"^[^\d]*", "", str(v_str)).strip()

        framework = "html"
        version = "1.0.0"
        framework_version = "HTML5"
        code_version = "1.0.0"
        language = "HTML5 / CSS / JavaScript"
        css_system = "Vanilla CSS"
        ui_library = "None"
        animation_library = "None"
        dependencies = {}
        pages = []
        components = []
        features_detected = []

        # Asset counters
        assets = {
            "images": 0,
            "svg": 0,
            "icons": 0,
            "videos": 0,
            "fonts": 0,
        }

        # Indicators
        has_dark_mode = False
        is_responsive = False
        seo_checks = {
            "meta_title": False,
            "meta_description": False,
            "og_tags": False,
            "twitter_cards": False,
            "robots_txt": False,
            "sitemap_xml": False,
        }
        accessibility_checks = {
            "aria_labels": False,
            "alt_tags": False,
            "keyboard_navigation": False,
            "contrast_safe": True,
        }

        # Color/Typography scanners
        color_freq = {}
        fonts_found = set()

        color_regex = re.compile(r"#(?:[a-fA-F0-9]{3}){1,2}\b")
        font_regex = re.compile(r"font-family:\s*['\"]?([a-zA-Z0-9\s\-_]+)['\"]?")

        # Tracking for fallback framework/language/CSS detection
        extension_counts = {
            ".jsx": 0,
            ".tsx": 0,
            ".vue": 0,
            ".svelte": 0,
            ".astro": 0,
            ".html": 0,
            ".js": 0,
            ".ts": 0,
        }
        has_react_import = False
        has_next_import = False
        has_vue_import = False
        has_svelte_import = False
        has_astro_import = False

        # 1. Inspect all app manifests, including frontend/client/workspace packages.
        manifest_skip_dirs = {"node_modules", ".git", ".next", ".nuxt", "dist", "build", ".venv", "vendor"}
        package_json_paths = []
        root_manifest = root_path / "package.json"
        if root_manifest.is_file():
            package_json_paths.append(root_manifest)
        for manifest_dir, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [name for name in dirnames if name not in manifest_skip_dirs]
            if "package.json" in filenames:
                manifest_path = Path(manifest_dir) / "package.json"
                if manifest_path not in package_json_paths:
                    package_json_paths.append(manifest_path)

        all_deps = {}
        root_package_data = None
        for manifest_path in package_json_paths:
            try:
                with manifest_path.open("r", encoding="utf-8") as package_file:
                    pkg_data = json.load(package_file)
                if not isinstance(pkg_data, dict):
                    continue
                if manifest_path == root_manifest:
                    root_package_data = pkg_data
                deps = pkg_data.get("dependencies") or {}
                dev_deps = pkg_data.get("devDependencies") or {}
                if not isinstance(deps, dict):
                    deps = {}
                if not isinstance(dev_deps, dict):
                    dev_deps = {}
                dependencies.update(deps)
                all_deps.update(deps)
                all_deps.update(dev_deps)
                if root_package_data is None:
                    root_package_data = pkg_data
            except Exception as e:
                logger.warning("Error parsing package manifest %s: %s", manifest_path, e)

        if all_deps:
            pkg_version = (root_package_data or {}).get("version")
            if pkg_version:
                code_version = clean_ver(pkg_version) or "1.0.0"
                version = code_version

            # Framework detection uses dependencies from every app/workspace manifest.
            if "next" in all_deps:
                framework, framework_version = "nextjs", clean_ver(all_deps.get("next", "15.0.0"))
            elif "react" in all_deps:
                framework, framework_version = "react", clean_ver(all_deps.get("react", "19.0.0"))
            elif "nuxt" in all_deps:
                framework, framework_version = "nuxt", clean_ver(all_deps.get("nuxt", "3.0.0"))
            elif "vue" in all_deps:
                framework, framework_version = "vue", clean_ver(all_deps.get("vue", "3.0.0"))
            elif "astro" in all_deps:
                framework, framework_version = "astro", clean_ver(all_deps.get("astro", "4.0.0"))
            elif "@angular/core" in all_deps:
                framework, framework_version = "angular", clean_ver(all_deps.get("@angular/core", "18.0.0"))
            elif "svelte" in all_deps:
                framework, framework_version = "svelte", clean_ver(all_deps.get("svelte", "5.0.0"))
            elif "tailwindcss" in all_deps:
                framework, framework_version = "tailwind", clean_ver(all_deps.get("tailwindcss", "3.4.0"))
            else:
                framework, framework_version = "html", "HTML5"
            if framework != "html":
                version = code_version if code_version != "1.0.0" else framework_version or "1.0.0"
            if framework == "angular":
                language = "TypeScript"
            elif "typescript" in all_deps:
                language = "TypeScript"
            elif framework != "html":
                language = "JavaScript"
            # CSS system
            if "tailwindcss" in all_deps:
                tw_v = clean_ver(all_deps.get("tailwindcss", "3.0"))
                css_system = f"Tailwind CSS v{tw_v}" if tw_v else "Tailwind CSS"
            elif "styled-components" in all_deps:
                css_system = "Styled Components"
            elif "sass" in all_deps or "node-sass" in all_deps:
                css_system = "SASS / SCSS"

            # UI library and animation tools
            if "@radix-ui/react-dialog" in all_deps or "lucide-react" in all_deps:
                ui_library = "Shadcn UI"
            elif "@mui/material" in all_deps:
                ui_library = "Material UI"
            elif "bootstrap" in all_deps:
                ui_library = "Bootstrap"
            if "framer-motion" in all_deps:
                animation_library = "Framer Motion"
            elif "gsap" in all_deps:
                animation_library = "GSAP"

        # 2. File traversal scanning
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [
                name for name in dirnames
                if name not in {"node_modules", ".git", ".next", ".nuxt", "dist", "build", ".venv", "vendor"}
            ]
            dp = Path(dirpath)

            for filename in filenames:
                file_ext = Path(filename).suffix.lower()
                full_file_path = dp / filename

                if file_ext in extension_counts:
                    extension_counts[file_ext] += 1

                # Check assets
                if file_ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico"]:
                    assets["images"] += 1
                if file_ext == ".svg":
                    assets["svg"] += 1
                    # SVG icons
                    if "icon" in filename.lower() or "icons" in dp.parts:
                        assets["icons"] += 1
                if file_ext in [".mp4", ".webm", ".avi", ".mov"]:
                    assets["videos"] += 1
                if file_ext in [".ttf", ".woff", ".woff2", ".otf"]:
                    assets["fonts"] += 1

                # SEO configuration files
                if filename.lower() == "robots.txt":
                    seo_checks["robots_txt"] = True
                if filename.lower() in ["sitemap.xml", "sitemap.js", "sitemap.ts"]:
                    seo_checks["sitemap_xml"] = True

                # Code content analysis
                if file_ext in [".jsx", ".tsx", ".js", ".ts", ".html", ".css", ".vue"]:
                    try:
                        with open(full_file_path, "r", encoding="utf-8", errors="ignore") as code_file:
                            content = code_file.read()

                            # Detect imports for fallback framework detection
                            if "from 'react'" in content or 'from "react"' in content or "import React" in content:
                                has_react_import = True
                            if "from 'next'" in content or 'from "next"' in content or "next/link" in content or "next/router" in content:
                                has_next_import = True
                            if "from 'vue'" in content or 'from "vue"' in content or "<template>" in content:
                                has_vue_import = True
                            if "from 'svelte'" in content or 'from "svelte"' in content:
                                has_svelte_import = True
                            if "from 'astro'" in content or 'from "astro"' in content:
                                has_astro_import = True

                            # Detect Tailwind directives
                            if "@tailwind" in content or "tailwind" in content:
                                if css_system == "Vanilla CSS":
                                    css_system = "Tailwind CSS"

                            # Detect colors
                            for match in color_regex.findall(content):
                                color_freq[match.lower()] = color_freq.get(match.lower(), 0) + 1

                            # Detect fonts
                            for match in font_regex.findall(content):
                                if match.strip():
                                    fonts_found.add(match.strip())

                            # Detect responsiveness
                            if "@media" in content or "sm:" in content or "md:" in content or "lg:" in content or "flex-wrap" in content:
                                is_responsive = True

                            # Detect dark mode
                            if "dark:" in content or "class=\"dark\"" in content or "prefers-color-scheme" in content:
                                has_dark_mode = True

                            # Detect features
                            if "login" in content.lower() or "register" in content.lower() or "signin" in content.lower():
                                if "Authentication" not in features_detected:
                                    features_detected.append("Authentication")
                            if "cart" in content.lower() or "checkout" in content.lower() or "stripe" in content.lower():
                                if "Payment Integration" not in features_detected:
                                    features_detected.append("Payment Integration")
                            if "contact" in content.lower() and ("form" in content.lower() or "input" in content.lower()):
                                if "Contact Form" not in features_detected:
                                    features_detected.append("Contact Form")
                            if "blog" in content.lower():
                                if "Blog Section" not in features_detected:
                                    features_detected.append("Blog Section")

                            # Detect Accessibility
                            if "aria-" in content:
                                accessibility_checks["aria_labels"] = True
                            if "alt=" in content:
                                accessibility_checks["alt_tags"] = True
                            if "tabindex=" in content or "onkeydown" in content or "onkeyup" in content:
                                accessibility_checks["keyboard_navigation"] = True

                            # Detect SEO
                            if "<title>" in content or "title:" in content:
                                seo_checks["meta_title"] = True
                            if "<meta name=\"description\"" in content or "description:" in content:
                                seo_checks["meta_description"] = True
                            if "og:" in content:
                                seo_checks["og_tags"] = True
                            if "twitter:" in content:
                                seo_checks["twitter_cards"] = True

                    except Exception as e:
                        logger.warning(f"Error scanning code file {filename}: {e}")

                if file_ext == ".html":
                    # Add standard HTML page name
                    page_name = Path(filename).stem
                    if page_name == "index":
                        pages.append("Home")
                    else:
                        pages.append(page_name.replace("-", " ").title())

                # Component scanning
                if "components" in dp.parts or "Components" in dp.parts:
                    comp_name = Path(filename).stem
                    if comp_name and comp_name[0].isupper() and comp_name not in components:
                        components.append(comp_name)

        # Fallback framework detection based on files, extensions, and imports if not set via package.json
        if framework.lower() == "html":
            if has_next_import or (extension_counts.get(".tsx", 0) > 0 and has_next_import):
                framework = "nextjs"
                framework_version = "15.0.0"
                version = code_version or "15.0.0"
                language = "TypeScript" if extension_counts.get(".tsx", 0) > 0 else "JavaScript"
            elif has_react_import or extension_counts.get(".tsx", 0) > 0 or extension_counts.get(".jsx", 0) > 0:
                framework = "react"
                framework_version = "19.0.0"
                version = code_version or "19.0.0"
                language = "TypeScript" if extension_counts.get(".tsx", 0) > 0 else "JavaScript"
            elif has_vue_import or extension_counts.get(".vue", 0) > 0:
                framework = "vue"
                framework_version = "3.0.0"
                version = code_version or "3.0.0"
                language = "JavaScript"
            elif has_svelte_import or extension_counts.get(".svelte", 0) > 0:
                framework = "svelte"
                framework_version = "5.0.0"
                version = code_version or "5.0.0"
                language = "JavaScript"
            elif has_astro_import or extension_counts.get(".astro", 0) > 0:
                framework = "astro"
                framework_version = "4.0.0"
                version = code_version or "4.0.0"
                language = "JavaScript"
            else:
                framework = "html"
                framework_version = "HTML5"
                version = code_version or "1.0.0"
                language = "HTML5 / JavaScript / CSS"

        # Language fallback
        if language == "JavaScript":
            if extension_counts.get(".ts", 0) > 0 or extension_counts.get(".tsx", 0) > 0:
                language = "TypeScript"

        for page_name in _discover_framework_pages(root_path, framework):
            pages.append(page_name)
        deduped_pages = []
        seen_pages = set()
        for page_name in pages:
            normalized_page = _page_name_from_route(page_name)
            key = normalized_page.casefold()
            if key not in seen_pages:
                seen_pages.add(key)
                deduped_pages.append(normalized_page)

        # 3. Process colors (select top 5 hex codes, skipping pure white/black if others exist)
        sorted_colors = sorted(color_freq.items(), key=lambda x: x[1], reverse=True)
        filtered_colors = []
        for color, freq in sorted_colors:
            # Skip typical grey scale if color count is high
            if color in ["#ffffff", "#000000", "#fff", "#000", "#111827"]:
                continue
            filtered_colors.append(color)
            if len(filtered_colors) >= 4:
                break
        # Append white and dark grey as standard backups
        filtered_colors.extend(["#FFFFFF", "#111827"])
        color_palette = [c.upper() for c in filtered_colors[:5]]

        # Process typography
        typography = list(fonts_found)[:4]
        # Filter standard fallback fonts
        typography = [f for f in typography if f.lower() not in ["sans-serif", "serif", "monospace", "inherit", "var"]]
        if not typography:
            typography = ["Inter"]

        return {
            "framework": framework,
            "version": version or "1.0.0",
            "framework_version": framework_version or "1.0.0",
            "code_version": code_version or "1.0.0",
            "is_html_only": framework.lower() == "html",
            "language": language,
            "css_system": css_system,
            "ui_library": ui_library,
            "animation_library": animation_library,
            "pages": deduped_pages[:50] or ["Home"],
            "components": components[:15] or (["Navbar", "Hero", "Footer"] if framework.lower() != "html" else ["Header", "Content", "Footer"]),
            "color_palette": color_palette,
            "typography": typography,
            "is_responsive": is_responsive,
            "has_dark_mode": has_dark_mode,
            "seo": seo_checks,
            "accessibility": accessibility_checks,
            "features_detected": features_detected,
            "dependencies": dependencies,
            "assets_count": assets,
        }

    def _detect_backend_project(self, root_path: Path) -> dict:
        """
        Detects whether an uploaded project is a backend/server application
        rather than a frontend web template.
        Returns {is_backend, backend_type, reason}.
        """
        BACKEND_NODE_PKGS = {
            "express", "fastify", "@nestjs/core", "koa", "@hapi/hapi",
            "restify", "sails", "feathers", "@feathersjs/feathers",
            "strapi", "keystone", "@loopback/core", "moleculer",
            "@adonisjs/core", "hapi", "polka", "micro",
        }
        FRONTEND_PKGS = {
            "react", "vue", "next", "nuxt", "svelte", "@sveltejs/kit",
            "astro", "@angular/core", "vite", "gatsby", "@remix-run/react",
            "solid-js", "preact",
        }
        PYTHON_BACKEND_FILES = [
            "manage.py", "wsgi.py", "asgi.py", "app.py",
            "main.py", "run.py", "server.py", "wsgi.py",
        ]
        PYTHON_DEP_FILES = ["requirements.txt", "Pipfile", "setup.py", "pyproject.toml"]

        has_index_html = (root_path / "index.html").exists()
        has_package_json = (root_path / "package.json").exists()
        has_python_deps = any((root_path / f).exists() for f in PYTHON_DEP_FILES)
        has_python_backend_entry = any((root_path / f).exists() for f in PYTHON_BACKEND_FILES)

        # ── Check 1: Python backend project ──────────────────────────────────
        if has_python_deps and not has_index_html:
            backend_type = "Python Backend"
            for dep_file in PYTHON_DEP_FILES:
                dep_path = root_path / dep_file
                if dep_path.exists():
                    try:
                        content = dep_path.read_text(encoding="utf-8", errors="ignore").lower()
                        if "django" in content:
                            backend_type = "Django"
                        elif "fastapi" in content:
                            backend_type = "FastAPI"
                        elif "flask" in content:
                            backend_type = "Flask"
                        elif "tornado" in content:
                            backend_type = "Tornado"
                        elif "aiohttp" in content:
                            backend_type = "AioHTTP"
                    except Exception:
                        pass

            if has_python_deps or has_python_backend_entry:
                return {
                    "is_backend": True,
                    "backend_type": backend_type,
                    "reason": (
                        f"\u26a0\ufe0f This looks like a {backend_type} backend/server project, not a web template. "
                        "Please upload only frontend web templates (HTML, React, Vue, Next.js, Nuxt, Svelte, Astro, etc.). "
                        "Backend projects cannot be previewed or sold as website templates."
                    ),
                }

        # ── Check 2: Node.js backend project ─────────────────────────────────
        if has_package_json and not has_index_html:
            try:
                with open(root_path / "package.json", "r", encoding="utf-8") as f:
                    pkg = json.load(f)
                all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                has_frontend = any(dep in all_deps for dep in FRONTEND_PKGS)
                has_backend  = any(dep in all_deps for dep in BACKEND_NODE_PKGS)

                if has_backend and not has_frontend:
                    detected_pkg = next(
                        (dep for dep in BACKEND_NODE_PKGS if dep in all_deps),
                        "Node.js Backend"
                    )
                    return {
                        "is_backend": True,
                        "backend_type": detected_pkg,
                        "reason": (
                            f"\u26a0\ufe0f This looks like a Node.js backend project ({detected_pkg}), not a web template. "
                            "Please upload only frontend web templates (HTML, React, Vue, Next.js, Nuxt, Svelte, Astro, etc.). "
                            "Backend projects cannot be previewed or sold as website templates."
                        ),
                    }
            except Exception:
                pass

        # ── Check 3: No HTML / JSX / Vue files at all ─────────────────────────
        if not has_index_html and not has_package_json:
            html_files = list(root_path.glob("**/*.html"))
            frontend_files = (
                list(root_path.glob("**/*.jsx"))
                + list(root_path.glob("**/*.tsx"))
                + list(root_path.glob("**/*.vue"))
                + list(root_path.glob("**/*.svelte"))
                + list(root_path.glob("**/*.astro"))
            )
            py_files = list(root_path.glob("**/*.py"))

            if not html_files and not frontend_files and py_files:
                return {
                    "is_backend": True,
                    "backend_type": "Python Project",
                    "reason": (
                        "\u26a0\ufe0f This project contains only Python files with no web template content. "
                        "Please upload only frontend web templates (HTML, React, Vue, Next.js, Nuxt, Svelte, Astro, etc.). "
                        "Backend projects cannot be previewed or sold as website templates."
                    ),
                }

        return {"is_backend": False, "reason": "", "backend_type": ""}

    async def _run_ai_analysis(self, scan_results: Dict[str, Any]) -> Dict[str, Any]:
        """Calls Gemini API (or fallback) to do an analysis of code parameters."""
        prompt = f"""
        You are an intelligent code review agent analyzing a web template project ZIP file.
        Here is the technical metadata of the project we scanned:
        - Framework: {scan_results['framework']} (version {scan_results['version']})
        - Language: {scan_results['language']}
        - CSS: {scan_results['css_system']}
        - UI Library: {scan_results['ui_library']}
        - Animations: {scan_results['animation_library']}
        - Detected Pages: {', '.join(scan_results['pages'])}
        - Detected Components: {', '.join(scan_results['components'])}
        - Core Color Palette: {', '.join(scan_results['color_palette'])}
        - Typography: {', '.join(scan_results['typography'])}
        - Responsive: {scan_results['is_responsive']}
        - Dark Mode: {scan_results['has_dark_mode']}
        - Core features: {', '.join(scan_results['features_detected'])}
        - Total assets count: {json.dumps(scan_results['assets_count'])}

        TAXONOMY & SUBCATEGORY MAPPING RULES:
        - Primary Categories: "Business", "Site Template", "Marketing", "Portfolio", "UI Templates", "Restaurant", "Wordpress", "Healthcare", "E-Commerce", "Education", "Real Estate", "Technology"
        - Sub-Categories:
          * Business: "Corporate", "Startup", "Small Business", "Enterprise", "Consulting", "Finance", "Insurance", "Accounting", "Manufacturing", "Logistics"
          * Site Template: "Landing Page", "Multi-Page", "Single-Page", "One-Page", "Personal", "Resume / CV"
          * Marketing: "Digital Marketing", "SEO Agency", "Social Media", "Email Marketing", "Content Marketing", "Advertising"
          * Portfolio: "Creative", "Designer", "Developer", "Photography", "Architecture", "Videographer", "Freelancer"
          * UI Templates: "Dashboard", "Admin Panel", "Component Library", "Design System", "Mobile UI", "Web App"
          * Restaurant: "Cafe", "Bakery", "Fine Dining", "Bar & Pub", "Fast Food", "Coffee Shop", "Food Truck", "Catering"
          * Healthcare: "Clinic", "Dental", "Medical", "Pharmacy", "Hospital", "Mental Health", "Fitness & Wellness"

        Generate an AI Analysis Report JSON. You must return ONLY a valid JSON object matching these exact keys:
        {{
          "project_name": "A premium marketing name for this template (e.g. Modern Agency Pro, SaaSify Landing Page, Corporate Flow, Ledger Accounting Suite)",
          "ai_description": "A high-converting, professional, 2-3 sentence marketplace description.",
          "ai_tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6"],
          "categories": {{
            "Business": 95,
            "Marketing": 80
          }},
          "sub_category": "Exact matching subcategory name from the taxonomy list above (e.g. Small Business, Accounting, Dashboard, Cafe, Clinic, Landing Page)",
          "industry": ["Marketing", "Software", "SaaS", "Creative"],
          "ai_selling_points": [
            "SEO Optimized Out of the Box",
            "Fully Responsive on Mobile/Tablet",
            "Modern aesthetic with curated color scheme",
            "Dynamic animations configured",
            "Clean component layout architecture"
          ],
          "performance_scores": {{
            "performance": 96,
            "accessibility": 99,
            "seo": 98,
            "best_practices": 100
          }},
          "features_detected": ["Contact Form", "Dark Mode", "Framer Motion", "Shadcn UI", "Responsive Design"],
          "ai_score": 96,
          "ai_suggestions": [
            "Add a robots.txt file to optimize SEO crawl budget.",
            "Compress hero images in public/ folder to improve loading speed.",
            "Ensure ARIA labels are added to custom mobile menus.",
            "Minify custom Vanilla CSS styles."
          ]
        }}
        Return ONLY valid JSON. Do not include markdown code block syntax (like ```json ... ```).
        """

        # Try running analysis via ai_service (Gemini with Azure Fallback)
        from app.services.ai_service import ai_service, robust_json_loads
        if ai_service.client:
            try:
                response_text = await ai_service._generate_content(
                    prompt,
                    response_mime_type="application/json",
                    feature_name="project_zip_analysis"
                )
                return robust_json_loads(response_text)
            except Exception as e:
                logger.error(f"AI analysis failed via ai_service: {e}")

        # Check for legacy OpenAI fallback (if configured directly)
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "sk-...":
            try:
                from openai import AsyncOpenAI
                openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                response = await openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    response_format={"type": "json_object"},
                )
                return json.loads(response.choices[0].message.content)
            except Exception as e:
                logger.error(f"OpenAI fallback call failed: {e}")

        # Mock fallback if no API keys are configured
        logger.warning("No AI keys found or API calls failed. Using mock rule-based analyzer.")
        return self._generate_mock_analysis(scan_results)

    def _generate_mock_analysis(self, scan_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generates standard parameters based on project parameters when no LLM key is set."""
        frame = scan_results["framework"].title()
        if frame == "Nextjs":
            frame = "Next.js"
        name = f"Modern {frame} Template"
        desc = f"A premium and highly responsive website template built with {frame}, {scan_results['css_system']}, and {scan_results['language']}. Optimized for fast performance and customizability."

        tags = [scan_results["framework"].lower(), scan_results["language"].lower(), "responsive", "ui", "business"]
        if "tailwind" in scan_results["css_system"].lower():
            tags.append("tailwind")
        if scan_results["has_dark_mode"]:
            tags.append("darkmode")

        # Determine subcategory and category heuristically from detected features, pages, components, and filenames
        page_str = " ".join(scan_results.get("pages", [])).lower()
        comp_str = " ".join(scan_results.get("components", [])).lower()
        all_txt = f"{page_str} {comp_str}"

        category = "Business"
        sub_cat = "Small Business"

        if "portfolio" in all_txt or "resume" in all_txt or "cv" in all_txt or "designer" in all_txt or "developer" in all_txt or "showcase" in all_txt:
            category = "Portfolio"
            sub_cat = "Creative"
            tags.extend(["portfolio", "resume", "designer", "showcase"])
        elif "shop" in all_txt or "cart" in all_txt or "product" in all_txt or "store" in all_txt or "ecommerce" in all_txt:
            category = "E-Commerce"
            sub_cat = "Digital Store"
            tags.extend(["ecommerce", "store", "shop"])
        elif "restaurant" in all_txt or "menu" in all_txt or "food" in all_txt or "cafe" in all_txt or "bistro" in all_txt:
            category = "Restaurant"
            sub_cat = "Cafe"
            tags.extend(["restaurant", "cafe", "food"])
        elif "doctor" in all_txt or "clinic" in all_txt or "hospital" in all_txt or "health" in all_txt or "medical" in all_txt:
            category = "Healthcare"
            sub_cat = "Clinic"
            tags.extend(["health", "medical", "clinic"])
        elif "estate" in all_txt or "property" in all_txt or "house" in all_txt or "listing" in all_txt or "realtor" in all_txt:
            category = "Real Estate"
            sub_cat = "Property Listing"
            tags.extend(["real-estate", "property", "realtor"])
        elif "accounting" in all_txt or "invoice" in all_txt or "tax" in all_txt:
            category = "Business"
            sub_cat = "Accounting"
            tags.extend(["accounting", "finance", "invoice"])
        elif "finance" in all_txt or "crypto" in all_txt or "banking" in all_txt:
            category = "Business"
            sub_cat = "Finance"
            tags.extend(["finance", "fintech"])
        elif "dashboard" in all_txt or "admin" in all_txt or "analytics" in all_txt:
            category = "Technology"
            sub_cat = "Dashboard"
            tags.extend(["dashboard", "admin", "tech"])
        elif "agency" in all_txt or "studio" in all_txt or "creative" in all_txt:
            category = "Agency"
            sub_cat = "Creative Agency"
            tags.extend(["agency", "studio"])
        else:
            category = "Business"
            sub_cat = "Small Business"
            tags.extend(["business", "corporate", "startup"])

        features = ["Responsive Design"]
        if scan_results["has_dark_mode"]:
            features.append("Dark Mode")
        if scan_results["framework"] == "nextjs":
            features.append("App Routing")
        if scan_results["ui_library"] != "None":
            features.append(scan_results["ui_library"])

        suggestions = []
        if not scan_results["seo"]["robots_txt"]:
            suggestions.append("Add a robots.txt file to optimize SEO crawler mapping.")
        if not scan_results["seo"]["sitemap_xml"]:
            suggestions.append("Incorporate an automated sitemap.xml for indexing.")
        if not scan_results["accessibility"]["aria_labels"]:
            suggestions.append("Improve navigation accessibility with explicit ARIA tags.")
        if not suggestions:
            suggestions.append("Optimize assets and code loading speeds.")

        categories = {category: 98}
        if category != "Business":
            categories["Business"] = 60
        if category != "Agency":
            categories["Agency"] = 55
        if "Authentication" in scan_results["features_detected"]:
            categories["Technology"] = 90

        # Unique tags
        clean_tags = list(dict.fromkeys([t.lower().replace("#", "").strip() for t in tags if t.strip()]))

        return {
            "project_name": name,
            "ai_description": desc,
            "ai_tags": clean_tags,
            "categories": categories,
            "sub_category": sub_cat,
            "industry": [category, sub_cat, "Software"],
            "ai_selling_points": [
                f"Built using production-ready {frame}",
                "Curated modern brand styling",
                "Fully mobile-responsive layout and grids",
                "SEO meta setups ready",
            ],
            "performance_scores": {
                "performance": 94,
                "accessibility": 96,
                "seo": 92,
                "best_practices": 95,
            },
            "features_detected": features,
            "ai_score": 94,
            "ai_suggestions": suggestions,
        }

project_analyzer = ProjectAnalyzer()
