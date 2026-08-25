const fs = require('fs');
const path = require('path');

const directory = path.join(__dirname, 'src', 'app');

function getAllFiles(dirPath, arrayOfFiles) {
  const files = fs.readdirSync(dirPath);

  arrayOfFiles = arrayOfFiles || [];

  files.forEach(function (file) {
    if (fs.statSync(dirPath + "/" + file).isDirectory()) {
      arrayOfFiles = getAllFiles(dirPath + "/" + file, arrayOfFiles);
    } else {
      arrayOfFiles.push(path.join(dirPath, "/", file));
    }
  });

  return arrayOfFiles;
}

const files = getAllFiles(directory);
const jsxFiles = files.filter(f => f.endsWith('.jsx'));
let modifiedCount = 0;

jsxFiles.forEach(file => {
  let content = fs.readFileSync(file, 'utf8');
  let originalContent = content;

  // Replace dark tailwind classes with light/neutral standard classes
  content = content.replace(/bg-slate-900\/10/g, 'bg-muted/30');
  content = content.replace(/bg-slate-900\/20/g, 'bg-muted/50');
  content = content.replace(/bg-slate-900/g, 'bg-card');
  content = content.replace(/bg-slate-800/g, 'bg-muted');
  content = content.replace(/text-slate-100/g, 'text-foreground');
  content = content.replace(/text-slate-200/g, 'text-foreground');
  content = content.replace(/text-slate-300/g, 'text-foreground');
  content = content.replace(/text-slate-400/g, 'text-muted-foreground');
  content = content.replace(/text-slate-500/g, 'text-muted-foreground');
  content = content.replace(/bg-\[\#020617\]/g, 'bg-background');
  content = content.replace(/border-white\/10/g, 'border-border/50');
  
  if (content !== originalContent) {
    fs.writeFileSync(file, content, 'utf8');
    modifiedCount++;
    console.log(`Modified: ${file}`);
  }
});

console.log(`Total files modified: ${modifiedCount}`);
