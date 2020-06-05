from typing import Dict, Set, Union

from pint import Quantity
from pydantic import BaseModel, validator
import sympy
from sympy import Expr


class AnalyticalPotential(BaseModel):
    """
    Generic representation of an interaction potential having an analytic
    form and lacking parameters.
    """

    name: str = None
    smirks: str = None
    expression: Union[Expr, str]
    independent_variables: Union[str, Set[Union[Expr, str]]]

    @validator("expression")
    def is_valid_sympy_expr(cls, val):
        if isinstance(val, Expr):
            return str(val)
        elif isinstance(val, str):
            return val

    class Config:
        arbitrary_types_allowed = True


class ParametrizedAnalyticalPotential(AnalyticalPotential):
    """AnalyticalPotential but filled with parameters."""

    parameters: Dict[Union[Expr, str], Quantity]

    @validator("parameters")
    def is_valid(cls, val, values):

        symbols_in_expr = sympy.sympify(values['expression']).free_symbols
        symbols_in_indep_vars = sympy.symbols(values['independent_variables'])
        symbols_in_parameters = sympy.symbols(set(val.keys()))

        print(symbols_in_expr)
        print(symbols_in_indep_vars)
        print(symbols_in_parameters)

        assert symbols_in_expr - symbols_in_indep_vars - symbols_in_parameters == set()

        return val
