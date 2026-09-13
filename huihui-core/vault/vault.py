#!/usr/bin/env python3
"""
Vault — OpenHuman-inspired local folder ingestion for Huihui

Core responsibilities:
1. Watch a local folder for document changes
2. Auto-detect and extract content from PDF, DOCX, MD, TXT, PY, JS, etc.
3. Feed through TokenJuice pipeline → Memory Tree
4. No external APIs required — pure local processing

Usage:
    python3 vault.py add /path/to/folder --name "work_docs"
    python3 vault.py ingest work_docs
    python3 vault.py list
    python3 vault.py remove work_docs
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, TypedDict

# ─── Configuration ────────────────────────────────────────────────────────────

CONFIG_DIR = Path(os.path.expanduser("~/.openclaw/workspace"))
VAULT_CONFIG = CONFIG_DIR / "vault_sources.json"
MEMORY_TREE_CLI = Path(__file__).parent.parent / "memory_tree" / "memory_tree.py"
TOKEN_JUICE_CLI = Path(__file__).parent.parent / "token_juice" / "token_juice.py"

# ─── Document Type Registry ───────────────────────────────────────────────────

EXTRACTORS = {}

def extractor(extensions: list[str]):
    """Decorator to register a file extractor for given extensions"""
    def decorator(func):
        for ext in extensions:
            EXTRACTORS[ext] = func
        return func
    return decorator

@extractor(['.txt', '.md', '.markdown', '.py', '.js', '.ts', '.json', '.yaml', '.yml', '.toml', '.sh', '.bash', '.zsh', '.csv', '.log'])
def extract_text(filepath: Path) -> str:
    """Plain text / code files"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

@extractor(['.docx'])
def extract_docx(filepath: Path) -> str:
    """Microsoft Word DOCX"""
    try:
        from docx import Document
        doc = Document(str(filepath))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return '\n\n'.join(paragraphs)
    except ImportError:
        raise RuntimeError("python-docx required: pip install python-docx")

@extractor(['.pdf'])
def extract_pdf(filepath: Path) -> str:
    """PDF files — requires PyPDF2 or pdfplumber"""
    text_parts = []
    
    try:
        import PyPDF2
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return '\n\n'.join(text_parts)
    except ImportError:
        pass
    
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return '\n\n'.join(text_parts)
    except ImportError:
        raise RuntimeError("PyPDF2 or pdfplumber required: pip install PyPDF2 pdfplumber")

# ─── Vault Source Registry ───────────────────────────────────────────────────

