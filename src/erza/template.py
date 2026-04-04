from __future__ import annotations

from dataclasses import dataclass, field
import ast
import html
import re
from typing import Any

from erza.backend import BackendBridge


class TemplateError(RuntimeError):
    """Raised when an .erza template cannot be parsed or evaluated."""


TOKEN_RE = re.compile(r"<\?(=)?(.*?)\?>", re.DOTALL)
ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", re.DOTALL)
FOR_RE = re.compile(r"^for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(.+)$", re.DOTALL)


@dataclass(slots=True)
class Token:
    kind: str
    content: str


@dataclass(slots=True)
class Scope:
    backend: BackendBridge
    values: dict[str, Any] = field(default_factory=dict)
    parent: "Scope | None" = None

    def child(self) -> "Scope":
        return Scope(backend=self.backend, parent=self)

    def resolve(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.resolve(name)
        raise TemplateError(f"unknown template name: {name}")


@dataclass(slots=True)
class TextNode:
    text: str


@dataclass(slots=True)
class OutputNode:
    expression: str


@dataclass(slots=True)
class AssignNode:
    name: str
    expression: str


@dataclass(slots=True)
class EvalNode:
    expression: str


@dataclass(slots=True)
class ForNode:
    name: str
    expression: str
    body: list["TemplateNode"]


@dataclass(slots=True)
class IfNode:
    expression: str
    body: list["TemplateNode"]
    else_body: list["TemplateNode"]


TemplateNode = TextNode | OutputNode | AssignNode | EvalNode | ForNode | IfNode


def render_template(
    source: str,
    backend: BackendBridge | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    scope = Scope(backend=backend or BackendBridge.empty(), values=dict(context or {}))
    tokens = _tokenize(source)
    nodes, index, stop = _parse_block(tokens, 0, stop_words=set())
    if stop is not None:
        raise TemplateError(f"unexpected template control statement: {stop}")
    if index != len(tokens):
        raise TemplateError("template parser did not consume the full source")
    chunks: list[str] = []
    _render_nodes(nodes, scope, chunks)
    return "".join(chunks)


def _tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    cursor = 0
    for match in TOKEN_RE.finditer(source):
        if match.start() > cursor:
            tokens.append(Token(kind="text", content=source[cursor : match.start()]))
        if match.group(1) == "=":
            tokens.append(Token(kind="output", content=match.group(2).strip()))
        else:
            tokens.append(Token(kind="statement", content=match.group(2).strip()))
        cursor = match.end()
    if cursor < len(source):
        tokens.append(Token(kind="text", content=source[cursor:]))
    return tokens


def _parse_block(
    tokens: list[Token],
    index: int,
    stop_words: set[str],
) -> tuple[list[TemplateNode], int, str | None]:
    nodes: list[TemplateNode] = []

    while index < len(tokens):
        token = tokens[index]
        if token.kind == "text":
            nodes.append(TextNode(text=token.content))
            index += 1
            continue
        if token.kind == "output":
            nodes.append(OutputNode(expression=token.content))
            index += 1
            continue

        statement = token.content.strip()
        keyword = statement.split(maxsplit=1)[0] if statement else ""
        if keyword in stop_words:
            return nodes, index, keyword

        if statement.startswith("if "):
            body, next_index, stop = _parse_block(tokens, index + 1, {"else", "endif"})
            else_body: list[TemplateNode] = []
            if stop == "else":
                else_body, next_index, stop = _parse_block(tokens, next_index + 1, {"endif"})
            if stop != "endif":
                raise TemplateError("if block must end with <? endif ?>")
            nodes.append(
                IfNode(
                    expression=statement[3:].strip(),
                    body=body,
                    else_body=else_body,
                )
            )
            index = next_index + 1
            continue

        if statement.startswith("for "):
            match = FOR_RE.match(statement)
            if match is None:
                raise TemplateError(
                    "for blocks must use the form <? for item in collection ?>"
                )
            body, next_index, stop = _parse_block(tokens, index + 1, {"endfor"})
            if stop != "endfor":
                raise TemplateError("for block must end with <? endfor ?>")
            nodes.append(
                ForNode(
                    name=match.group(1),
                    expression=match.group(2).strip(),
                    body=body,
                )
            )
            index = next_index + 1
            continue

        assignment = ASSIGNMENT_RE.match(statement)
        if assignment is not None:
            nodes.append(
                AssignNode(
                    name=assignment.group(1),
                    expression=assignment.group(2).strip(),
                )
            )
            index += 1
            continue

        nodes.append(EvalNode(expression=statement))
        index += 1

    return nodes, index, None


def _render_nodes(nodes: list[TemplateNode], scope: Scope, chunks: list[str]) -> None:
    for node in nodes:
        if isinstance(node, TextNode):
            chunks.append(node.text)
            continue
        if isinstance(node, OutputNode):
            value = _evaluate_expression(node.expression, scope)
            chunks.append(html.escape(_stringify(value), quote=True))
            continue
        if isinstance(node, AssignNode):
            scope.values[node.name] = _evaluate_expression(node.expression, scope)
            continue
        if isinstance(node, EvalNode):
            _evaluate_expression(node.expression, scope)
            continue
        if isinstance(node, ForNode):
            collection = _evaluate_expression(node.expression, scope)
            if collection is None:
                continue
            for value in collection:
                child_scope = scope.child()
                child_scope.values[node.name] = value
                _render_nodes(node.body, child_scope, chunks)
            continue
        if isinstance(node, IfNode):
            condition = _evaluate_expression(node.expression, scope)
            body = node.body if condition else node.else_body
            _render_nodes(body, scope.child(), chunks)
            continue
        raise TemplateError(f"unsupported template node: {type(node).__name__}")


def _evaluate_expression(expression: str, scope: Scope) -> Any:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise TemplateError(f"invalid template expression: {expression}") from exc
    return _ExpressionEvaluator(scope).visit(tree.body)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _resolve_attribute(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        if name in value:
            return value[name]
        raise TemplateError(f"missing dict key {name!r} in template expression")
    try:
        return getattr(value, name)
    except AttributeError as exc:
        raise TemplateError(f"missing attribute {name!r} in template expression") from exc


class _ExpressionEvaluator(ast.NodeVisitor):
    def __init__(self, scope: Scope) -> None:
        self.scope = scope

    def generic_visit(self, node: ast.AST) -> Any:
        raise TemplateError(
            f"unsupported expression in .erza template: {type(node).__name__}"
        )

    def visit_Name(self, node: ast.Name) -> Any:
        return self.scope.resolve(node.id)

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        return _resolve_attribute(self.visit(node.value), node.attr)

    def visit_List(self, node: ast.List) -> Any:
        return [self.visit(item) for item in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> Any:
        return tuple(self.visit(item) for item in node.elts)

    def visit_Dict(self, node: ast.Dict) -> Any:
        return {
            self.visit(key): self.visit(value)
            for key, value in zip(node.keys, node.values, strict=True)
        }

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        value = self.visit(node.value)
        key = self.visit(node.slice)
        try:
            return value[key]
        except (KeyError, IndexError, TypeError) as exc:
            raise TemplateError("invalid subscript access in template expression") from exc

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        return self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        values = [self.visit(value) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        return self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        for operator, comparator in zip(node.ops, node.comparators, strict=True):
            right = self.visit(comparator)
            if isinstance(operator, ast.Eq):
                result = left == right
            elif isinstance(operator, ast.NotEq):
                result = left != right
            elif isinstance(operator, ast.Lt):
                result = left < right
            elif isinstance(operator, ast.LtE):
                result = left <= right
            elif isinstance(operator, ast.Gt):
                result = left > right
            elif isinstance(operator, ast.GtE):
                result = left >= right
            elif isinstance(operator, ast.In):
                result = left in right
            elif isinstance(operator, ast.NotIn):
                result = left not in right
            else:
                return self.generic_visit(node)
            if not result:
                return False
            left = right
        return True

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name) or node.func.id != "backend":
            raise TemplateError("only backend(...) calls are allowed in .erza templates")
        if not node.args:
            raise TemplateError("backend(...) requires a handler name")
        name = self.visit(node.args[0])
        if not isinstance(name, str):
            raise TemplateError("backend(...) handler name must evaluate to a string")
        kwargs = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                raise TemplateError("backend(...) does not support **kwargs in templates")
            kwargs[keyword.arg] = self.visit(keyword.value)
        return self.scope.backend.call(name, **kwargs)
