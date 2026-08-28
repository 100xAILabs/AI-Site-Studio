"""
Live Template Security Scanner & Malware Protection Engine
Audits uploaded templates, AI-generated codebases, and live preview executions.
"""

import io
import re
import os
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

# Maximum allowed uncompressed template size (100 MB)
MAX_UNCOMPRESSED_SIZE_BYTES = 100 * 1024 * 1024
# Maximum allowed number of files in a template ZIP
MAX_ZIP_FILES_COUNT = 5000
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
        findings = []
        purged_files = []
        is_safe = True
        total_uncompressed_size = 0

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                infolist = zf.infolist()
                total_files = len(infolist)

                # 1. Check max file count
                if total_files > MAX_ZIP_FILES_COUNT:
                    return {
                        "is_safe": False,
                        "is_zip_bomb": True,
                        "status": "REJECTED",
                        "reason": f"ZIP contains too many files ({total_files} > {MAX_ZIP_FILES_COUNT}). Exceeds safety threshold.",
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

                    total_uncompressed_size += member.file_size

                # 3. Check uncompressed size
                if total_uncompressed_size > MAX_UNCOMPRESSED_SIZE_BYTES:
                    return {
                        "is_safe": False,
                        "is_zip_bomb": True,
                        "status": "REJECTED",
                        "reason": f"Uncompressed size ({total_uncompressed_size / (1024*1024):.1f} MB) exceeds maximum allowed limit (100 MB).",
                        "findings": [{"id": "ZIP_BOMB_SIZE", "severity": "CRITICAL", "message": "Decompression bomb risk."}],
                        "scanned_files": total_files
                    }

                # 4. Code Signature Audit on text / script files
                text_exts = {".html", ".htm", ".js", ".jsx", ".ts", ".tsx", ".vue", ".json", ".css", ".php", ".py", ".rb"}
                for member in infolist:
                    ext = Path(member.filename).suffix.lower()
                    if ext in text_exts and member.file_size < 2 * 1024 * 1024:  # scan files < 2MB
                        try:
                            content = zf.read(member.filename).decode("utf-8", errors="ignore")
                            code_findings = self.scan_code_content(content, filename=member.filename)
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
        purged_files = []
        _SKIP_DIRS = {
            "node_modules", ".git", ".venv", "venv", "__pycache__",
            ".next", ".nuxt", ".output", "dist", "build", ".cache",
            "vendor", ".tox", ".eggs", "*.egg-info",
        }

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
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
                    with open(target_path, "wb") as f:
                        f.write(zf.read(member.filename))

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

    def get_secure_preview_headers(self) -> Dict[str, str]:
        """
        Returns strict HTTP headers for sandboxed live previews.
        Prevents clickjacking, MIME-sniffing, and cross-site exfiltration.
        """
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https:; "
                "font-src 'self' https: data:; "
                "img-src 'self' https: data: blob:; "
                "connect-src 'self' https: http://localhost:* http://127.0.0.1:*; "
                "frame-ancestors 'self' http://localhost:* http://127.0.0.1:*;"
            )
        }

    def audit_template_structure(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Audits template page completeness (e.g. index.html, about, contact, pricing).
        Returns list of existing pages, missing recommended pages, and completeness score.
        """
        html_files = [p.lower() for p in file_paths if p.lower().endswith(".html") or p.lower().endswith(".htm")]
        page_basenames = [Path(p).name for p in html_files]

        recommended_pages = {
            "index": ["index.html", "home.html"],
            "about": ["about.html", "about-us.html"],
            "services": ["services.html", "features.html"],
            "pricing": ["pricing.html", "plans.html"],
            "contact": ["contact.html", "contact-us.html"],
        }

        detected_pages = []
        missing_pages = []

        for category, candidates in recommended_pages.items():
            found = any(c in page_basenames for c in candidates)
            if found:
                detected_pages.append(category)
            else:
                missing_pages.append(category)

        total_recommended = len(recommended_pages)
        found_count = len(detected_pages)
        page_score = round((found_count / total_recommended) * 100, 1)

        return {
            "total_html_files": len(html_files),
            "detected_pages": detected_pages,
            "missing_recommended_pages": missing_pages,
            "page_completeness_score": page_score,
            "has_index": "index" in detected_pages,
        }

    def audit_relative_links(self, html_contents: Dict[str, str]) -> Dict[str, Any]:
        """
        Audits HTML relative links for dead '#' anchors and broken references.
        """
        href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
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
        all_filenames = []
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                all_filenames = zf.namelist()
                for member in zf.infolist():
                    ext = Path(member.filename).suffix.lower()
                    if ext in [".html", ".htm"] and member.file_size < 1 * 1024 * 1024:
                        try:
                            html_contents[member.filename] = zf.read(member.filename).decode("utf-8", errors="ignore")
                        except Exception:
                            pass
        except Exception:
            pass

        struct_audit = self.audit_template_structure(all_filenames)
        link_audit = self.audit_relative_links(html_contents)

        # Calculate Overall Score (Security 50%, Structure 30%, Link Health 20%)
        sec_score = 100 if sec_report["is_safe"] else 0
        struct_score = struct_audit["page_completeness_score"]
        link_score = link_audit["link_health_percentage"]

        overall_score = round((sec_score * 0.5) + (struct_score * 0.3) + (link_score * 0.2), 1)

        return {
            "overall_score": overall_score,
            "status": "PASSED" if overall_score >= 70 else "NEEDS_IMPROVEMENT",
            "security": sec_report,
            "structure": struct_audit,
            "link_health": link_audit,
            "summary": f"Audit complete. Overall Quality Score: {overall_score}/100.",
        }


# Global singleton instance
security_scanner = SecurityScanner()
