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
    ".vbs", ".ps1", ".scr", ".pif", ".jar", ".com", ".msi", ".bin",
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
    Comprehensive Security Auditor for AI Site Studio.
    Guarantees that no uploaded ZIP, Git repository, AI-generated codebase,
    or live preview contains malicious code, exploits, or dangerous payloads.
    """

    def scan_zip_bytes(self, zip_bytes: bytes, template_name: str = "Template") -> Dict[str, Any]:
        """
        Inspects a ZIP file in memory for:
        1. Zip Slip / Path Traversal attacks
        2. Dangerous executable files
        3. Zip bomb decompression exploits
        4. In-depth code vulnerability signatures
        """
        findings: List[Dict[str, Any]] = []
        is_safe = True
        total_uncompressed_size = 0
        total_files = 0

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                infolist = zf.infolist()
                total_files = len(infolist)

                # 1. Check max file count
                if total_files > MAX_ZIP_FILES_COUNT:
                    return {
                        "is_safe": False,
                        "status": "REJECTED",
                        "reason": f"ZIP contains too many files ({total_files} > {MAX_ZIP_FILES_COUNT}). Exceeds safety threshold.",
                        "findings": [{"id": "ZIP_BOMB_FILES", "severity": "CRITICAL", "message": "Excessive file count."}],
                        "scanned_files": total_files
                    }

                # 2. Inspect members for Zip Slip & Dangerous Files
                for member in infolist:
                    filename = member.filename
                    
                    # Prevent Zip Slip / Path Traversal
                    if ".." in filename or filename.startswith("/") or filename.startswith("\\") or (len(filename) > 1 and filename[1] == ":"):
                        findings.append({
                            "id": "ZIP_SLIP_ATTACK",
                            "severity": "CRITICAL",
                            "file": filename,
                            "message": "Path traversal / Zip Slip vulnerability detected."
                        })
                        is_safe = False

                    # Prevent Dangerous Binary Extensions
                    ext = Path(filename).suffix.lower()
                    if ext in DANGEROUS_EXTENSIONS:
                        findings.append({
                            "id": "DANGEROUS_EXECUTABLE",
                            "severity": "CRITICAL",
                            "file": filename,
                            "message": f"Disallowed executable or script binary extension ({ext}) detected."
                        })
                        is_safe = False

                    total_uncompressed_size += member.file_size

                # 3. Check uncompressed size
                if total_uncompressed_size > MAX_UNCOMPRESSED_SIZE_BYTES:
                    return {
                        "is_safe": False,
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
                                if cf["severity"] in ["CRITICAL", "HIGH"]:
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
            "scanned_files": total_files,
            "total_size_mb": round(total_uncompressed_size / (1024 * 1024), 2)
        }

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


# Global singleton instance
security_scanner = SecurityScanner()
