"""
AI Code Debugger Service — Autonomous analysis, AST healing, and AI-driven syntax repair
for React JSX/TSX, Vue, Svelte, Astro, HTML, and full-stack source files.
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

    def sanitize_code_heuristics(self, code: str, ext: str = ".jsx", framework: str = "react") -> str:
        """
        Fast heuristic syntax repair before or in addition to LLM debugging.
        Cleans common AI generator defects without corrupting framework-specific structures.
        """
        if not code or not code.strip():
            return code

        ext_clean = ext.lower().strip()

        # Reject raw JSON status anomalies masquerading as code
        trimmed = code.strip()
        if ext_clean in [".jsx", ".tsx"] and (trimmed.startswith("{") and ("status" in trimmed or "diagnosis" in trimmed or "Dynamic structural" in trimmed)):
            from app.services.template_synthesizer import analyze_prompt_intent, synthesize_react_application
            profile = analyze_prompt_intent("Professional Website Template")
            return synthesize_react_application(profile)

        code = clean_code_response(code, ext_clean)

        # 1. HTML / HTM Files
        if ext_clean in [".html", ".htm"]:
            if "</html>" in code:
                parts = code.split("</html>")
                code = parts[0] + "</html>\n"
            return repair_truncated_html(code)

        # 2. Vue Single File Components (.vue)
        if ext_clean == ".vue":
            # Ensure closing tags for template, script, and style blocks
            for tag in ["template", "script", "style"]:
                open_cnt = len(re.findall(rf'<{tag}\b', code, re.IGNORECASE))
                close_cnt = len(re.findall(rf'</{tag}>', code, re.IGNORECASE))
                if open_cnt > close_cnt:
                    code = code.rstrip() + f"\n</{tag}>\n"
            return code

        # 3. Svelte Components (.svelte)
        if ext_clean == ".svelte":
            for tag in ["script", "style"]:
                open_cnt = len(re.findall(rf'<{tag}\b', code, re.IGNORECASE))
                close_cnt = len(re.findall(rf'</{tag}>', code, re.IGNORECASE))
                if open_cnt > close_cnt:
                    code = code.rstrip() + f"\n</{tag}>\n"
            return code

        # 4. React JSX / TSX Components (.jsx, .tsx)
        if ext_clean in [".jsx", ".tsx"]:
            code = re.sub(r'export\s+default\s+function\s*;', 'export default App;', code)
            code = re.sub(r'export\s+default\s*;', 'export default App;', code)

            # Fix premature `);` before HTML/JSX closing tags
            code = re.sub(r'\);\s*(</[A-Za-z0-9_.-]+>)', r'\1', code)
            code = re.sub(r';\s*(</[A-Za-z0-9_.-]+>)', r'\1', code)

            # Fix duplicate or missing export defaults safely
            has_inline_export = bool(re.search(r'export\s+default\s+(function|class)\b', code))
            if not has_inline_export:
                export_matches = list(re.finditer(r'export\s+default\s+([A-Za-z0-9_]+)\s*;?', code))
                valid_standalone = [m for m in export_matches if m.group(1) not in ("function", "class", "const")]
                if len(valid_standalone) > 1:
                    last_func = valid_standalone[-1].group(1)
                    code = re.sub(r'export\s+default\s+[A-Za-z0-9_]+\s*;?', '', code)
                    code = code.strip() + f"\n\nexport default {last_func};\n"
            else:
                code = re.sub(r'\nexport\s+default\s+[A-Za-z0-9_]+\s*;?\s*$', '', code).strip() + "\n"

            code = repair_truncated_jsx(code)
            return code

        # 5. Standard JS / TS files (main.js, router.js, configs)
        # Never inject React JSX or export defaults into standard scripts!
        return code

    async def debug_code_with_ai(
        self,
        code: str,
        filename: str,
        error_message: str = "",
        framework: str = "react",
    ) -> str:
        """
        Invokes Gemini AI Debugger model to analyze and fix compile/syntax errors
        tailored to the specific framework (Vue, Svelte, React, Astro, Next.js, HTML).
        """
        ext = os.path.splitext(filename)[1].lower() or ".js"
        is_config = any(c in os.path.basename(filename).lower() for c in ["config", "package.json", "tsconfig"])

        # Determine framework-tailored instructions
        if ext == ".vue" or framework == "vue":
            spec_inst = """VUE 3 SINGLE FILE COMPONENT INSTRUCTIONS:
