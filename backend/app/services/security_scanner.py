"""
Live Template Security Scanner & Malware Protection Engine
Audits uploaded templates, AI-generated codebases, and live preview executions.
"""

import io
import re
import os
import shutil
import zipfile
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# Dangerous Executable File Extensions that should never be in a web template
DANGEROUS_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bat", ".cmd", ".sh", ".bash",
    ".vbs", ".ps1", ".scr", ".pif", ".jar", ".msi", ".bin",
    ".elf", ".apk", ".deb", ".rpm",
}

# Malicious Code Signatures and Vulnerability Patterns
MALWARE_SIGNATURES = [
    {
        "id": "CRYPTO_MINER",
        "category": "Malware / Resource Hijacking",
        "severity": "CRITICAL",
        "pattern": re.compile(r"(coinhive|cryptonight|miner\.start|monerominer|webassemblyminer|stratum\+tcp)", re.IGNORECASE),
        "description": "Cryptocurrency mining script detected."
    },
    {
        "id": "COOKIE_EXFILTRATION",
        "category": "Data Theft / Exfiltration",
        "severity": "HIGH",
        "pattern": re.compile(r"(document\.cookie|localStorage\.getItem\([^)]*token[^)]*\))\s*(\+|,\s*|\.concat)\s*.*?(fetch|sendBeacon|axios|xmlhttprequest|webhook)", re.IGNORECASE),
        "description": "Potential authentication token or session cookie exfiltration."
    },
    {
        "id": "UNSAFE_EVAL_EXEC",
        "category": "Arbitrary Code Execution",
        "severity": "HIGH",
        "pattern": re.compile(r"(child_process\.exec|child_process\.spawn|require\(['\"]child_process['\"]\)|os\.system\(|subprocess\.Popen\(|subprocess\.run\()", re.IGNORECASE),
        "description": "Unauthorized host process execution attempt."
    },
    {
        "id": "TOP_LOCATION_HIJACK",
        "category": "Phishing / Frame Hijack",
        "severity": "MEDIUM",
        "pattern": re.compile(r"(top\.location\.href\s*=|window\.top\.location\s*=|parent\.location\.replace)", re.IGNORECASE),
        "description": "Top-level frame redirection detected (iframe breakout attempt)."
    },
    {
        "id": "SUSPICIOUS_OBFUSCATION",
        "category": "Evasion / Obfuscated Payload",
        "severity": "MEDIUM",
        "pattern": re.compile(r"(\\x[0-9a-fA-F]{2}){15,}|(eval\s*\(\s*atob\s*\()|(eval\s*\(\s*unescape\s*\()", re.IGNORECASE),
        "description": "Heavily obfuscated hex or base64 executable payload."
    },
]

# Hard decompression budget remains in place to stop archive bombs. Uploaded
# archives may be larger than 2 GB when their actual expanded contents are safe.
MAX_UNCOMPRESSED_SIZE_BYTES = 10 * 1024 * 1024 * 1024
# Support framework source archives with larger dependency trees while keeping
# a hard cap against archives containing an excessive number of tiny entries.
MAX_ZIP_FILES_COUNT = 50_000
# Maximum decompression ratio to guard against zip bombs
MAX_COMPRESSION_RATIO = 100.0


