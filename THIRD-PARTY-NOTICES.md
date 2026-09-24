# Third-party notices

## amplifier-collection-recipes — Microsoft Corporation, MIT

The gate-condition evaluator and donor-derived behavior tests originated in
amplifier-collection-recipes:
modules/tool-recipes/amplifier_module_tool_recipes/expression_evaluator.py and
modules/tool-recipes/tests/test_expression_evaluator.py.

Full upstream license:
[LICENSE.amplifier-collection-recipes.txt](e01_calculator/vendor/LICENSE.amplifier-collection-recipes.txt).
The upstream MIT license and copyright remain in force.

September 2026 modifications by RUSSELL PHILIP SMITHSON replace string-splicing
and splitting with bounded token parsing, treat context values as data, validate
all branches and enforce scalar limits. This adaptation reuses the reviewed
local R08 candidate's parser. The file is modified, not an unmodified upstream copy.

The original calculator and service code are Apache 2.0; see LICENSE and NOTICE.
No other third-party code or runtime package is vendored.
