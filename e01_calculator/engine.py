"""E01 Local Calculator — exact-arithmetic expression engine.

Zero-side-effect kernel (provisional D0.2 definition; see
docs/PROVISIONAL_ASSUMPTIONS.md): evaluation performs no file, network,
environment, clock, randomness, or host-process effects. The public entry
point is the pure function :func:`evaluate`.

Arithmetic model:
- All rational-closed operations (+ - * / ^ with integer exponents, unary
  minus, parentheses, abs, floor, ceil) are computed exactly over
  ``fractions.Fraction``.
- Non-rational functions (sqrt on non-perfect squares, sin, cos, tan, ln,
  log10, exp, pi, e) are computed with ``decimal.Decimal`` at an explicit
  working precision (default 50 significant digits, configurable per call)
  and results carry ``exact: false`` plus the precision used.

Grammar (EBNF, canonical form; see docs/GRAMMAR.ebnf):
    expr    = term { ("+" | "-") term } ;
    term    = factor { ("*" | "/" | implicit) factor } ;
    factor  = unary { "^" unary } ;            (* right associative *)
    unary   = [ "-" | "+" ] primary ;
    primary = NUMBER | CONST | func "(" expr ")" | "(" expr ")" ;
    func    = "sqrt"|"abs"|"floor"|"ceil"|"sin"|"cos"|"tan"|"ln"|"log10"|"exp" ;
    NUMBER  = digits [ "." digits ] [ ("e"|"E") [sign] digits ] ;
    CONST   = "pi" | "e" ;
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import (Decimal, Context, DecimalException, DivisionByZero, InvalidOperation,
                     Overflow, Underflow, ROUND_HALF_EVEN, getcontext, localcontext)
from fractions import Fraction
from typing import Iterator, Optional, Union


class CalcError(Exception):
    """Base class for all engine errors. Carries a stable error code."""

    code = "E_CALC"


class LexError(CalcError):
    code = "E_LEX"


class ParseError(CalcError):
    code = "E_PARSE"


class DomainError(CalcError):
    code = "E_DOMAIN"


class LimitError(CalcError):
    code = "E_LIMIT"


# ------------------------------- limits (provisional, D0.4/P4) ----------
MAX_EXPRESSION_LENGTH = 4096          # characters
MAX_TOKENS = 1024
MAX_DEPTH = 64                        # parser recursion depth
MAX_EXPONENT = 4096                   # |integer exponent| bound
MAX_NUMBER_DIGITS = 400               # literal digits bound
DEFAULT_PRECISION = 50                # significant digits for inexact ops
MAX_INTEGER_BITS = 8192
MAX_AST_DEPTH = 200
MAX_DECIMAL_EXPONENT = 10000
MAX_TRIG_MAGNITUDE = 100


def _context():
    return Context(prec=DEFAULT_PRECISION, rounding=ROUND_HALF_EVEN,
                   Emin=-MAX_DECIMAL_EXPONENT, Emax=MAX_DECIMAL_EXPONENT,
                   capitals=1, clamp=0, flags=[],
                   traps=[InvalidOperation, DivisionByZero, Overflow, Underflow])


def _bounded(value):
    if isinstance(value, Fraction):
        if max(value.numerator.bit_length(), value.denominator.bit_length()) > MAX_INTEGER_BITS:
            raise LimitError("exact numerator or denominator exceeds the bit budget")
    elif not value.is_finite():
        raise DomainError("nonfinite numeric result")
    elif value and abs(value.adjusted()) > MAX_DECIMAL_EXPONENT:
        raise LimitError("decimal magnitude exceeds the exponent budget")
    return value

_TOKEN_RE = re.compile(
    r"""\s*(?:
        (?P<num>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)
      | (?P<name>[A-Za-z_][A-Za-z_0-9]*)
      | (?P<op>\*\*|[-+*/^()])
    )""",
    re.VERBOSE,
)

_FUNCS_EXACT = {"abs", "floor", "ceil"}
_FUNCS_INEXACT = {"sqrt", "sin", "cos", "tan", "ln", "log10", "exp"}
_CONSTS = {"pi", "e"}


@dataclass(frozen=True)
class Token:
    kind: str        # "num" | "name" | "op" | "end"
    text: str
    pos: int


def tokenize(source: str) -> list[Token]:
    if not isinstance(source, str):
        raise ParseError("expression must be a string")
    if len(source) > MAX_EXPRESSION_LENGTH:
        raise LimitError(f"expression exceeds {MAX_EXPRESSION_LENGTH} characters")
    tokens: list[Token] = []
    pos = 0
    while pos < len(source):
        m = _TOKEN_RE.match(source, pos)
        if not m or m.end() == m.start():
            stripped = source[pos:].lstrip()
            if not stripped:
                break
            raise LexError(f"unexpected character {stripped[0]!r} at position {pos}")
        if m.lastgroup is None and not source[pos:m.end()].strip():
            pos = m.end()
            continue
        kind = m.lastgroup
        text = m.group(kind) if kind else ""
        if kind == "num":
            if len(text.replace(".", "").replace("e", "").replace("E", "")) > MAX_NUMBER_DIGITS:
                raise LimitError(f"numeric literal exceeds {MAX_NUMBER_DIGITS} digits")
            # A017-F4: a scientific exponent scales the exact value's digit
            # count regardless of literal length; bound it to the same limit.
            em = re.search(r"[eE]([+-]?\d+)$", text)
            if em is not None and abs(int(em.group(1))) > MAX_NUMBER_DIGITS:
                raise LimitError(
                    f"|scientific exponent| exceeds {MAX_NUMBER_DIGITS} "
                    "(literal magnitude bound)")
        if kind == "op" and text == "**":
            text = "^"
        tokens.append(Token(kind, text, m.start()))
        if len(tokens) > MAX_TOKENS:
            raise LimitError(f"expression exceeds {MAX_TOKENS} tokens")
        pos = m.end()
    tokens.append(Token("end", "", len(source)))
    return tokens


# ------------------------------- AST ------------------------------------
@dataclass(frozen=True)
class Num:
    value: Fraction


@dataclass(frozen=True)
class Const:
    name: str


@dataclass(frozen=True)
class Unary:
    op: str
    operand: "Node"


@dataclass(frozen=True)
class Binary:
    op: str
    left: "Node"
    right: "Node"


@dataclass(frozen=True)
class Call:
    func: str
    arg: "Node"


Node = Union[Num, Const, Unary, Binary, Call]


class Parser:
    """Recursive-descent parser implementing the canonical EBNF grammar."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0
        self.depth = 0

    def peek(self) -> Token:
        return self.tokens[self.i]

    def take(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def expect_op(self, text: str) -> None:
        tok = self.take()
        if tok.kind != "op" or tok.text != text:
            raise ParseError(f"expected {text!r} at position {tok.pos}")

    def _enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise LimitError(f"expression nesting exceeds depth {MAX_DEPTH}")

    def _leave(self) -> None:
        self.depth -= 1

    def parse(self) -> Node:
        node = self.expr()
        tok = self.peek()
        if tok.kind != "end":
            raise ParseError(f"unexpected token {tok.text!r} at position {tok.pos}")
        return node

    def expr(self) -> Node:
        self._enter()
        node = self.term()
        while self.peek().kind == "op" and self.peek().text in "+-":
            op = self.take().text
            node = Binary(op, node, self.term())
        self._leave()
        return node

    def term(self) -> Node:
        self._enter()
        node = self.factor()
        while True:
            tok = self.peek()
            if tok.kind == "op" and tok.text in "*/":
                op = self.take().text
                node = Binary(op, node, self.factor())
            elif tok.kind in ("num", "name") or (tok.kind == "op" and tok.text == "("):
                # implicit multiplication: 2pi, 2(3+4), (1+1)(2+2)
                node = Binary("*", node, self.factor())
            else:
                break
        self._leave()
        return node

    def factor(self) -> Node:
        # factor = unary; "^" binds tighter than unary minus, so -3^2 = -(3^2)
        return self.unary()

    def unary(self) -> Node:
        self._enter()
        tok = self.peek()
        if tok.kind == "op" and tok.text in "+-":
            self.take()
            node: Node = Unary(tok.text, self.unary())
        else:
            node = self.power()
        self._leave()
        return node

    def power(self) -> Node:
        self._enter()
        base = self.primary()
        if self.peek().kind == "op" and self.peek().text == "^":
            self.take()
            # right associative; exponent may carry a unary sign (2^-2)
            node: Node = Binary("^", base, self.unary())
        else:
            node = base
        self._leave()
        return node

    def primary(self) -> Node:
        tok = self.take()
        if tok.kind == "num":
            return Num(_fraction_from_literal(tok.text))
        if tok.kind == "name":
            name = tok.text.lower()
            if name in _CONSTS:
                return Const(name)
            if name in _FUNCS_EXACT or name in _FUNCS_INEXACT:
                self.expect_op("(")
                arg = self.expr()
                self.expect_op(")")
                return Call(name, arg)
            raise ParseError(f"unknown identifier {tok.text!r} at position {tok.pos}")
        if tok.kind == "op" and tok.text == "(":
            node = self.expr()
            self.expect_op(")")
            return node
        raise ParseError(f"unexpected token {tok.text or 'end of input'!r} at position {tok.pos}")


def _fraction_from_literal(text: str) -> Fraction:
    # Fraction(str) accepts decimal and scientific notation exactly.
    try:
        return Fraction(text)
    except ValueError as exc:  # pragma: no cover - guarded by lexer
        raise LexError(f"invalid numeric literal {text!r}") from exc


def parse(source: str) -> Node:
    node = Parser(tokenize(source)).parse()
    stack = [(node, 1)]
    while stack:
        item, depth = stack.pop()
        if depth > MAX_AST_DEPTH:
            raise LimitError("expression tree exceeds the evaluation depth budget")
        if isinstance(item, Binary):
            stack.extend(((item.left, depth + 1), (item.right, depth + 1)))
        elif isinstance(item, Unary):
            stack.append((item.operand, depth + 1))
        elif isinstance(item, Call):
            stack.append((item.arg, depth + 1))
    return node


# ------------------------------- canonicalization ------------------------
def canonicalize(node: Node) -> str:
    """Deterministic canonical text form of a parsed expression."""
    if isinstance(node, Num):
        v = node.value
        return f"({_canonical_integer(v.numerator)} / {_canonical_integer(v.denominator)})" if v.denominator != 1 else _canonical_integer(v.numerator)
    if isinstance(node, Const):
        return node.name
    if isinstance(node, Unary):
        return f"({node.op}{canonicalize(node.operand)})"
    if isinstance(node, Binary):
        return f"({canonicalize(node.left)} {node.op} {canonicalize(node.right)})"
    if isinstance(node, Call):
        return f"{node.func}({canonicalize(node.arg)})"
    raise TypeError(f"unknown node {node!r}")


def _canonical_integer(value):
    text = str(value)
    if len(text.lstrip("-")) > MAX_NUMBER_DIGITS:
        coefficient = text.rstrip("0")
        exponent = len(text) - len(coefficient)
        if 0 < exponent <= MAX_NUMBER_DIGITS and len(coefficient.lstrip("-")) <= MAX_NUMBER_DIGITS:
            return f"{coefficient}e{exponent}"
    return text


# ------------------------------- evaluation ------------------------------
@dataclass(frozen=True)
class Result:
    value: Union[Fraction, Decimal]
    exact: bool
    precision: Optional[int]  # significant digits used when exact is False

    def as_strings(self) -> dict:
        if self.exact:
            frac = self.value
            assert isinstance(frac, Fraction)
            out = {
                "exact": True,
                "rational": f"{frac.numerator}/{frac.denominator}",
            }
            if frac.denominator == 1:
                out["integer"] = str(frac.numerator)
            out["decimal"] = _decimal_render(frac)
            return out
        return {
            "exact": False,
            "precision": self.precision,
            "decimal": str(self.value),
        }


def _decimal_render(frac: Fraction, digits: int = DEFAULT_PRECISION) -> str:
    with localcontext(_context()) as ctx:
        ctx.prec = digits
        return str(Decimal(frac.numerator) / Decimal(frac.denominator))


def evaluate(source: str, precision: int = DEFAULT_PRECISION) -> Result:
    """Pure evaluation of one expression. No side effects of any kind."""
    if not isinstance(source, str):
        raise ParseError("expression must be a string")
    if isinstance(precision, bool) or not isinstance(precision, int):
        # A017-F5: non-int precision previously escaped as a bare TypeError.
        raise LimitError("precision must be an integer")
    if not (1 <= precision <= 200):
        raise LimitError("precision must be between 1 and 200 significant digits")
    node = parse(source)
    try:
        with localcontext(_context()):
            value = _bounded(_eval(node, precision))
    except (Overflow, Underflow) as exc:
        raise LimitError("decimal result exceeds the supported magnitude range") from exc
    except DecimalException as exc:
        raise DomainError("numeric operation is undefined at this working precision") from exc
    except RecursionError as exc:
        raise LimitError("expression exceeds the evaluation recursion budget") from exc
    if isinstance(value, Fraction):
        return Result(value, True, None)
    return Result(value, False, precision)


def _eval(node: Node, precision: int) -> Union[Fraction, Decimal]:
    if isinstance(node, Num):
        return node.value
    if isinstance(node, Const):
        return _const(node.name, precision)
    if isinstance(node, Unary):
        val = _eval(node.operand, precision)
        return val if node.op == "+" else (val.copy_negate() if isinstance(val, Decimal) else -val)
    if isinstance(node, Binary):
        return _bounded(_binary(node, precision))
    if isinstance(node, Call):
        return _bounded(_call(node.func, _eval(node.arg, precision), precision))
    raise TypeError(f"unknown node {node!r}")


def _binary(node: Binary, precision: int) -> Union[Fraction, Decimal]:
    left = _eval(node.left, precision)
    right = _eval(node.right, precision)
    op = node.op
    if op == "^":
        if isinstance(right, Fraction):
            if right.denominator != 1:
                raise DomainError("non-integer exponents are not supported")
            exponent = right.numerator
        else:
            if right != right.to_integral_value():
                raise DomainError("non-integer exponents are not supported")
            if abs(right) > MAX_EXPONENT:
                raise LimitError("exponent exceeds the supported bound")
            exponent = int(right)
        if abs(exponent) > MAX_EXPONENT:
            raise LimitError("exponent exceeds the supported bound")
        if left == 0 and exponent <= 0:
            raise DomainError("zero to a nonpositive power is undefined")
        if isinstance(left, Fraction) and isinstance(right, Fraction):
            if max(abs(left.numerator).bit_length(), left.denominator.bit_length()) * abs(exponent) > MAX_INTEGER_BITS:
                raise LimitError("power exceeds the exact arithmetic bit budget")
            return left ** exponent
    if isinstance(left, Decimal) or isinstance(right, Decimal):
        l, r = _to_decimal(left, precision), _to_decimal(right, precision)
        with localcontext(_context()) as ctx:
            ctx.prec = precision
            if op == "+":
                return +(l + r)
            if op == "-":
                return +(l - r)
            if op == "*":
                return +(l * r)
            if op == "/":
                if r == 0:
                    raise DomainError("division by zero")
                return +(l / r)
            if op == "^":
                return +(l ** exponent)
    assert isinstance(left, Fraction) and isinstance(right, Fraction)
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        if right == 0:
            raise DomainError("division by zero")
        return left / right
    if op == "^":
        if right.denominator != 1:
            raise DomainError("non-integer exponents are not supported; use sqrt() for square roots")
        exp = right.numerator
        if abs(exp) > MAX_EXPONENT:
            raise LimitError(f"|exponent| exceeds {MAX_EXPONENT}")
        if left == 0 and exp < 0:
            raise DomainError("zero cannot be raised to a negative power")
        return left ** exp
    raise ParseError(f"unknown operator {op!r}")


def _to_decimal(value: Union[Fraction, Decimal], precision: int) -> Decimal:
    if isinstance(value, Decimal):
        return value
    with localcontext(_context()) as ctx:
        ctx.prec = precision
        return Decimal(value.numerator) / Decimal(value.denominator)


def _const(name: str, precision: int) -> Decimal:
    with localcontext(_context()) as ctx:
        ctx.prec = precision + 10
        if name == "pi":
            val = _pi()
        elif name == "e":
            val = Decimal(1).exp()
        else:  # pragma: no cover
            raise DomainError(f"unknown constant {name}")
    with localcontext(_context()) as ctx:
        ctx.prec = precision
        return +val


def _pi() -> Decimal:
    """Machin-like arctan series at current context precision."""
    ctx_prec = getcontext().prec

    def arctan_inv(x: int) -> Decimal:
        total = Decimal(0)
        term = Decimal(1) / x
        n = 0
        x2 = x * x
        while term != 0:
            total += term / (2 * n + 1) * (1 if n % 2 == 0 else -1)
            term /= x2
            n += 1
            if n > ctx_prec * 4:  # convergence guard
                break
        return total

    return 4 * (4 * arctan_inv(5) - arctan_inv(239))


def _call(func: str, arg: Union[Fraction, Decimal], precision: int) -> Union[Fraction, Decimal]:
    if func in _FUNCS_EXACT:
        if isinstance(arg, Decimal):
            with localcontext(_context()) as ctx:
                ctx.prec = precision
                if func == "abs":
                    return abs(arg)
                if func == "floor":
                    return arg.to_integral_value(rounding="ROUND_FLOOR")
                if func == "ceil":
                    return arg.to_integral_value(rounding="ROUND_CEILING")
        assert isinstance(arg, Fraction)
        if func == "abs":
            return abs(arg)
        if func == "floor":
            return Fraction(arg.numerator // arg.denominator)
        if func == "ceil":
            return Fraction(-((-arg.numerator) // arg.denominator))

    if func == "sqrt":
        if isinstance(arg, Fraction):
            if arg < 0:
                raise DomainError("sqrt of a negative number")
            num_root = _isqrt_exact(arg.numerator)
            den_root = _isqrt_exact(arg.denominator)
            if num_root is not None and den_root is not None:
                return Fraction(num_root, den_root)   # exact perfect square
        dec = _to_decimal(arg, precision + 10)
        if dec < 0:
            raise DomainError("sqrt of a negative number")
        with localcontext(_context()) as ctx:
            ctx.prec = precision
            return dec.sqrt()

    dec = _to_decimal(arg, precision + 10)
    extra = 0
    if func in ("sin", "cos", "tan"):
        extra = max(0, dec.adjusted())
        if extra > MAX_TRIG_MAGNITUDE:
            raise LimitError("trigonometric argument exceeds the reduction budget")
        dec = _to_decimal(arg, precision + 10 + extra)
    with localcontext(_context()) as ctx:
        ctx.prec = precision + 10 + extra
        if func == "exp":
            out = dec.exp()
        elif func == "ln":
            if dec <= 0:
                raise DomainError("ln requires a positive argument")
            out = dec.ln()
        elif func == "log10":
            if dec <= 0:
                raise DomainError("log10 requires a positive argument")
            out = dec.log10()
        elif func in ("sin", "cos", "tan"):
            out = _trig(func, dec, precision)
        else:  # pragma: no cover
            raise DomainError(f"unknown function {func}")
    with localcontext(_context()) as ctx:
        ctx.prec = precision
        return +out


def _isqrt_exact(n: int) -> Optional[int]:
    # A017-F1: float-based root overflowed (OverflowError) for ints >= 1e308;
    # math.isqrt is exact and overflow-free for arbitrary size.
    if n < 0:
        return None
    import math
    cand = math.isqrt(n)
    return cand if cand * cand == n else None


def _trig(func: str, x: Decimal, precision: int) -> Decimal:
    """Taylor series with argument reduction modulo 2*pi."""
    pi = _pi()
    two_pi = 2 * pi
    x = x % two_pi
    if func == "tan":
        c = _trig("cos", x, precision)
        if abs(c) <= Decimal(1).scaleb(-max(1, precision - 2)):
            raise DomainError("tan is numerically unresolved near a pole at this precision")
        return _trig("sin", x, precision) / c
    total = Decimal(0)
    term = x if func == "sin" else Decimal(1)
    n = 0
    while term != 0 and n < 1000:
        updated = total + (term if n % 2 == 0 else -term)
        if n and updated == total:
            break
        total = updated
        if func == "sin":
            term = term * x * x / ((2 * n + 2) * (2 * n + 3))
        else:
            term = term * x * x / ((2 * n + 1) * (2 * n + 2))
        n += 1
    return total