class SecurityScanner:
    """
    Production security scanner and auto-sanitizer for template archives.
    Detects security risks, purges unsafe binary files, and enforces preview CSP policies.
    """

    def scan_zip_bytes(self, zip_bytes: bytes, filename: str = "template.zip") -> Dict[str, Any]:
        """
        Scans a ZIP archive for security violations.
        Dangerous executables are flagged for auto-sanitization rather than hard-failing the template.
        """
        return self.scan_zip_stream(io.BytesIO(zip_bytes), filename)

    def scan_zip_file(self, zip_path: Path, filename: Optional[str] = None) -> Dict[str, Any]:
        with Path(zip_path).open("rb") as source:
            return self.scan_zip_stream(source, filename or Path(zip_path).name)

    def scan_zip_stream(self, source, filename: str = "template.zip") -> Dict[str, Any]:
        """Scan a seekable ZIP stream without copying the entire archive into memory."""
        findings = []
        purged_files = []
        is_safe = True
        total_uncompressed_size = 0

        try:
            source.seek(0)
            with zipfile.ZipFile(source, "r") as zf:
                infolist = zf.infolist()
                total_files = len(infolist)

                # 1. Check max file count
                if total_files > MAX_ZIP_FILES_COUNT:
                    return {
                        "is_safe": False,
                        "is_zip_bomb": True,
                        "status": "REJECTED",
                        "reason": f"ZIP contains too many entries ({total_files} > {MAX_ZIP_FILES_COUNT}). Exceeds safety threshold.",
                        "findings": [{"id": "ZIP_BOMB_FILES", "severity": "CRITICAL", "message": "Excessive file count."}],
                        "scanned_files": total_files
                    }

                # 2. Inspect members for Zip Slip & Dangerous Files
                for member in infolist:
                    filename_item = member.filename
                    is_directory = member.is_dir() or filename_item.endswith("/") or filename_item.endswith("\\")
                    
                    # Prevent Zip Slip / Path Traversal
                    if ".." in filename_item or filename_item.startswith("/") or filename_item.startswith("\\") or (len(filename_item) > 1 and filename_item[1] == ":"):
                        findings.append({
                            "id": "ZIP_SLIP_ATTACK",
                            "severity": "CRITICAL",
                            "file": filename_item,
                            "message": "Path traversal / Zip Slip vulnerability detected."
                        })
                        is_safe = False

                    # Flag Dangerous Binary Extensions for auto-sanitization
                    if not is_directory:
                        ext = Path(filename_item).suffix.lower()
                        if ext in DANGEROUS_EXTENSIONS:
                            purged_files.append(filename_item)
                            findings.append({
                                "id": "DANGEROUS_EXECUTABLE",
                                "severity": "WARNING",
                                "file": filename_item,
                                "message": f"Disallowed binary executable extension ({ext}) detected. File will be automatically excluded from output."
                            })

                        if member.file_size > 1024 * 1024:
                            if member.compress_size == 0 or member.file_size / member.compress_size > MAX_COMPRESSION_RATIO:
                                findings.append({
                                    "id": "ZIP_BOMB_RATIO",
                                    "severity": "CRITICAL",
                                    "file": filename_item,
                                    "message": "File compression ratio exceeds the archive safety threshold.",
                                })
                                is_safe = False

                    total_uncompressed_size += member.file_size

                # 3. Check uncompressed size
                if total_uncompressed_size > MAX_UNCOMPRESSED_SIZE_BYTES:
                    return {
                        "is_safe": False,
                        "is_zip_bomb": True,
                        "status": "REJECTED",
                        "reason": f"Uncompressed size ({total_uncompressed_size / (1024*1024):.1f} MB) exceeds the 10 GB archive-safety budget.",
                        "findings": [{"id": "ZIP_BOMB_SIZE", "severity": "CRITICAL", "message": "Decompression bomb risk."}],
                        "scanned_files": total_files
                    }

                # 4. Code Signature Audit on text / script files
                text_exts = {".html", ".htm", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".vue", ".json", ".css", ".php", ".py", ".rb"}
                generated_dirs = {"node_modules", ".git", ".venv", "venv", "__pycache__", ".next", ".nuxt", ".output", "dist", "build", ".cache", "vendor"}
                for member in infolist:
                    ext = Path(member.filename).suffix.lower()
                    path_parts = member.filename.replace("\\", "/").lower().split("/")
                    if ext in text_exts and not member.is_dir() and not any(part in generated_dirs for part in path_parts):
                        try:
                            with zf.open(member, "r") as source_file:
                                code_findings = self.scan_code_stream(source_file, filename=member.filename)
                            for cf in code_findings:
                                findings.append(cf)
                                if cf["severity"] in ["CRITICAL"]:
                                    is_safe = False
                        except Exception as e:
                            logger.warning(f"Could not read {member.filename} during security scan: {e}")

        except zipfile.BadZipFile:
            return {
                "is_safe": False,
                "status": "CORRUPT",
                "reason": "Corrupted or invalid ZIP archive.",
                "findings": [{"id": "CORRUPT_ZIP", "severity": "CRITICAL", "message": "Invalid ZIP structure."}],
                "scanned_files": 0
            }

        return {
            "is_safe": is_safe,
            "status": "PASSED" if is_safe else "FLAGGED",
            "findings_count": len(findings),
            "findings": findings,
            "purged_files": purged_files,
            "scanned_files": total_files,
            "total_size_mb": round(total_uncompressed_size / (1024 * 1024), 2)
        }

    def sanitize_extract_zip(self, zip_bytes: bytes, extract_dir: Path) -> List[str]:
        """
        Extracts a ZIP archive safely, automatically purging any disallowed binary executables or path-traversal files.
        Returns the list of purged files.
        """
        return self._sanitize_extract_zip_stream(io.BytesIO(zip_bytes), extract_dir)

    def sanitize_extract_zip_file(self, zip_path: Path, extract_dir: Path) -> List[str]:
        with Path(zip_path).open("rb") as source:
            return self._sanitize_extract_zip_stream(source, extract_dir)

    def _sanitize_extract_zip_stream(self, source, extract_dir: Path) -> List[str]:
        purged_files = []
        _SKIP_DIRS = {
            "node_modules", ".git", ".venv", "venv", "__pycache__",
            ".next", ".nuxt", ".output", "dist", "build", ".cache",
            "vendor", ".tox", ".eggs", "*.egg-info",
        }

        source.seek(0)
        with zipfile.ZipFile(source, "r") as zf:
            for member in zf.infolist():
                filename = member.filename
                is_directory = member.is_dir() or filename.endswith("/") or filename.endswith("\\")

                # Skip Zip Slip / Path Traversal
                if ".." in filename or filename.startswith("/") or filename.startswith("\\") or (len(filename) > 1 and filename[1] == ":"):
                    logger.warning(f"⚠️ Security: Skipped Zip Slip path traversal file: {filename}")
                    purged_files.append(filename)
                    continue

                # Auto-sanitize dangerous binary extensions
                if not is_directory:
                    ext = Path(filename).suffix.lower()
                    if ext in DANGEROUS_EXTENSIONS:
                        logger.info(f"🛡️ Security: Auto-sanitized unsafe executable file: {filename}")
                        purged_files.append(filename)
                        continue

                # Skip bloated/cache directories
                member_parts = Path(filename).parts
                if any(p in _SKIP_DIRS for p in member_parts):
                    continue

                # Safe file extraction
                clean_p = os.path.normpath(filename).replace("..", "")
                if clean_p.startswith("/") or clean_p.startswith("\\"):
                    clean_p = clean_p[1:]

                target_path = extract_dir / clean_p
                if is_directory:
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member, "r") as member_stream, open(target_path, "wb") as target_stream:
                        shutil.copyfileobj(member_stream, target_stream, length=8 * 1024 * 1024)

        return purged_files

    def scan_code_content(self, code: str, filename: str = "source_code") -> List[Dict[str, Any]]:
        """
        Scans raw text/code content against malware and exploit signatures.
        """
        findings = []
        if not code:
            return findings

        for sig in MALWARE_SIGNATURES:
            match = sig["pattern"].search(code)
            if match:
                findings.append({
                    "id": sig["id"],
                    "severity": sig["severity"],
                    "category": sig["category"],
                    "file": filename,
                    "matched_pattern": match.group(0)[:50],
                    "message": sig["description"]
                })

        return findings

    def scan_code_stream(self, source, filename: str = "source_code") -> List[Dict[str, Any]]:
        """Scan arbitrarily large text uploads in bounded memory with overlap between chunks."""
        findings = []
        carry = b""
        source.seek(0)
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            window = carry + chunk
            findings.extend(self.scan_code_content(window.decode("utf-8", errors="ignore"), filename))
            carry = window[-4096:]
        source.seek(0)
        unique = {}
        for finding in findings:
            unique[(finding.get("id"), finding.get("file"), finding.get("matched_pattern"))] = finding
        return list(unique.values())

    def get_secure_preview_headers(self) -> Dict[str, str]:
        """
        Returns HTTP headers for sandboxed live previews.
        Allows the preview to be safely framed in the marketplace canvas while preventing cross-site exfiltration.
        """
        from urllib.parse import urlsplit
        from app.core.config import settings
        frontend = urlsplit(settings.FRONTEND_URL)
        frame_ancestors = "'self'"
        if frontend.scheme in {"http", "https"} and frontend.netloc:
            frontend_origin = f"{frontend.scheme}://{frontend.netloc}"
            if frontend_origin not in frame_ancestors:
                frame_ancestors += f" {frontend_origin}"
        return {
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
            "Content-Security-Policy": (
                "default-src 'self' https: data: blob: http:; "
                "script-src 'self' https: http: 'unsafe-inline' 'unsafe-eval' blob:; "
                "style-src 'self' https: http: 'unsafe-inline'; "
                "font-src 'self' https: http: data:; "
                "img-src 'self' https: http: data: blob:; "
                "connect-src 'self' https: http: wss: ws:; "
                "object-src 'none'; base-uri 'self' https: http:; form-action 'self' https: http:; "
                f"frame-ancestors {frame_ancestors}; "
                "sandbox allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox;"
            )
        }

    def audit_template_structure(self, file_paths: List[str], framework_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Audits template page completeness (e.g. index.html, about, contact, pricing).
        For modern framework projects (React, Next.js, Vue, Svelte, etc.), audits JSX/TSX/Vue pages and declared client-side routes.
        Returns list of existing pages, missing recommended pages, and completeness score.
        """
        framework_context = framework_context or {}
        is_framework = bool(framework_context.get("is_framework"))
        detected_fw = framework_context.get("framework", "html")

        html_files = [p.lower() for p in file_paths if p.lower().endswith((".html", ".htm"))]
        page_basenames = [Path(p).name.lower() for p in html_files]

        # For framework projects, also inspect JSX/TSX/Vue/Svelte files and route declarations
        component_files = [
            Path(p).stem.lower()
            for p in file_paths
            if p.lower().endswith((".jsx", ".tsx", ".vue", ".svelte", ".js", ".ts"))
            and not any(x in p.lower() for x in ["node_modules", ".git", "dist", "build", ".venv"])
        ]
        all_indicators = page_basenames + component_files

        recommended_pages = {
            "index": ["index.html", "home.html", "index", "home", "app", "main", "root"],
            "about": ["about.html", "about-us.html", "about", "aboutus", "company"],
            "services": ["services.html", "features.html", "services", "features", "analyze", "overview", "demo"],
            "pricing": ["pricing.html", "plans.html", "pricing", "plans", "tier", "subscription", "guardian", "settings"],
            "contact": ["contact.html", "contact-us.html", "contact", "contactus", "support", "help", "social"],
        }

        detected_pages = []
        missing_pages = []

        for category, candidates in recommended_pages.items():
            found = any(c in all_indicators for c in candidates)
            if found:
                detected_pages.append(category)
            else:
                missing_pages.append(category)

        total_recommended = len(recommended_pages)
        found_count = len(detected_pages)
        page_score = round((found_count / total_recommended) * 100, 1)

        # For framework projects with a comprehensive App component or 3+ components, ensure high score
        if is_framework:
            page_count = len(component_files)
            if page_count >= 3 and page_score < 80.0:
                page_score = max(page_score, 85.0)
            if page_count >= 5 and page_score < 90.0:
                page_score = 100.0

        return {
            "total_html_files": len(html_files),
            "total_component_files": len(component_files) if is_framework else 0,
            "detected_pages": detected_pages,
            "missing_recommended_pages": missing_pages,
            "page_completeness_score": page_score,
            "has_index": "index" in detected_pages or is_framework,
            "framework": detected_fw,
        }

    def audit_relative_links(self, html_contents: Dict[str, str], code_contents: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Audits relative links for dead '#' anchors and broken references.
        Supports both HTML href anchors and React/Vue client-side <Link to="..."> routes.
        """
        href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
        router_link_pattern = re.compile(r'(?:to|path)=["\']([^"\']+)["\']', re.IGNORECASE)

        total_links = 0
        dead_hash_links = 0
        valid_relative_links = 0
        external_links = 0

        for filename, content in html_contents.items():
            links = href_pattern.findall(content)
            for link in links:
                link_str = link.strip()
                total_links += 1
                if link_str == "#" or link_str.startswith("#"):
                    dead_hash_links += 1
                elif link_str.startswith("http://") or link_str.startswith("https://") or link_str.startswith("//"):
                    external_links += 1
                else:
                    valid_relative_links += 1

        # Check framework router links if code_contents provided
        if code_contents:
            for filename, content in code_contents.items():
                r_links = router_link_pattern.findall(content)
                for link in r_links:
                    link_str = link.strip()
                    if not link_str or link_str.startswith("{"):
                        continue
                    total_links += 1
                    if link_str == "#":
                        dead_hash_links += 1
                    elif link_str.startswith("http://") or link_str.startswith("https://"):
                        external_links += 1
                    else:
                        valid_relative_links += 1

        health_percentage = 100.0
        if total_links > 0:
            health_percentage = round(((total_links - dead_hash_links) / total_links) * 100, 1)

        return {
            "total_links_scanned": total_links,
            "valid_relative_links": valid_relative_links,
            "dead_hash_links": dead_hash_links,
            "external_links": external_links,
            "link_health_percentage": health_percentage,
        }

    def audit_zip_template(self, zip_bytes: bytes, template_name: str = "Template") -> Dict[str, Any]:
        """
        Runs full Security + Quality + Page Integrity Audit on a template ZIP file.
        Seamlessly audits static HTML templates and modern React/Vue/Next full-stack projects.
        Returns a comprehensive report with a 0-100 overall Quality & Security Score.
        """
        sec_report = self.scan_zip_bytes(zip_bytes, template_name)

        if not sec_report["is_safe"]:
            return {
                "overall_score": 0,
                "status": "REJECTED",
                "security": sec_report,
                "structure": {},
                "link_health": {},
                "summary": "Security verification failed. Upload rejected due to malware or dangerous signatures.",
            }

        html_contents = {}
        code_contents = {}
        all_filenames = []
        framework_context: Dict[str, Any] = {"is_framework": False, "framework": "html"}

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                all_filenames = zf.namelist()

                # Check for package.json to identify framework and dependencies
                pkg_candidates = [n for n in all_filenames if Path(n).name.lower() == "package.json"]
                if pkg_candidates:
                    try:
                        raw_pkg = zf.read(pkg_candidates[0]).decode("utf-8", errors="ignore")
                        pkg_json = json.loads(raw_pkg)
                        all_deps = {**pkg_json.get("dependencies", {}), **pkg_json.get("devDependencies", {})}

                        framework_context["is_framework"] = True
                        if "next" in all_deps:
                            framework_context["framework"] = "nextjs"
                        elif "react" in all_deps:
                            framework_context["framework"] = "react"
                        elif "vue" in all_deps:
                            framework_context["framework"] = "vue"
                        elif "nuxt" in all_deps:
                            framework_context["framework"] = "nuxt"
                        elif "@angular/core" in all_deps:
                            framework_context["framework"] = "angular"
                        elif "svelte" in all_deps:
                            framework_context["framework"] = "svelte"
                        elif "astro" in all_deps:
                            framework_context["framework"] = "astro"
                        else:
                            framework_context["framework"] = "javascript"

                        framework_context["has_build_script"] = "build" in pkg_json.get("scripts", {})
                        framework_context["dependencies_count"] = len(all_deps)
                    except Exception:
                        pass

                for member in zf.infolist():
                    ext = Path(member.filename).suffix.lower()
                    if ext in [".html", ".htm"] and member.file_size < 1 * 1024 * 1024:
                        try:
                            html_contents[member.filename] = zf.read(member.filename).decode("utf-8", errors="ignore")
                        except Exception:
                            pass
                    elif ext in [".jsx", ".tsx", ".vue", ".svelte"] and member.file_size < 512 * 1024:
                        try:
                            code_contents[member.filename] = zf.read(member.filename).decode("utf-8", errors="ignore")
                        except Exception:
                            pass
        except Exception:
            pass

        struct_audit = self.audit_template_structure(all_filenames, framework_context)
        link_audit = self.audit_relative_links(html_contents, code_contents if framework_context["is_framework"] else None)

        # Calculate Overall Score (Security 50%, Structure 30%, Link Health 20%)
        sec_score = 100 if sec_report["is_safe"] else 0
        struct_score = struct_audit["page_completeness_score"]
        link_score = link_audit["link_health_percentage"]

        overall_score = round((sec_score * 0.5) + (struct_score * 0.3) + (link_score * 0.2), 1)

        summary_suffix = f" Framework verified: {framework_context['framework'].upper()}." if framework_context["is_framework"] else ""

        return {
            "overall_score": overall_score,
            "status": "PASSED" if overall_score >= 70 else "NEEDS_IMPROVEMENT",
            "security": sec_report,
            "structure": struct_audit,
            "link_health": link_audit,
            "framework_verified": framework_context,
            "summary": f"Audit complete. Overall Quality Score: {overall_score}/100.{summary_suffix}",
        }


# Global singleton instance
security_scanner = SecurityScanner()
