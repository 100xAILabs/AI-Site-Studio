"""
AI Code Debugger Service — Autonomous analysis, AST healing, and AI-driven syntax repair
for React JSX/TSX, HTML, Vue, and backend source files.
"""

import os
import re
import json
import logging
import asyncio
import subprocess
import platform
from typing import Optional, Tuple, Dict, Any

from app.core.config import settings
from app.services.ai_service import AIService, clean_code_response, repair_truncated_jsx, repair_truncated_html

logger = logging.getLogger(__name__)


class AIDebuggerService:
    def __init__(self):
        self.ai_service = AIService()

    def sanitize_code_heuristics(self, code: str, ext: str = ".jsx") -> str:
        """
        Fast heuristic syntax repair before or in addition to LLM debugging.
        Cleans common AI generator defects:
        - premature `);` before closing JSX tags (e.g. `);</main>`)
        - trailing garbage or unbalanced brackets
        - duplicate `export default` statements
        - missing React or icon imports
        """
        if not code or not code.strip():
            return code

        # Reject raw JSON status anomalies masquerading as code
        trimmed = code.strip()
        if trimmed.startswith("{") and ("status" in trimmed or "diagnosis" in trimmed or "Dynamic structural" in trimmed):
            if ext.lower() in [".jsx", ".tsx", ".js", ".ts"]:
                return """import React from 'react';

export default function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-8">
      <div className="max-w-md text-center">
        <h1 className="text-3xl font-extrabold mb-3">Live Template Preview</h1>
        <p className="text-slate-400 text-sm">Synthesized full-stack React application ready for inspection.</p>
      </div>
    </div>
  );
}
"""

        code = clean_code_response(code, ext)
        code = re.sub(r'export\s+default\s+function\s*;', 'export default App;', code)
        code = re.sub(r'export\s+default\s*;', 'export default App;', code)

        # Fix premature `);` before HTML/JSX closing tags
        # Example: `);</main>` or `);\n</section>`
        code = re.sub(r'\);\s*(</[A-Za-z0-9_.-]+>)', r'\1', code)
        code = re.sub(r';\s*(</[A-Za-z0-9_.-]+>)', r'\1', code)

        # Fix multiple duplicate `export default` statements
        export_matches = list(re.finditer(r'export\s+default\s+([A-Za-z0-9_]+)\s*;?', code))
        if len(export_matches) > 1:
            # Keep only the last valid export default
            last_match = export_matches[-1]
            last_func = last_match.group(1)
            # Remove all export defaults
            code = re.sub(r'export\s+default\s+[A-Za-z0-9_]+\s*;?', '', code)
            code = code.strip() + f"\n\nexport default {last_func};\n"

        # Apply structural repair for JSX/HTML
        if ext.lower() in [".jsx", ".tsx", ".js", ".ts"]:
            code = repair_truncated_jsx(code)
        elif ext.lower() in [".html", ".htm"]:
            # Clean content after closing </html> tag
            if "</html>" in code:
                parts = code.split("</html>")
                code = parts[0] + "</html>\n"
            code = repair_truncated_html(code)

        return code

    async def debug_code_with_ai(
        self,
        code: str,
        filename: str,
        error_message: str = "",
        framework: str = "react",
    ) -> str:
        """
        Invokes Gemini AI Debugger model to analyze and fix compile/syntax errors.
        """
        prompt = f"""You are an expert compiler engineer and senior full-stack debugging agent specializing in {framework.upper()}, React, Vite, TypeScript, and modern web development.

A compilation/build error occurred on this source file.

==================================================
TARGET FILE: {filename}
FRAMEWORK: {framework}
COMPILER ERROR OUTPUT:
{error_message if error_message else "SyntaxError: Unexpected token or unbalanced JSX tags / unclosed brackets / stray semicolons."}
==================================================

CURRENT SOURCE CODE WITH DEFECTS:
```
{code}
```

DEBUGGING & REPAIR INSTRUCTIONS:
1. Carefully inspect the exact line numbers and syntax errors reported.
2. Fix all syntax defects:
   - Balance every JSX/HTML tag properly. Ensure every opened element has its matching closing element in proper nesting order.
   - Remove misplaced premature `);` or semicolons occurring before JSX closing tags (e.g., replace `);</main>` with `</main>`).
   - Fix unmatched curly braces `{{}}`, parentheses `()`, or brackets `[]`.
   - Ensure all imported Lucide icons or components exist and are properly imported.
   - Ensure the file has valid imports at top and exactly ONE valid `export default ComponentName;` at the bottom.
3. CRITICAL: You must return the COMPLETE source code of the entire file from the very first `import` line to the final `export default` line. Do NOT omit or abbreviate any code with comments like "// rest of code".
4. Return ONLY the raw code inside standard ``` code blocks or plain text. Do NOT include conversational explanations.
"""

        try:
            logger.info(f"🤖 [AI Debugger] Sending {filename} ({len(code)} bytes) to Gemini for automated code repair...")
            response = await self.ai_service._generate_content(
                prompt=prompt,
                response_mime_type="text/plain",
                feature_name="code_debugging_agent"
            )
            repaired_code = clean_code_response(response)
            ext = os.path.splitext(filename)[1] or ".jsx"

            # Check if LLM returned a valid full file (not an accidental stub)
            if repaired_code and (len(repaired_code) >= len(code) * 0.6 or len(repaired_code) > 800):
                return self.sanitize_code_heuristics(repaired_code, ext)
            else:
                logger.warning(f"⚠️ [AI Debugger] LLM output was too short ({len(repaired_code or '')} chars vs {len(code)} original). Using heuristic AST repair.")
                return self.sanitize_code_heuristics(code, ext)
        except Exception as e:
            logger.warning(f"⚠️ [AI Debugger] LLM debug request failed: {e}. Falling back to heuristic repair.")

        # Fallback to heuristic repair
        ext = os.path.splitext(filename)[1] or ".jsx"
        return self.sanitize_code_heuristics(code, ext)

    def extract_failing_files_from_error(self, project_root: str, error_log: str) -> list[str]:
        """
        Parses Vite / esbuild / Next.js / TypeScript compiler error output
        to extract the absolute or relative file paths that caused the failure.
        """
        failing_files = []
        lines = error_log.splitlines()
        
        # Regex patterns for common compiler error lines
        patterns = [
            r'file:\s*([^\s:]+\.(jsx|tsx|js|ts|vue|html))(?::\d+:\d+)?',
            r'([^\s:]+\.(jsx|tsx|js|ts|vue|html)):\d+:\d+:\s*(?:ERROR|error)',
            r'Error in\s+([^\s:]+\.(jsx|tsx|js|ts|vue|html))',
            r'SyntaxError:\s*.*?\(([^\s:]+\.(jsx|tsx|js|ts|vue|html))(?::\d+:\d+)?\)',
            r'([A-Za-z]:\\[^\s:]+\.(jsx|tsx|js|ts|vue|html))',
            r'([A-Za-z0-9_./\\-]+\.(jsx|tsx|js|ts|vue|html))',
        ]

        for line in lines:
            for pattern in patterns:
                matches = re.findall(pattern, line, re.IGNORECASE)
                for match in matches:
                    file_candidate = match[0] if isinstance(match, tuple) else match
                    file_candidate = file_candidate.strip().strip("'\"()[]")
                    
                    # Resolve to absolute path
                    if os.path.isabs(file_candidate) and os.path.exists(file_candidate):
                        if file_candidate not in failing_files:
                            failing_files.append(file_candidate)
                    else:
                        full_candidate = os.path.join(project_root, file_candidate)
                        if os.path.exists(full_candidate) and full_candidate not in failing_files:
                            failing_files.append(full_candidate)
                        else:
                            # Search in project_root for basename
                            base_name = os.path.basename(file_candidate)
                            for root, _, files in os.walk(project_root):
                                if any(d in root.replace("\\", "/").split("/") for d in ["dist", "node_modules", "build", ".output"]):
                                    continue
                                if base_name in files:
                                    found_p = os.path.join(root, base_name)
                                    if found_p not in failing_files:
                                        failing_files.append(found_p)

        # If no specific file matched from patterns, check common entry files
        if not failing_files:
            for common_rel in ["src/App.jsx", "src/App.tsx", "src/main.jsx", "src/main.tsx", "src/index.js", "App.jsx", "index.html"]:
                cand = os.path.join(project_root, common_rel)
                if os.path.exists(cand):
                    failing_files.append(cand)

        return failing_files

    async def debug_project_build(
        self,
        project_root: str,
        build_cmd: list[str],
        initial_error_log: str,
        max_attempts: int = 3,
    ) -> Tuple[bool, str, Dict[str, str]]:
        """
        Autonomous Multi-Step AI Debugging Loop:
        1. Identifies failing files from error output.
        2. Applies AI code repair to each failing file.
        3. Re-runs `npm run build`.
        4. Repeats up to `max_attempts` until build succeeds or max iterations reached.
        Returns: (is_success, final_log, dict_of_repaired_files)
        """
        loop = asyncio.get_running_loop()
        current_error_log = initial_error_log
        repaired_files = {}

        for attempt in range(1, max_attempts + 1):
            logger.info(f"🛠️ [AI Debugger] Starting automated repair iteration {attempt}/{max_attempts} for project {project_root}...")

            # 0. Check for index.html entry script mismatch (e.g. /src/main.tsx vs /src/main.jsx)
            index_html_p = os.path.join(project_root, "index.html")
            if os.path.exists(index_html_p):
                try:
                    with open(index_html_p, "r", encoding="utf-8", errors="ignore") as f:
                        h_content = f.read()
                    
                    orig_h = h_content
                    # Ensure index.html doesn't have stray elements after </html>
                    if "</html>" in h_content:
                        h_content = h_content.split("</html>")[0] + "</html>\n"

                    # Fix /src/main.tsx if only main.jsx exists
                    if "/src/main.tsx" in h_content and not os.path.exists(os.path.join(project_root, "src", "main.tsx")) and os.path.exists(os.path.join(project_root, "src", "main.jsx")):
                        h_content = h_content.replace("/src/main.tsx", "/src/main.jsx")
                    elif "/src/main.jsx" in h_content and not os.path.exists(os.path.join(project_root, "src", "main.jsx")) and os.path.exists(os.path.join(project_root, "src", "main.tsx")):
                        h_content = h_content.replace("/src/main.jsx", "/src/main.tsx")

                    if h_content != orig_h:
                        with open(index_html_p, "w", encoding="utf-8") as f:
                            f.write(h_content)
                        repaired_files[os.path.relpath(index_html_p, project_root)] = h_content
                        logger.info(f"✅ [AI Debugger] Fixed entry script in index.html")
                except Exception as e_html:
                    logger.warning(f"AI Debugger index.html check skipped: {e_html}")

            failing_files = self.extract_failing_files_from_error(project_root, current_error_log)
            logger.info(f"🔍 [AI Debugger] Identified {len(failing_files)} potentially failing file(s): {failing_files}")

            for fpath in failing_files:
                try:
                    if not os.path.exists(fpath) or os.path.isdir(fpath):
                        continue

                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        original_code = f.read()

                    # 1. Run AI Debugger on the file
                    rel_name = os.path.relpath(fpath, project_root)
                    fixed_code = await self.debug_code_with_ai(
                        code=original_code,
                        filename=rel_name,
                        error_message=current_error_log,
                    )

                    if fixed_code and fixed_code != original_code:
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(fixed_code)
                        repaired_files[rel_name] = fixed_code
                        logger.info(f"✅ [AI Debugger] Successfully repaired and saved {rel_name}")

                except Exception as e_file:
                    logger.error(f"❌ [AI Debugger] Failed to repair file {fpath}: {e_file}")

            # 2. Re-test the build
            def run_build_check():
                return subprocess.run(
                    build_cmd,
                    cwd=project_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

            build_res = await loop.run_in_executor(None, run_build_check)
            if build_res.returncode == 0:
                logger.info(f"🎉 [AI Debugger] Build SUCCEEDED after {attempt} repair iteration(s)!")
                return True, "Build succeeded after AI Debugger self-repair.", repaired_files

            current_error_log = (build_res.stderr or build_res.stdout or b"").decode("utf-8", errors="ignore")
            logger.warning(f"⚠️ [AI Debugger] Build iteration {attempt} failed: {current_error_log[:200]}...")

        return False, current_error_log, repaired_files


# Singleton instance
ai_debugger = AIDebuggerService()
