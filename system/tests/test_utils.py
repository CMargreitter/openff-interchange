import pytest
import numpy as np
from simtk import unit as simtk_unit

from .. import unit
from system.utils import simtk_to_pint, pint_to_simtk, compare_sympy_expr, get_partial_charges_from_openmm_system
from .base_test import BaseTest


simtk_quantitites = [
    4.0 * simtk_unit.nanometer,
    5.0 * simtk_unit.angstrom,
    1.0 * simtk_unit.elementary_charge,
]

pint_quantities = [
    4.0 * unit.nanometer,
    5.0 * unit.angstrom,
    1.0 * unit.elementary_charge,
]


@pytest.mark.parametrize(
    'simtk_quantity,pint_quantity',
    [(s, p) for s, p in zip(simtk_quantitites, pint_quantities)]
)
def test_simtk_to_pint(simtk_quantity, pint_quantity):
    """Test conversion from SimTK Quantity to pint Quantity."""
    converted_pint_quantity = simtk_to_pint(simtk_quantity)

    assert pint_quantity == converted_pint_quantity


def test_pint_to_simtk():
    """Test conversion from pint Quantity to SimTK Quantity."""
    with pytest.raises(NotImplementedError):
        pint_to_simtk(None)


@pytest.mark.parametrize(
    'expr1,expr2,result',
    [
        ('x+1', 'x+1', True),
        ('x+1', 'x**2+1', False),
        ('0.5*k*(th-th0)**2', 'k*(th-th0)**2', False),
        ('k*(1+cos(n*th-th0))', 'k*(1+cos(n*th-th0))', True),
    ]
)
def test_compare_sympy_expr(expr1, expr2, result):
    assert compare_sympy_expr(expr1, expr2) == result


class TestOpenMM(BaseTest):
    def test_openmm_partial_charges(self, argon_ff, argon_top):
        omm_system = argon_ff.create_openmm_system(argon_top)
        partial_charges = get_partial_charges_from_openmm_system(omm_system)

        assert isinstance(partial_charges, unit.Quantity)
        assert partial_charges.units == unit.elementary_charge
        assert np.allclose(partial_charges.magnitude, np.zeros(4))