class VaultConfig:
    def __init__(self):
        self.config_file = VAULT_CONFIG
        self.data = self._load()
    
    def _load(self) -> dict:
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text())
            except:
                pass
        return {"sources": {}}
    
    def save(self):
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))
    
    def add_source(self, name: str, path: str, extensions: Optional[list[str]] = None) -> dict:
        """Register a new vault source folder"""
        if extensions is None:
            extensions = list(EXTRACTORS.keys())
        
        source_path = Path(os.path.expanduser(path))
        if not source_path.exists():
            raise FileNotFoundError(f"Folder not found: {source_path}")
        
        self.data["sources"][name] = {
            "path": str(source_path),
            "extensions": extensions,
            "last_ingest": None,
            "file_index": {},  # filename → mtime/md5 to detect changes
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.save()
        return self.data["sources"][name]
    
    def remove_source(self, name: str):
        if name in self.data["sources"]:
            del self.data["sources"][name]
            self.save()
    
    def get_source(self, name: str) -> Optional[dict]:
        return self.data.get("sources", {}).get(name)
    
    def list_sources(self) -> dict:
        return self.data.get("sources", {})
    
    def update_last_ingest(self, name: str):
        if name in self.data["sources"]:
            self.data["sources"][name]["last_ingest"] = datetime.now(timezone.utc).isoformat()
            self.save()

# ─── Core Ingestion ───────────────────────────────────────────────────────────

def extract_content(filepath: Path) -> str:
    """Extract text content based on file extension"""
    ext = filepath.suffix.lower()
    
    if ext not in EXTRACTORS:
        raise ValueError(f"No extractor for {ext} (supported: {', '.join(EXTRACTORS.keys())})")
    
    return EXTRACTORS[ext](filepath)

def ingest_folder(name: str, verbose: bool = True) -> dict:
    """
    Ingest all changed/new files from a vault source into memory tree.
    Returns summary of what was ingested.
    """
    vault = VaultConfig()
    source = vault.get_source(name)
    
    if not source:
        raise ValueError(f"Vault source '{name}' not found. Add it first with: vault.py add <name> <path>")
    
    source_path = Path(source["path"])
    allowed_exts = set(source["extensions"])
    file_index = source.get("file_index", {})
    
    stats = {
        "scanned": 0,
        "new": 0,
        "changed": 0,
        "unchanged": 0,
        "errors": 0,
        "total_chars": 0
    }
    
    for filepath in source_path.rglob('*'):
        if not filepath.is_file():
            continue
        
        ext = filepath.suffix.lower()
        if ext not in allowed_exts:
            continue
        
        stats["scanned"] += 1
        
        try:
            # Check if file is new or changed
            mtime = filepath.stat().st_mtime
            file_key = str(filepath.relative_to(source_path))
            file_hash = hashlib.md5(filepath.read_bytes()[:8192]).hexdigest()  # quick hash
            
            prev = file_index.get(file_key, {})
            
            if file_key not in file_index:
                # New file
                stats["new"] += 1
                is_new_or_changed = True
            elif prev.get("mtime") != mtime or prev.get("hash") != file_hash:
                # Changed file
                stats["changed"] += 1
                is_new_or_changed = True
            else:
                # Unchanged
                stats["unchanged"] += 1
                is_new_or_changed = False
            
            if is_new_or_changed:
                if verbose:
                    marker = "🆕" if stats["new"] > 0 and file_key not in prev else "🔄"
                    print(f"  {marker} {filepath.name}")
                
                # Extract content
                content = extract_content(filepath)
                stats["total_chars"] += len(content)
                
                # Compress with TokenJuice
                try:
                    import subprocess
                    result = subprocess.run(
                        ['python3', str(TOKEN_JUICE_CLI), '--input', '-', '--chunks'],
                        input=content,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode == 0:
                        content = result.stdout.strip()
                except Exception as e:
                    if verbose:
                        print(f"    ⚠️ TokenJuice failed: {e}")
                
                # Feed to memory tree
                try:
                    import subprocess
                    topic = f"vault:{name}"
                    
                    # Add as chunks
                    chunks = content.split('\n\n---\n\n') if '\n\n---\n\n' in content else [content]
                    for i, chunk in enumerate(chunks[:10]):  # max 10 chunks per file
                        subprocess.run(
                            ['python3', str(MEMORY_TREE_CLI), 'add',
                             '--content', f"## {filepath.name}\n\n{chunk[:2000]}",
                             '--topic', topic,
                             '--chunk', str(i)],
                            capture_output=True,
                            timeout=10
                        )
                except Exception as e:
                    if verbose:
                        print(f"    ⚠️ Memory tree failed: {e}")
                
                # Update index
                file_index[file_key] = {
                    "mtime": mtime,
                    "hash": file_hash,
                    "size": len(content),
                    "ingested": datetime.now(timezone.utc).isoformat()
                }
        
        except Exception as e:
            stats["errors"] += 1
            if verbose:
                print(f"  ❌ {filepath.name}: {e}")
    
    # Save updated index
    vault.data["sources"][name]["file_index"] = file_index
    vault.update_last_ingest(name)
    
    return stats

# ─── CLI Interface ────────────────────────────────────────────────────────────

def cmd_add(args):
    vault = VaultConfig()
    
    # Validate path
    path = Path(os.path.expanduser(args.path))
    if not path.exists():
        print(f"Error: Path not found: {path}")
        return
    
    if not path.is_dir():
        print(f"Error: Not a directory: {path}")
        return
    
    # Auto-detect supported file types
    supported_exts = set(EXTRACTORS.keys())
    found_exts = set(p.suffix.lower() for p in path.rglob('*') if p.is_file() and p.suffix.lower() in supported_exts)
    
    source = vault.add_source(args.name, args.path, args.extensions or sorted(found_exts))
    print(f"Added vault source: {args.name}")
    print(f"  Path: {source['path']}")
    print(f"  Extensions: {', '.join(sorted(source['extensions']))}")
    print(f"  Existing files: {len(found_exts)} types found")

def cmd_remove(args):
    vault = VaultConfig()
    if vault.get_source(args.name):
        vault.remove_source(args.name)
        print(f"Removed vault source: {args.name}")
    else:
        print(f"Vault source not found: {args.name}")

def cmd_list(args):
    vault = VaultConfig()
    sources = vault.list_sources()
    
    if not sources:
        print("No vault sources configured.")
        print("Add one: vault.py add <name> <folder_path>")
        return
    
    print(f"=== Vault Sources ({len(sources)}) ===\n")
    for name, info in sources.items():
        print(f"{name}:")
        print(f"  Path: {info['path']}")
        print(f"  Extensions: {', '.join(sorted(info['extensions']))}")
        print(f"  Last ingest: {info.get('last_ingest', 'never')}")
        indexed = len(info.get('file_index', {}))
        print(f"  Files indexed: {indexed}")
        print()

def cmd_ingest(args):
    vault = VaultConfig()
    
    if args.name:
        # Ingest specific source
        stats = ingest_folder(args.name, verbose=True)
        print(f"\n📊 Ingest complete for '{args.name}':")
        print(f"  Scanned: {stats['scanned']} files")
        print(f"  New: {stats['new']} | Changed: {stats['changed']} | Unchanged: {stats['unchanged']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  Total chars processed: {stats['total_chars']:,}")
    else:
        # Ingest all sources
        sources = vault.list_sources()
        if not sources:
            print("No vault sources configured.")
            return
        
        for name in sources:
            print(f"\n{'='*40}")
            print(f"🍽️  Ingesting: {name}")
            print('='*40)
            stats = ingest_folder(name, verbose=True)
            print(f"\n  Scanned: {stats['scanned']} | New: {stats['new']} | Changed: {stats['changed']} | Errors: {stats['errors']}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Vault — Local folder ingestion for Huihui')
    subparsers = parser.add_subparsers(dest='command')
    
    add_parser = subparsers.add_parser('add', help='Add a vault source folder')
    add_parser.add_argument('name', help='Name for this source (e.g., work_docs)')
    add_parser.add_argument('path', help='Folder path to monitor')
    add_parser.add_argument('--extensions', nargs='+', help='File extensions to track (default: all supported)')
    
    subparsers.add_parser('list', help='List all vault sources')
    
    remove_parser = subparsers.add_parser('remove', help='Remove a vault source')
    remove_parser.add_argument('name', help='Name of source to remove')
    
    ingest_parser = subparsers.add_parser('ingest', help='Ingest files into memory tree')
    ingest_parser.add_argument('name', nargs='?', help='Source name (default: all sources)')
    
    args = parser.parse_args()
    
    if args.command == 'add':
        cmd_add(args)
    elif args.command == 'remove':
        cmd_remove(args)
    elif args.command == 'list':
        cmd_list(args)
    elif args.command == 'ingest':
        cmd_ingest(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
