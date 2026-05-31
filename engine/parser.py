"""Parser for Playwright codegen output using Python AST."""

import ast
from pathlib import Path
from typing import List, Dict, Any
from core.security import sanitize_step
from core.exceptions import RecordingError
from core.logging import get_logger

logger = get_logger()

class PlaywrightASTVisitor(ast.NodeVisitor):
    def __init__(self, is_oracle: bool = False):
        self.steps = []
        self.seq = 1
        self.redacted_count = 0
        self.parsed_count = 0
        self.is_oracle = is_oracle

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            self._parse_call(node.value)
        self.generic_visit(node)
        
    def _parse_call(self, call_node):
        # We are looking for something like:
        # page.goto("url")
        # page.get_by_label("...").fill("...")
        # expect(page.locator("...")).to_be_visible()
        
        try:
            # 1. Handle expect(...).to_xxx(...)
            if isinstance(call_node.func, ast.Attribute) and isinstance(call_node.func.value, ast.Call):
                inner_call = call_node.func.value
                if isinstance(inner_call.func, ast.Name) and inner_call.func.id == "expect":
                    # expect(...)
                    assertion = call_node.func.attr # e.g. 'to_be_visible'
                    if assertion in ["to_be_visible", "to_have_text"]:
                        # extract locator string
                        locator_src = ast.unparse(inner_call.args[0])
                        action = "assert_visible" if assertion == "to_be_visible" else "assert_text"
                        val = ast.unparse(call_node.args[0]) if call_node.args else ""
                        self._add_step(action, locator_src, val)
                        return

            # 2. Handle page.xxx(...) or page.get_by_xxx(...).yyy(...)
            if isinstance(call_node.func, ast.Attribute):
                method_name = call_node.func.attr
                
                # if it's a direct page action: page.goto("url")
                if isinstance(call_node.func.value, ast.Name) and call_node.func.value.id == "page":
                    if method_name == "goto":
                        val = ast.unparse(call_node.args[0]).strip("'\"")
                        self._add_step("navigate", val, "")
                        return
                    if method_name in ["click", "fill", "check", "uncheck", "press", "select_option"]:
                        selector = ast.unparse(call_node.args[0]).strip("'\"")
                        val = ast.unparse(call_node.args[1]).strip("'\"") if len(call_node.args) > 1 else ""
                        if method_name == "select_option":
                            method_name = "select"
                        self._add_step(method_name, selector, val)
                        return
                        
                # if it's chained: page.get_by_label(...).fill(...) or deeper chains
                elif isinstance(call_node.func.value, ast.Call):
                    chained_call = call_node.func.value
                    if isinstance(chained_call.func, ast.Attribute):
                        locator_src = ast.unparse(chained_call)
                        if locator_src.startswith("page."):
                            if method_name in ["click", "fill", "check", "uncheck", "press", "select_option"]:
                                selector = locator_src
                                val = ast.unparse(call_node.args[0]).strip("'\"") if call_node.args else ""
                                if method_name == "select_option":
                                    method_name = "select"
                                self._add_step(method_name, selector, val)
                                return

        except Exception as e:
            # Safely ignore AST nodes we don't understand
            pass

    def _add_step(self, action: str, selector: str, value: str):
        self.parsed_count += 1
        
        # Auto-filter Oracle login steps from the beginning of recordings
        if self.is_oracle and self.parsed_count < 10:
            sel_lower = selector.lower()
            if action in ["click", "fill"] and any(t in sel_lower for t in ["username", "userid", "password", "sign in", "btnactive"]):
                logger.info(f"Auto-skipping Oracle login step: {action} on {selector}")
                return
                
        sanitized = sanitize_step(action, selector, value)
        if sanitized["is_sensitive"]:
            self.redacted_count += 1
            
        desc_action = action.replace("_", " ").title()
        desc_target = selector if len(selector) < 30 else "element"
        description = f"{desc_action} on {desc_target}"
        
        if action == "navigate":
            description = f"Navigate to {selector}"
            
        self.steps.append({
            "sequence": self.seq,
            "action": sanitized["action"],
            "selector": sanitized["selector"],
            "value": sanitized["value"],
            "is_sensitive": sanitized["is_sensitive"],
            "description": description
        })
        self.seq += 1

def parse_codegen_output(py_file: Path, is_oracle: bool = False) -> List[Dict[str, Any]]:
    """Parse Playwright codegen Python output into steps."""
    if not py_file.exists() or py_file.stat().st_size == 0:
        raise RecordingError("Output file is empty or missing")
        
    content = py_file.read_text(encoding='utf-8')
    
    try:
        tree = ast.parse(content)
        visitor = PlaywrightASTVisitor(is_oracle=is_oracle)
        visitor.visit(tree)
    except SyntaxError as e:
        raise RecordingError(f"Failed to parse Python output: {e}")
        
    if not visitor.steps:
        raise RecordingError("No actions found in recording")
        
    logger.info(f"Parsed {len(visitor.steps)} steps, redacted {visitor.redacted_count} sensitive fields")
    return visitor.steps
