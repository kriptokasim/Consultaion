import os
import re
import ast
import json
from pathlib import Path
import networkx as nx
import networkx.algorithms.community as nx_comm

# Constants & Configurations
REPO_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = REPO_ROOT / 'graphify-out'
AUDIT_DIR = REPO_ROOT / 'docs' / 'audits'

# Ensure output and audit directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

# Ignore patterns for files (similar to .graphifyignore but for code graph)
EXCLUDED_DIRS = {
    'node_modules', '.git', '.next', '.venv', 'dist', 'build', 'graphify-out', '.agents', '.gemini'
}

def is_excluded(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDED_DIRS:
            return True
    return False

class CodebaseParser:
    def __init__(self):
        self.py_files = []
        self.ts_files = []
        self.config_files = []
        
        # Symbol mappings
        self.py_modules = {}        # module_name -> filepath
        self.py_symbols = {}        # symbol_fq -> {'type': class/function/variable, 'file': filepath}
        self.py_module_symbols = {} # module_name -> list of symbol names defined in it
        
        self.ts_modules = {}        # module_name -> filepath
        self.ts_exports = {}        # symbol_fq -> {'type': class/function/variable, 'file': filepath}
        self.ts_module_exports = {} # module_name -> list of exported symbol names
        
        # Parsed info per file
        self.parsed_py = {}         # filepath -> {'definitions': [...], 'imports': [...], 'calls': [...]}
        self.parsed_ts = {}         # filepath -> {'definitions': [...], 'imports': [...], 'calls': [...]}
        
        # Ambiguities and unresolved imports
        self.ambiguous_resolutions = []
        self.unresolved_imports = []
        self.wildcard_imports = []
        
    def collect_files(self, include_config=False):
        self.py_files = []
        self.ts_files = []
        self.config_files = []
        
        for path in REPO_ROOT.rglob('*'):
            if path.is_dir() or is_excluded(path):
                continue
                
            suffix = path.suffix.lower()
            rel_path = path.relative_to(REPO_ROOT)
            
            # Code Files
            if suffix == '.py':
                self.py_files.append(rel_path)
            elif suffix in ('.ts', '.tsx', '.js', '.jsx'):
                self.ts_files.append(rel_path)
            
            # Config Files (Only if requested)
            if include_config:
                if (rel_path.match('.github/workflows/*.yml') or 
                    rel_path.match('.github/workflows/*.yaml') or
                    rel_path.match('docker-compose*.yml') or
                    rel_path.match('docker-compose*.yaml') or
                    rel_path.match('Dockerfile*') or
                    rel_path.name in ('package.json', 'pyproject.toml', 'alembic.ini', 'tsconfig.json') or
                    rel_path.name.startswith('requirements') and suffix == '.txt' or
                    rel_path.name.startswith('next.config.')):
                    self.config_files.append(rel_path)

    def parse_python_files(self):
        for rel_path in self.py_files:
            abs_path = REPO_ROOT / rel_path
            parts = list(rel_path.with_suffix('').parts)
            if parts[0] == 'apps' and parts[1] == 'api':
                module_fq = '.'.join(parts)
                module_short = '.'.join(parts[2:])
                self.py_modules[module_fq] = rel_path
                if module_short:
                    self.py_modules[module_short] = rel_path
            else:
                module_fq = '.'.join(parts)
                self.py_modules[module_fq] = rel_path
            
            try:
                content = abs_path.read_text(encoding='utf-8')
                tree = ast.parse(content, filename=str(abs_path))
            except Exception as e:
                print(f"Error parsing Python file {rel_path}: {e}")
                continue
                
            definitions = []
            module_name = '.'.join(parts)
            
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    fq_name = f"class:{module_name}.{node.name}"
                    self.py_symbols[fq_name] = {'type': 'class', 'file': rel_path}
                    definitions.append({'name': node.name, 'type': 'class', 'fq': fq_name})
                    for subnode in node.body:
                        if isinstance(subnode, ast.ClassDef) and subnode.name == 'Config':
                            sub_fq = f"class:{module_name}.{node.name}.Config"
                            self.py_symbols[sub_fq] = {'type': 'class', 'file': rel_path}
                            definitions.append({'name': f"{node.name}.Config", 'type': 'class', 'fq': sub_fq})
                            
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fq_name = f"function:{module_name}.{node.name}"
                    self.py_symbols[fq_name] = {'type': 'function', 'file': rel_path}
                    definitions.append({'name': node.name, 'type': 'function', 'fq': fq_name})
                    
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            fq_name = f"variable:{module_name}.{target.id}"
                            self.py_symbols[fq_name] = {'type': 'variable', 'file': rel_path}
                            definitions.append({'name': target.id, 'type': 'variable', 'fq': fq_name})
                elif isinstance(node, ast.AnnAssign):
                    if isinstance(node.target, ast.Name):
                        fq_name = f"variable:{module_name}.{node.target.id}"
                        self.py_symbols[fq_name] = {'type': 'variable', 'file': rel_path}
                        definitions.append({'name': node.target.id, 'type': 'variable', 'fq': fq_name})
            
            self.py_module_symbols[module_name] = [d['name'] for d in definitions]
            self.parsed_py[rel_path] = {
                'definitions': definitions,
                'imports': [],
                'calls': [],
                'tree': tree,
                'module_name': module_name
            }

        for rel_path in self.py_files:
            if rel_path not in self.parsed_py:
                continue
            data = self.parsed_py[rel_path]
            tree = data['tree']
            module_name = data['module_name']
            
            imports = []
            calls = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imports.append({
                            'type': 'module',
                            'name': name.name,
                            'alias': name.asname,
                            'node': node
                        })
                elif isinstance(node, ast.ImportFrom):
                    level = node.level
                    module = node.module or ''
                    
                    if level > 0:
                        module_parts = module_name.split('.')
                        resolved_parts = module_parts[:-level]
                        if module:
                            resolved_parts.extend(module.split('.'))
                        resolved_module = '.'.join(resolved_parts)
                    else:
                        resolved_module = module
                        
                    for name in node.names:
                        imports.append({
                            'type': 'symbol',
                            'module': resolved_module,
                            'name': name.name,
                            'alias': name.asname,
                            'node': node
                        })
                        
                elif isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name):
                        calls.append(func.id)
                    elif isinstance(func, ast.Attribute):
                        attrs = []
                        curr = func
                        while isinstance(curr, ast.Attribute):
                            attrs.append(curr.attr)
                            curr = curr.value
                        if isinstance(curr, ast.Name):
                            attrs.append(curr.id)
                        attrs.reverse()
                        calls.append('.'.join(attrs))
                        
            data['imports'] = imports
            data['calls'] = list(set(calls))

    def parse_typescript_files(self):
        import_pattern = re.compile(
            r"import\s+(?:type\s+)?(?:([\w*\s{},]*)\s+from\s+)?['\"]([^'\"]+)['\"]|import\s*\(?\s*['\"]([^'\"]+)['\"]\s*\)?"
        )
        export_pattern = re.compile(
            r"export\s+(?:default\s+)?(?:class|function|const|let|var|type|interface)\s+(\w+)|export\s+default\s+(\w+)"
        )
        
        for rel_path in self.ts_files:
            abs_path = REPO_ROOT / rel_path
            parts = list(rel_path.with_suffix('').parts)
            module_fq = '.'.join(parts)
            self.ts_modules[module_fq] = rel_path
            
            if parts[0] == 'apps' and parts[1] == 'web':
                short_parts = parts[2:]
                if short_parts:
                    alias_fq = '@/' + '/'.join(short_parts)
                    self.ts_modules[alias_fq] = rel_path
            
            try:
                content = abs_path.read_text(encoding='utf-8')
            except Exception as e:
                print(f"Error reading TS file {rel_path}: {e}")
                continue
                
            exports = []
            for match in export_pattern.finditer(content):
                name = match.group(1) or match.group(2)
                if name:
                    fq_name = f"symbol:{module_fq}.{name}"
                    self.ts_exports[fq_name] = {'type': 'export', 'file': rel_path}
                    exports.append({'name': name, 'fq': fq_name})
                    
            self.ts_module_exports[module_fq] = [e['name'] for e in exports]
            self.parsed_ts[rel_path] = {
                'exports': exports,
                'imports': [],
                'content': content,
                'module_name': module_fq
            }
            
        for rel_path in self.ts_files:
            if rel_path not in self.parsed_ts:
                continue
            data = self.parsed_ts[rel_path]
            content = data['content']
            imports = []
            
            for match in import_pattern.finditer(content):
                specifiers_str = match.group(1) or ""
                source = match.group(2) or match.group(3)
                
                resolved_source = source
                if source.startswith('.'):
                    parent_parts = list(rel_path.parent.parts)
                    source_parts = source.split('/')
                    for part in source_parts:
                        if part == '.':
                            continue
                        elif part == '..':
                            if parent_parts:
                                parent_parts.pop()
                        else:
                            parent_parts.append(part)
                    resolved_source = '.'.join(parent_parts)
                        
                specifiers = []
                if specifiers_str:
                    specifiers_str = specifiers_str.strip()
                    if specifiers_str.startswith('{') and specifiers_str.endswith('}'):
                        parts = specifiers_str[1:-1].split(',')
                        for p in parts:
                            p = p.strip().split(' as ')[0].strip()
                            if p:
                                specifiers.append(p)
                    elif '*' in specifiers_str:
                        specifiers.append('*')
                    else:
                        specifiers.append(specifiers_str)
                        
                imports.append({
                    'source': source,
                    'resolved_source': resolved_source,
                    'specifiers': specifiers
                })
                
            data['imports'] = imports

    def parse_config_files(self):
        configs_parsed = {}
        for rel_path in self.config_files:
            abs_path = REPO_ROOT / rel_path
            try:
                content = abs_path.read_text(encoding='utf-8')
            except Exception as e:
                print(f"Error reading config {rel_path}: {e}")
                continue
                
            referenced_modules = []
            for match in re.finditer(r"([\w_/-]+\.py)", content):
                py_script = match.group(1)
                referenced_modules.append(py_script)
                
            configs_parsed[rel_path] = {
                'referenced_modules': list(set(referenced_modules)),
                'content': content
            }
        return configs_parsed

    def resolve_graph(self, mode='code', correct_collision=True):
        G = nx.DiGraph()
        
        self.ambiguous_resolutions = []
        self.unresolved_imports = []
        self.wildcard_imports = []
        
        for file_path, data in self.parsed_py.items():
            mod_node = f"module:{data['module_name']}"
            G.add_node(mod_node, type='module', file=str(file_path))
            for def_info in data['definitions']:
                G.add_node(def_info['fq'], type=def_info['type'], file=str(file_path))
                G.add_edge(mod_node, def_info['fq'], relation='contains')
                
        for file_path, data in self.parsed_ts.items():
            mod_node = f"module:{data['module_name']}"
            G.add_node(mod_node, type='module', file=str(file_path))
            for exp_info in data['exports']:
                G.add_node(exp_info['fq'], type='export', file=str(file_path))
                G.add_edge(mod_node, exp_info['fq'], relation='contains')

        configs_parsed = {}
        if mode == 'architecture':
            configs_parsed = self.parse_config_files()
            for file_path in self.config_files:
                config_node = f"config:{file_path}"
                G.add_node(config_node, type='config', file=str(file_path))

        for file_path, data in self.parsed_py.items():
            mod_node = f"module:{data['module_name']}"
            
            for imp in data['imports']:
                if imp['type'] == 'module':
                    target_module = imp['name']
                    resolved_file = self.py_modules.get(target_module)
                    
                    if resolved_file:
                        target_node = f"module:{target_module}"
                        G.add_edge(mod_node, target_node, relation='imports')
                    else:
                        ext_node = f"external:{target_module}"
                        G.add_node(ext_node, type='external')
                        G.add_edge(mod_node, ext_node, relation='imports_external')
                        self.unresolved_imports.append({
                            'file': str(file_path),
                            'import': target_module
                        })
                        
                elif imp['type'] == 'symbol':
                    source_module = imp['module']
                    symbol_name = imp['name']
                    
                    if symbol_name == '*':
                        self.wildcard_imports.append({
                            'file': str(file_path),
                            'module': source_module
                        })
                    
                    is_collision_case = (source_module == 'config' and symbol_name == 'settings') or (source_module == 'alembic.config' and symbol_name == 'Config')
                    
                    if not correct_collision and is_collision_case:
                        collision_target = "class:apps.api.scripts.dev_db.Config"
                        if collision_target not in G:
                            G.add_node(collision_target, type='class', file='apps/api/scripts/dev_db.py')
                        G.add_edge(mod_node, collision_target, relation='imports_collided')
                        continue
                    
                    resolved_file = self.py_modules.get(source_module)
                    if resolved_file:
                        possible_kinds = ['class', 'function', 'variable']
                        resolved_symbol = None
                        matches = []
                        
                        for kind in possible_kinds:
                            fq_symbol = f"{kind}:{source_module}.{symbol_name}"
                            alt_fq_symbol = fq_symbol
                            parts = source_module.split('.')
                            if parts[0] != 'apps':
                                fq_mod = 'apps.api.' + source_module
                                alt_fq_symbol = f"{kind}:{fq_mod}.{symbol_name}"
                                
                            if fq_symbol in self.py_symbols:
                                matches.append(fq_symbol)
                            elif alt_fq_symbol in self.py_symbols:
                                matches.append(alt_fq_symbol)
                                
                        if len(matches) > 1:
                            self.ambiguous_resolutions.append({
                                'file': str(file_path),
                                'import': f"from {source_module} import {symbol_name}",
                                'matches': matches
                            })
                            resolved_symbol = matches[0]
                        elif len(matches) == 1:
                            resolved_symbol = matches[0]
                            
                        if resolved_symbol:
                            G.add_edge(mod_node, resolved_symbol, relation='imports')
                        else:
                            target_mod_node = f"module:{source_module}"
                            G.add_edge(mod_node, target_mod_node, relation='imports')
                    else:
                        ext_node = f"external:{source_module}.{symbol_name}"
                        G.add_node(ext_node, type='external')
                        G.add_edge(mod_node, ext_node, relation='imports_external')
                        self.unresolved_imports.append({
                            'file': str(file_path),
                            'import': f"from {source_module} import {symbol_name}"
                        })

        for file_path, data in self.parsed_ts.items():
            mod_node = f"module:{data['module_name']}"
            
            for imp in data['imports']:
                source = imp['source']
                resolved_source = imp['resolved_source']
                specifiers = imp['specifiers']
                
                resolved_file = self.ts_modules.get(resolved_source)
                if not resolved_file and resolved_source.startswith('@/'):
                    stripped = resolved_source[2:]
                    for key, val in self.ts_modules.items():
                        if key.endswith(stripped):
                            resolved_file = val
                            break
                            
                if resolved_file:
                    target_mod_node = f"module:{resolved_source}"
                    if target_mod_node not in G:
                        G.add_node(target_mod_node, type='module', file=str(resolved_file))
                    
                    if not specifiers or '*' in specifiers:
                        G.add_edge(mod_node, target_mod_node, relation='imports')
                    else:
                        for spec in specifiers:
                            fq_symbol = f"symbol:{resolved_source}.{spec}"
                            alt_fq = None
                            for k in self.ts_exports.keys():
                                if k.endswith(f".{spec}"):
                                    alt_fq = k
                                    break
                            
                            target_node = alt_fq or fq_symbol
                            if target_node not in G:
                                G.add_node(target_node, type='export', file=str(resolved_file))
                            G.add_edge(mod_node, target_node, relation='imports')
                else:
                    ext_node = f"external:{source}"
                    G.add_node(ext_node, type='external')
                    G.add_edge(mod_node, ext_node, relation='imports_external')
                    self.unresolved_imports.append({
                        'file': str(file_path),
                        'import': f"import from {source}"
                    })

        if mode == 'architecture':
            for file_path, cdata in configs_parsed.items():
                config_node = f"config:{file_path}"
                for ref_mod in cdata['referenced_modules']:
                    parts = list(Path(ref_mod).with_suffix('').parts)
                    mod_fq = '.'.join(parts)
                    
                    matching_node = None
                    for node in G.nodes:
                        if node.startswith('module:') and node.endswith(mod_fq):
                            matching_node = node
                            break
                            
                    if matching_node:
                        G.add_edge(config_node, matching_node, relation='references_code')

        return G

if __name__ == "__main__":
    print("CodebaseParser library loaded.")

