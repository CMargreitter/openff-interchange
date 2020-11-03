from openforcefield.topology import Molecule, Topology
from openforcefield.typing.engines.smirnoff.parameters import AngleHandler, BondHandler
from simtk import unit as omm_unit

from openff.system.tests.base_test import BaseTest
from openff.system.utils import simtk_to_pint


class TestBondPotentialHandler(BaseTest):
    def test_bond_parameter_handler(self):
        top = Topology.from_molecules(Molecule.from_smiles("O=O"))

        bond_handler = BondHandler(version=0.3)
        bond_parameter = BondHandler.BondType(
            smirks="[*:1]~[*:2]",
            k=1.5 * omm_unit.kilocalorie_per_mole / omm_unit.angstrom ** 2,
            length=1.5 * omm_unit.angstrom,
            id="b1000",
        )
        bond_handler.add_parameter(bond_parameter.to_dict())

        from openff.system.stubs import ForceField

        forcefield = ForceField()
        forcefield.register_parameter_handler(bond_handler)
        bond_potentials = forcefield["Bonds"].create_potential(top)

        pot = bond_potentials.potentials[bond_potentials.slot_map[(0, 1)]]
        kcal_ang2_mol = omm_unit.kilocalorie_per_mole / omm_unit.angstrom ** 2

        assert pot.parameters["k"] == simtk_to_pint(1.5 * kcal_ang2_mol)

    def test_angle_parameter_handler(self):
        top = Topology.from_molecules(Molecule.from_smiles("CCC"))

        angle_handler = AngleHandler(version=0.3)
        angle_parameter = AngleHandler.AngleType(
            smirks="[*:1]~[*:2]~[*:3]",
            k=2.5 * omm_unit.kilocalorie_per_mole / omm_unit.degree ** 2,
            angle=100 * omm_unit.degree,
            id="b1000",
        )
        angle_handler.add_parameter(angle_parameter.to_dict())

        from openff.system.stubs import ForceField

        forcefield = ForceField()
        forcefield.register_parameter_handler(angle_handler)
        angle_potentials = forcefield["Angles"].create_potential(top)

        pot = angle_potentials.potentials[angle_potentials.slot_map[(0, 1, 2)]]
        kcal_deg2_mol = omm_unit.kilocalorie_per_mole / omm_unit.degree ** 2

        assert pot.parameters["k"] == simtk_to_pint(2.5 * kcal_deg2_mol)
