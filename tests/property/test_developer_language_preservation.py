"""
Property-based test for developer language preservation.

This test verifies that ALL developer-facing content remains in English:
- Function names, variable names, class names
- Code comments and docstrings
- Log messages (CloudWatch logs)
- Documentation files (README, docstrings)
- Infrastructure configuration

This is CORRECT behavior that must be preserved after implementing the
Brazilian Portuguese language fix for user-facing messages.

**EXPECTED OUTCOME ON UNFIXED CODE**: Test PASSES
- All code identifiers are in English
- All comments and docstrings are in English
- All log messages are in English
- All documentation is in English

**Validates: Requirements 3.9, 3.10, 3.11**
"""

import pytest
import re
import ast
from pathlib import Path
from typing import List, Set, Dict, Any
from hypothesis import given, strategies as st, settings, HealthCheck


class TestDeveloperLanguagePreservation:
    """
    Preservation test for developer language (English).
    
    This test verifies that the language fix for user-facing messages does NOT
    change the language of developer-facing content. All code, comments, logs,
    and documentation must remain in English for maintainability.
    """
    
    # Common English programming terms that should be present
    ENGLISH_CODE_TERMS = {
        'def', 'class', 'import', 'from', 'return', 'if', 'else', 'for',
        'while', 'try', 'except', 'raise', 'with', 'as', 'lambda', 'yield',
        'async', 'await', 'assert', 'pass', 'break', 'continue', 'global',
        'nonlocal', 'del', 'and', 'or', 'not', 'in', 'is', 'None', 'True',
        'False', 'self', 'cls', 'args', 'kwargs', 'init', 'str', 'repr',
        'dict', 'list', 'tuple', 'set', 'int', 'float', 'bool', 'type'
    }
    
    # Portuguese words that should NOT appear in code/comments/logs
    # Using word boundaries to avoid false positives (e.g., "erro" in "error")
    PORTUGUESE_WORDS = {
        # Common Portuguese words (standalone words only)
        r'\baluno\b', r'\bestudante\b', r'\bsessão\b', r'\bsessao\b', 
        r'\bpagamento\b', r'\btreino\b', r'\btreinador\b', 
        r'\bcalendário\b', r'\bcalendario\b', r'\bnotificação\b', 
        r'\bnotificacao\b', r'\bbem-vindo\b', r'\bbemvindo\b', 
        r'\bobrigado\b', r'\bdesculpe\b', r'\bsucesso\b', r'\bfalha\b', 
        r'\bconfirmação\b', r'\bconfirmacao\b',
        # Portuguese function/variable naming patterns
        r'registrar_aluno', r'agendar_sessao', r'cancelar_sessao',
        r'visualizar_alunos', r'enviar_notificacao', r'conectar_calendario',
        # Portuguese log messages
        r'\bprocessando\b', r'\bexecutando\b', r'\bfinalizando\b', 
        r'\biniciando\b', r'\brecebido\b', r'\benviado\b', 
        r'\batualizado\b', r'\bcriado\b', r'\bdeletado\b',
        # Portuguese phrases
        r'por\s+favor', r'bem\s+vindo'
    }
    
    def test_python_files_use_english_identifiers(self):
        """
        Test that all Python files use English identifiers.
        
        Verifies:
        - Function names are in English
        - Variable names are in English
        - Class names are in English
        - No Portuguese words in identifiers
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.9**
        """
        # Get all Python files in src/
        src_dir = Path(__file__).parent.parent.parent / "src"
        python_files = list(src_dir.rglob("*.py"))
        
        assert len(python_files) > 0, "No Python files found in src/"
        
        portuguese_identifiers_found = []
        
        for py_file in python_files:
            # Parse the Python file
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content, filename=str(py_file))
                
                # Extract all identifiers
                identifiers = self._extract_identifiers(tree)
                
                # Check for Portuguese words in identifiers
                for identifier in identifiers:
                    identifier_lower = identifier.lower()
                    for pt_pattern in self.PORTUGUESE_WORDS:
                        if re.search(pt_pattern, identifier_lower):
                            portuguese_identifiers_found.append({
                                'file': str(py_file.relative_to(src_dir.parent)),
                                'identifier': identifier,
                                'portuguese_pattern': pt_pattern
                            })
            
            except SyntaxError:
                # Skip files with syntax errors (might be templates)
                continue
        
        # This should PASS on unfixed code - no Portuguese in identifiers
        assert len(portuguese_identifiers_found) == 0, (
            f"Found {len(portuguese_identifiers_found)} Portuguese identifiers in code!\n"
            f"Developer-facing code must remain in English.\n\n"
            f"Examples:\n" +
            "\n".join([
                f"  {item['file']}: {item['identifier']} (matches '{item['portuguese_pattern']}')"
                for item in portuguese_identifiers_found[:5]
            ])
        )
    
    def test_python_files_use_english_comments(self):
        """
        Test that all Python files use English comments and docstrings.
        
        Verifies:
        - Comments are in English
        - Docstrings are in English
        - No Portuguese words in comments/docstrings
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.9**
        """
        # Get all Python files in src/
        src_dir = Path(__file__).parent.parent.parent / "src"
        python_files = list(src_dir.rglob("*.py"))
        
        portuguese_comments_found = []
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract comments and docstrings
                comments = self._extract_comments_and_docstrings(content)
                
                # Check for Portuguese words
                for comment in comments:
                    comment_lower = comment.lower()
                    for pt_pattern in self.PORTUGUESE_WORDS:
                        if re.search(pt_pattern, comment_lower):
                            portuguese_comments_found.append({
                                'file': str(py_file.relative_to(src_dir.parent)),
                                'comment': comment[:100],  # First 100 chars
                                'portuguese_pattern': pt_pattern
                            })
            
            except Exception:
                continue
        
        # This should PASS on unfixed code - no Portuguese in comments
        assert len(portuguese_comments_found) == 0, (
            f"Found {len(portuguese_comments_found)} Portuguese comments/docstrings!\n"
            f"Developer-facing comments must remain in English.\n\n"
            f"Examples:\n" +
            "\n".join([
                f"  {item['file']}: '{item['comment']}...' (matches '{item['portuguese_pattern']}')"
                for item in portuguese_comments_found[:5]
            ])
        )
    
    def test_log_messages_use_english(self):
        """
        Test that all log messages use English.
        
        Verifies:
        - logger.info() messages are in English
        - logger.error() messages are in English
        - logger.warning() messages are in English
        - No Portuguese words in log messages
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.10**
        """
        # Get all Python files in src/
        src_dir = Path(__file__).parent.parent.parent / "src"
        python_files = list(src_dir.rglob("*.py"))
        
        portuguese_logs_found = []
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract log messages (logger.info, logger.error, etc.)
                log_messages = self._extract_log_messages(content)
                
                # Check for Portuguese words
                for log_msg in log_messages:
                    log_lower = log_msg.lower()
                    for pt_pattern in self.PORTUGUESE_WORDS:
                        if re.search(pt_pattern, log_lower):
                            portuguese_logs_found.append({
                                'file': str(py_file.relative_to(src_dir.parent)),
                                'log_message': log_msg[:100],
                                'portuguese_pattern': pt_pattern
                            })
            
            except Exception:
                continue
        
        # This should PASS on unfixed code - no Portuguese in logs
        assert len(portuguese_logs_found) == 0, (
            f"Found {len(portuguese_logs_found)} Portuguese log messages!\n"
            f"CloudWatch logs must remain in English for developer debugging.\n\n"
            f"Examples:\n" +
            "\n".join([
                f"  {item['file']}: '{item['log_message']}...' (matches '{item['portuguese_pattern']}')"
                for item in portuguese_logs_found[:5]
            ])
        )
    
    def test_documentation_uses_english(self):
        """
        Test that all documentation files use English.
        
        Verifies:
        - README.md is in English
        - Other .md files are in English
        - No Portuguese words in documentation
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.11**
        """
        # Get all markdown files in project root and docs/
        project_root = Path(__file__).parent.parent.parent
        md_files = [
            project_root / "README.md",
            project_root / "QUICKSTART.md",
            project_root / "LOCAL_TESTING_GUIDE.md",
            project_root / "TWILIO_SANDBOX_SETUP.md",
            project_root / "CI_CD_SETUP.md",
        ]
        
        # Filter to existing files
        md_files = [f for f in md_files if f.exists()]
        
        assert len(md_files) > 0, "No documentation files found"
        
        portuguese_docs_found = []
        
        for md_file in md_files:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for Portuguese words (excluding code blocks)
                content_no_code = self._remove_code_blocks(content)
                content_lower = content_no_code.lower()
                
                for pt_pattern in self.PORTUGUESE_WORDS:
                    if re.search(pt_pattern, content_lower):
                        # Find context around the word
                        match = re.search(pt_pattern, content_lower)
                        if match:
                            idx = match.start()
                            context = content[max(0, idx-50):min(len(content), idx+50)]
                            
                            portuguese_docs_found.append({
                                'file': str(md_file.relative_to(project_root)),
                                'context': context,
                                'portuguese_pattern': pt_pattern
                            })
            
            except Exception:
                continue
        
        # This should PASS on unfixed code - no Portuguese in docs
        assert len(portuguese_docs_found) == 0, (
            f"Found {len(portuguese_docs_found)} Portuguese words in documentation!\n"
            f"Documentation must remain in English for developers.\n\n"
            f"Examples:\n" +
            "\n".join([
                f"  {item['file']}: '...{item['context']}...' (matches '{item['portuguese_pattern']}')"
                for item in portuguese_docs_found[:5]
            ])
        )
    
    def test_infrastructure_config_uses_english(self):
        """
        Test that infrastructure configuration uses English.
        
        Verifies:
        - CloudFormation templates use English descriptions
        - Parameter names are in English
        - Resource names are in English
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.10**
        """
        # Get CloudFormation template
        project_root = Path(__file__).parent.parent.parent
        template_file = project_root / "infrastructure" / "template.yml"
        
        if not template_file.exists():
            pytest.skip("CloudFormation template not found")
        
        portuguese_config_found = []
        
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for Portuguese words
            content_lower = content.lower()
            
            for pt_pattern in self.PORTUGUESE_WORDS:
                if re.search(pt_pattern, content_lower):
                    # Find context
                    match = re.search(pt_pattern, content_lower)
                    if match:
                        idx = match.start()
                        context = content[max(0, idx-50):min(len(content), idx+50)]
                        
                        portuguese_config_found.append({
                            'file': 'infrastructure/template.yml',
                            'context': context,
                            'portuguese_pattern': pt_pattern
                        })
        
        except Exception:
            pass
        
        # This should PASS on unfixed code - no Portuguese in config
        assert len(portuguese_config_found) == 0, (
            f"Found {len(portuguese_config_found)} Portuguese words in infrastructure config!\n"
            f"Infrastructure configuration must remain in English.\n\n"
            f"Examples:\n" +
            "\n".join([
                f"  {item['file']}: '...{item['context']}...' (matches '{item['portuguese_pattern']}')"
                for item in portuguese_config_found[:3]
            ])
        )
    
    def test_english_terms_present_in_codebase(self):
        """
        Test that common English programming terms are present in codebase.
        
        This is a sanity check to ensure we're actually reading English code.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.9**
        """
        # Get all Python files in src/
        src_dir = Path(__file__).parent.parent.parent / "src"
        python_files = list(src_dir.rglob("*.py"))
        
        # Read all content
        all_content = ""
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    all_content += f.read() + "\n"
            except Exception:
                continue
        
        # Check for presence of English terms
        english_terms_found = set()
        for term in self.ENGLISH_CODE_TERMS:
            if term in all_content:
                english_terms_found.add(term)
        
        # Should find at least 50% of common English terms
        coverage = len(english_terms_found) / len(self.ENGLISH_CODE_TERMS)
        
        assert coverage >= 0.5, (
            f"Only found {len(english_terms_found)}/{len(self.ENGLISH_CODE_TERMS)} "
            f"common English programming terms.\n"
            f"This suggests the codebase might not be in English or test is broken."
        )
    
    # Helper methods
    
    def _extract_identifiers(self, tree: ast.AST) -> Set[str]:
        """Extract all identifiers (function names, variable names, class names) from AST."""
        identifiers = set()
        
        for node in ast.walk(tree):
            # Function definitions
            if isinstance(node, ast.FunctionDef):
                identifiers.add(node.name)
            
            # Class definitions
            elif isinstance(node, ast.ClassDef):
                identifiers.add(node.name)
            
            # Variable names
            elif isinstance(node, ast.Name):
                identifiers.add(node.id)
            
            # Attribute names
            elif isinstance(node, ast.Attribute):
                identifiers.add(node.attr)
        
        return identifiers
    
    def _extract_comments_and_docstrings(self, content: str) -> List[str]:
        """Extract all comments and docstrings from Python code."""
        comments = []
        
        # Extract single-line comments
        for line in content.split('\n'):
            if '#' in line:
                comment = line[line.index('#'):].strip()
                comments.append(comment)
        
        # Extract docstrings using regex
        docstring_pattern = r'"""(.*?)"""|\'\'\'(.*?)\'\'\''
        matches = re.findall(docstring_pattern, content, re.DOTALL)
        for match in matches:
            docstring = match[0] or match[1]
            comments.append(docstring.strip())
        
        return comments
    
    def _extract_log_messages(self, content: str) -> List[str]:
        """Extract log messages from Python code."""
        log_messages = []
        
        # Pattern to match logger calls: logger.info("message", ...)
        log_pattern = r'logger\.(info|error|warning|debug|critical)\s*\(\s*["\']([^"\']+)["\']'
        matches = re.findall(log_pattern, content)
        
        for match in matches:
            log_messages.append(match[1])  # match[1] is the message string
        
        return log_messages
    
    def _remove_code_blocks(self, markdown_content: str) -> str:
        """Remove code blocks from markdown content."""
        # Remove fenced code blocks (```...```)
        content = re.sub(r'```.*?```', '', markdown_content, flags=re.DOTALL)
        
        # Remove inline code (`...`)
        content = re.sub(r'`[^`]+`', '', content)
        
        return content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
