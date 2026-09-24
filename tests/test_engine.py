import unittest
from decimal import Decimal
from fractions import Fraction

from e01_calculator import engine
from e01_calculator.engine import (CalcError, DomainError, LexError, LimitError,
                                   ParseError, evaluate, parse, canonicalize)


class ExactArithmetic(unittest.TestCase):
    def check(self, expr, frac):
        r = evaluate(expr)
        self.assertTrue(r.exact, expr)
        self.assertEqual(r.value, Fraction(frac), expr)

    def test_basics(self):
        self.check("1+2*3", 7)
        self.check("(1+2)*3", 9)
        self.check("10/4", Fraction(5, 2))
        self.check("0.1 + 0.2", Fraction(3, 10))          # exact, unlike floats
        self.check("1/3 + 1/6", Fraction(1, 2))
        self.check("2^10", 1024)
        self.check("2^-2", Fraction(1, 4))
        self.check("-3^2", -9)                             # unary binds looser than ^
        self.check("(-3)^2", 9)
        self.check("2**3", 8)                              # ** alias
        self.check("1e3 + 1", 1001)
        self.check("2.5e-1", Fraction(1, 4))

    def test_implicit_multiplication(self):
        self.check("2(3+4)", 14)
        self.check("(1+1)(2+2)", 8)

    def test_exact_functions(self):
        self.check("abs(-7/2)", Fraction(7, 2))
        self.check("floor(7/2)", 3)
        self.check("ceil(7/2)", 4)
        self.check("floor(-7/2)", -4)
        self.check("ceil(-7/2)", -3)
        self.check("sqrt(49)", 7)
        self.check("sqrt(9/16)", Fraction(3, 4))

    def test_big_exact(self):
        r = evaluate("2^1000 / 2^998")
        self.assertEqual(r.value, Fraction(4))


class InexactArithmetic(unittest.TestCase):
    def test_sqrt2(self):
        r = evaluate("sqrt(2)", precision=30)
        self.assertFalse(r.exact)
        self.assertTrue(str(r.value).startswith("1.4142135623730950488"))

    def test_pi(self):
        r = evaluate("pi", precision=30)
        self.assertTrue(str(r.value).startswith("3.14159265358979323846"))

    def test_e(self):
        r = evaluate("e", precision=30)
        self.assertTrue(str(r.value).startswith("2.71828182845904523536"))

    def test_trig_identity(self):
        r = evaluate("sin(1)^2 + cos(1)^2", precision=30)
        self.assertAlmostEqual(float(r.value), 1.0, places=20)

    def test_ln_exp(self):
        r = evaluate("ln(exp(1))", precision=30)
        self.assertAlmostEqual(float(r.value), 1.0, places=20)

    def test_log10(self):
        r = evaluate("log10(1000)", precision=30)
        self.assertAlmostEqual(float(r.value), 3.0, places=20)


class Errors(unittest.TestCase):
    def test_division_by_zero(self):
        with self.assertRaises(DomainError):
            evaluate("1/0")

    def test_sqrt_negative(self):
        with self.assertRaises(DomainError):
            evaluate("sqrt(-1)")

    def test_ln_domain(self):
        with self.assertRaises(DomainError):
            evaluate("ln(0)")

    def test_non_integer_exponent(self):
        with self.assertRaises(DomainError):
            evaluate("2^(1/2)")

    def test_parse_error(self):
        for bad in ("1+", "(1", "1)+2", "foo(1)", "1 $ 2"):
            with self.assertRaises(CalcError):
                evaluate(bad)

    def test_limits(self):
        with self.assertRaises(LimitError):
            evaluate("2^100000")
        with self.assertRaises(LimitError):
            evaluate("(" * 100 + "1" + ")" * 100)
        with self.assertRaises(LimitError):
            evaluate("1+" * 2000 + "1")

    def test_zero_negative_power(self):
        with self.assertRaises(DomainError):
            evaluate("0^-1")


class Canonicalization(unittest.TestCase):
    def test_deterministic(self):
        a = canonicalize(parse("1 +2* 3"))
        b = canonicalize(parse("1+2*3"))
        self.assertEqual(a, b)
        self.assertEqual(a, "(1 + (2 * 3))")

    def test_cross_notation(self):
        self.assertEqual(canonicalize(parse("2**3")), canonicalize(parse("2^3")))


if __name__ == "__main__":
    unittest.main()