- Preserve Vue 3 SFC structure (<template>, <script setup>, and <style scoped>).
- If <script setup> is used, do NOT add `export default`.
- Balance every HTML/Vue tag in <template>.
- Ensure all reactive state and composables (ref, reactive, computed, onMounted) are imported from 'vue'.
- Fix any unclosed brackets or syntax errors in <script>."""
        elif ext == ".svelte" or framework == "svelte":
            spec_inst = """SVELTE COMPONENT INSTRUCTIONS:
- Preserve Svelte component structure (<script>, HTML template, and <style>).
- Do NOT insert React imports or `export default`.
- Balance every HTML/Svelte tag and block ({#if}, {#each}).
- Fix any syntax errors in <script>."""
        elif is_config:
            spec_inst = """CONFIGURATION FILE INSTRUCTIONS:
- Preserve the configuration structure (e.g. export default defineConfig({ ... }) or module.exports).
- Do NOT wrap in React JSX, components, or HTML tags.
- Ensure correct plugin imports and valid JavaScript/TypeScript syntax."""
        elif ext in [".html", ".htm"]:
            spec_inst = """HTML5 DOCUMENT INSTRUCTIONS:
- Preserve valid HTML5 document structure (<!DOCTYPE html>, <html>, <head>, <body>).
- Ensure all open tags have matching closing tags in proper nesting order."""
        else:
            spec_inst = """REACT JSX / TSX INSTRUCTIONS:
- Balance every JSX/HTML tag properly in proper nesting order.
- Remove misplaced premature `);` or semicolons before closing JSX tags.
- Fix unmatched curly braces {}, parentheses (), or brackets [].
- Ensure all imported icons or components exist and are properly imported.
- Ensure the file has valid imports at the top and exactly ONE valid default export."""

        prompt = f"""You are an expert compiler engineer and senior full-stack debugging agent specializing in {framework.upper()}, Vue, Svelte, React, Vite, TypeScript, and modern web development.

A compilation/build error occurred on this source file.

==================================================
TARGET FILE: {filename}
FRAMEWORK: {framework}
COMPILER ERROR OUTPUT:
{error_message if error_message else "SyntaxError: Unexpected token or unbalanced tags / unclosed brackets / stray semicolons."}
==================================================

CURRENT SOURCE CODE WITH DEFECTS:
```
{code}
```

DEBUGGING & REPAIR INSTRUCTIONS:
1. Carefully inspect the exact line numbers and syntax errors reported.
2. {spec_inst}
3. CRITICAL: You must return the COMPLETE source code of the entire file from line 1 to the end. Do NOT omit or abbreviate any code with comments like "// rest of code".
4. Return ONLY the raw code inside standard ``` code blocks or plain text. Do NOT include conversational explanations.
"""

        try:
            logger.info(f"🤖 [AI Debugger] Sending {filename} ({len(code)} bytes) for {framework.upper()} automated repair...")
            response = await self.ai_service._generate_content(
                prompt=prompt,
                response_mime_type="text/plain",
                feature_name="code_debugging_agent"
            )
            repaired_code = clean_code_response(response, ext)

            # Check if LLM returned a valid full file (not an accidental stub)
            if repaired_code and (len(repaired_code) >= len(code) * 0.5 or len(repaired_code) > 400):
                return self.sanitize_code_heuristics(repaired_code, ext, framework)
            else:
                logger.warning(f"⚠️ [AI Debugger] LLM output was too short ({len(repaired_code or '')} chars vs {len(code)} original). Using heuristic repair.")
                return self.sanitize_code_heuristics(code, ext, framework)
        except Exception as e:
            logger.warning(f"⚠️ [AI Debugger] LLM debug request failed: {e}. Falling back to heuristic repair.")

        # Fallback to heuristic repair
        return self.sanitize_code_heuristics(code, ext, framework)

    def extract_failing_files_from_error(self, project_root: str, error_log: str, framework: str = "react") -> list[str]:
        """
        Parses Vite / esbuild / Next.js / TypeScript / Vue compiler error output
        to extract the absolute file paths of USER source files that caused the failure.
        CRITICAL: Never touches node_modules, build outputs, or vendor libraries!
        """
        failing_files = []
        lines = error_log.splitlines()
        abs_project_root = os.path.abspath(project_root)

        IGNORED_PARTS = {"node_modules", "dist", "build", "out", ".output", ".git", ".cache", ".next", ".nuxt", ".turbo"}
        
        # Regex patterns for common compiler error lines
        patterns = [
            r'file:\s*([^\s:]+\.(jsx|tsx|vue|svelte|astro|js|ts|html))(?::\d+:\d+)?',
            r'([^\s:]+\.(jsx|tsx|vue|svelte|astro|js|ts|html)):\d+:\d+:\s*(?:ERROR|error)',
            r'Error in\s+([^\s:]+\.(jsx|tsx|vue|svelte|astro|js|ts|html))',
            r'SyntaxError:\s*.*?\(([^\s:]+\.(jsx|tsx|vue|svelte|astro|js|ts|html))(?::\d+:\d+)?\)',
            r'([A-Za-z]:\\[^\s:]+\.(jsx|tsx|vue|svelte|astro|js|ts|html))',
            r'([A-Za-z0-9_./\\-]+\.(jsx|tsx|vue|svelte|astro|js|ts|html))',
        ]

        for line in lines:
            for pattern in patterns:
                matches = re.findall(pattern, line, re.IGNORECASE)
                for match in matches:
                    file_candidate = match[0] if isinstance(match, tuple) else match
                    file_candidate = file_candidate.strip().strip("'\"()[]")
                    norm_cand = file_candidate.replace("\\", "/").lower()

                    # STRICT GUARD: Never touch node_modules or build outputs!
                    if any(ig in norm_cand.split("/") for ig in IGNORED_PARTS) or "node_modules" in norm_cand:
                        continue
                    
                    # Resolve to candidate path
                    resolved_path = None
                    if os.path.isabs(file_candidate) and os.path.exists(file_candidate):
                        resolved_path = os.path.abspath(file_candidate)
                    else:
                        full_candidate = os.path.abspath(os.path.join(project_root, file_candidate))
                        if os.path.exists(full_candidate):
                            resolved_path = full_candidate
                        else:
                            # Search inside project_root for matching basename (skipping vendor dirs)
                            base_name = os.path.basename(file_candidate)
                            for root, dirs, files in os.walk(project_root):
                                dirs[:] = [d for d in dirs if d.lower() not in IGNORED_PARTS]
                                if base_name in files:
                                    resolved_path = os.path.abspath(os.path.join(root, base_name))
                                    break

                    if resolved_path and os.path.exists(resolved_path) and not os.path.isdir(resolved_path):
                        # Verify the resolved path is strictly inside project_root
                        try:
                            common = os.path.commonpath([abs_project_root, resolved_path])
                            if common == abs_project_root:
                                norm_res = resolved_path.replace("\\", "/").lower()
                                if not any(ig in norm_res.split("/") for ig in IGNORED_PARTS) and resolved_path not in failing_files:
                                    failing_files.append(resolved_path)
                        except ValueError:
                            pass

        # If no specific file matched from patterns, check common entry files for the framework
        if not failing_files:
            cands = []
            fw_lower = framework.lower()
            if fw_lower == "vue":
                cands = ["src/App.vue", "src/main.js", "src/main.ts", "App.vue", "vite.config.js", "index.html"]
            elif fw_lower == "svelte":
                cands = ["src/App.svelte", "src/main.js", "src/main.ts", "App.svelte", "vite.config.js", "index.html"]
            elif fw_lower == "astro":
                cands = ["src/pages/index.astro", "astro.config.mjs"]
            elif fw_lower in ["react", "nextjs"]:
                cands = ["src/App.jsx", "src/App.tsx", "src/main.jsx", "src/main.tsx", "src/index.js", "App.jsx", "pages/index.jsx", "app/page.jsx", "index.html"]
            else:
                cands = ["index.html", "src/main.js", "src/App.jsx", "App.jsx"]

            for rel_c in cands:
                cand = os.path.join(project_root, rel_c)
                if os.path.exists(cand) and cand not in failing_files:
                    failing_files.append(cand)
                    break

        return failing_files

    async def debug_project_build(
        self,
        project_root: str,
        build_cmd: list[str],
        initial_error_log: str,
        max_attempts: int = 3,
        framework: str = "react",
    ) -> Tuple[bool, str, Dict[str, str]]:
        """
        Autonomous Multi-Step AI Debugging Loop:
        1. Identifies failing files from error output (excluding vendor libraries).
        2. Applies AI code repair to each failing file tailored to framework.
        3. Re-runs build command.
        4. Repeats up to `max_attempts` until build succeeds or max iterations reached.
        Returns: (is_success, final_log, dict_of_repaired_files)
        """
        loop = asyncio.get_running_loop()
        current_error_log = initial_error_log
        repaired_files = {}

        for attempt in range(1, max_attempts + 1):
            logger.info(f"🛠️ [AI Debugger] Starting automated repair iteration {attempt}/{max_attempts} for {framework.upper()} project {project_root}...")

            # 0. Check for index.html entry script mismatch
            index_html_p = os.path.join(project_root, "index.html")
            if os.path.exists(index_html_p):
                try:
                    with open(index_html_p, "r", encoding="utf-8", errors="ignore") as f:
                        h_content = f.read()
                    
                    orig_h = h_content
                    # Ensure index.html doesn't have stray elements after </html>
                    if "</html>" in h_content:
                        h_content = h_content.split("</html>")[0] + "</html>\n"

                    # Match script tag to existing entry file in src/
                    src_p = os.path.join(project_root, "src")
                    if os.path.isdir(src_p):
                        src_files = os.listdir(src_p)
                        for entry_cand in ["main.js", "main.jsx", "main.ts", "main.tsx", "index.js", "index.jsx", "index.ts", "index.tsx"]:
                            if entry_cand in src_files:
                                for other_cand in ["main.js", "main.jsx", "main.ts", "main.tsx"]:
                                    if f"/src/{other_cand}" in h_content and other_cand != entry_cand and other_cand not in src_files:
                                        h_content = h_content.replace(f"/src/{other_cand}", f"/src/{entry_cand}")
                                        break
                                break

                    if h_content != orig_h:
                        with open(index_html_p, "w", encoding="utf-8") as f:
                            f.write(h_content)
                        repaired_files[os.path.relpath(index_html_p, project_root)] = h_content
                        logger.info(f"✅ [AI Debugger] Fixed entry script in index.html")
                except Exception as e_html:
                    logger.warning(f"AI Debugger index.html check skipped: {e_html}")

            failing_files = self.extract_failing_files_from_error(project_root, current_error_log, framework=framework)
            logger.info(f"🔍 [AI Debugger] Identified {len(failing_files)} potentially failing file(s): {failing_files}")

            for fpath in failing_files:
                try:
                    if not os.path.exists(fpath) or os.path.isdir(fpath):
                        continue

                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        original_code = f.read()

                    # 1. Run AI Debugger on the file with framework context
                    rel_name = os.path.relpath(fpath, project_root)
                    fixed_code = await self.debug_code_with_ai(
                        code=original_code,
                        filename=rel_name,
                        error_message=current_error_log,
                        framework=framework,
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
