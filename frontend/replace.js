const fs = require('fs');
const path = require('path');

function replaceInDir(dir) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    if (fs.statSync(fullPath).isDirectory()) {
      replaceInDir(fullPath);
    } else if (fullPath.endsWith('.js') || fullPath.endsWith('.jsx')) {
      let content = fs.readFileSync(fullPath, 'utf8');
      
      let changed = false;
      const original = content;

      // Replace next/link
      content = content.replace(/import\s+Link\s+from\s+["']next\/link["'];?/g, 'import Link from "@/components/Link";');
      
      // Replace next/image
      content = content.replace(/import\s+Image\s+from\s+["']next\/image["'];?/g, 'import Image from "@/components/Image";');
      
      // Replace next/font/google
      content = content.replace(/import\s+\{\s*Inter\s*\}\s+from\s+["']next\/font\/google["'];?/g, '');
      
      // Replace next/dynamic
      content = content.replace(/import\s+dynamicImport\s+from\s+["']next\/dynamic["'];?/g, 'import { lazy as dynamicImport } from "react";');
      
      // Replace next/navigation hooks
      content = content.replace(/import\s+\{\s*([a-zA-Z0-9_,\s]+)\s*\}\s+from\s+["']next\/navigation["'];?/g, 
        'const usePathname = () => window.location.pathname;\nconst useRouter = () => ({ push: (p) => window.location.href = p });\nconst useSearchParams = () => new URLSearchParams(window.location.search);');
      
      // Remove Inter instantiation
      content = content.replace(/const inter = Inter\(\{[^}]*\}\);?/g, '');
      content = content.replace(/inter\.className/g, '"font-sans"');

      // Next.js metadata export
      content = content.replace(/export\s+const\s+metadata\s*=\s*\{[^}]+\};?/g, '');

      if (content !== original) {
        fs.writeFileSync(fullPath, content);
      }
    }
  }
}

replaceInDir('./src');
