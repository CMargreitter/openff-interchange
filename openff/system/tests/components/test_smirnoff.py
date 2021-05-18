import numpy as np
import pytest
from openff.toolkit.topology import Molecule
from openff.toolkit.typing.engines.smirnoff import ImproperTorsionHandler
from openff.toolkit.typing.engines.smirnoff.parameters import AngleHandler, BondHandler
from openff.units import unit
from openff.utilities.testing import skip_if_missing
from simtk import unit as omm_unit
from simtk import unit as simtk_unit

from openff.system.components.mdtraj import OFFBioTop
from openff.system.components.smirnoff import (
    SMIRNOFFAngleHandler,
    SMIRNOFFBondHandler,
    SMIRNOFFImproperTorsionHandler,
    SMIRNOFFvdWHandler,
)
from openff.system.models import TopologyKey
from openff.system.tests import BaseTest
from openff.system.utils import get_test_file_path


class TestSMIRNOFFHandlers(BaseTest):
    def test_bond_potential_handler(self):
        top = OFFBioTop.from_molecules(Molecule.from_smiles("O=O"))

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
        bond_potentials, _ = SMIRNOFFBondHandler.from_toolkit(
            bond_handler=forcefield["Bonds"],
            topology=top,
        )

        top_key = TopologyKey(atom_indices=(0, 1))
        pot = bond_potentials.potentials[bond_potentials.slot_map[top_key]]

        kcal_mol_a2 = unit.Unit("kilocalorie / (angstrom ** 2 * mole)")
        assert pot.parameters["k"].to(kcal_mol_a2).magnitude == pytest.approx(1.5)

    def test_angle_potential_handler(self):
        top = OFFBioTop.from_molecules(Molecule.from_smiles("CCC"))

        angle_handler = AngleHandler(version=0.3)
        angle_parameter = AngleHandler.AngleType(
            smirks="[*:1]~[*:2]~[*:3]",
            k=2.5 * omm_unit.kilocalorie_per_mole / omm_unit.radian ** 2,
            angle=100 * omm_unit.degree,
            id="b1000",
        )
        angle_handler.add_parameter(angle_parameter.to_dict())

        from openff.system.stubs import ForceField

        forcefield = ForceField()
        forcefield.register_parameter_handler(angle_handler)
        angle_potentials = SMIRNOFFAngleHandler.from_toolkit(
            parameter_handler=forcefield["Angles"],
            topology=top,
        )

        top_key = TopologyKey(atom_indices=(0, 1, 2))
        pot = angle_potentials.potentials[angle_potentials.slot_map[top_key]]

        kcal_mol_rad2 = unit.Unit("kilocalorie / (mole * radian ** 2)")
        assert pot.parameters["k"].to(kcal_mol_rad2).magnitude == pytest.approx(2.5)

    def test_store_improper_torsion_matches(self):

        formaldehyde: Molecule = Molecule.from_mapped_smiles("[H:3][C:1]([H:4])=[O:2]")

        parameter_handler = ImproperTorsionHandler(version=0.3)
        parameter_handler.add_parameter(
            parameter=ImproperTorsionHandler.ImproperTorsionType(
                smirks="[*:1]~[#6X3:2](~[*:3])~[*:4]",
                periodicity1=2,
                phase1=180.0 * simtk_unit.degree,
                k1=1.1 * simtk_unit.kilocalorie_per_mole,
            )
        )

        potential_handler = SMIRNOFFImproperTorsionHandler()
        potential_handler.store_matches(parameter_handler, formaldehyde.to_topology())

        assert len(potential_handler.slot_map) == 3

        assert (
            TopologyKey(atom_indices=(0, 1, 2, 3), mult=0) in potential_handler.slot_map
        )
        assert (
            TopologyKey(atom_indices=(0, 2, 3, 1), mult=0) in potential_handler.slot_map
        )
        assert (
            TopologyKey(atom_indices=(0, 3, 1, 2), mult=0) in potential_handler.slot_map
        )


@skip_if_missing("jax")
class TestMatrixRepresentations(BaseTest):
    @pytest.mark.parametrize(
        "handler_name,n_ff_terms,n_sys_terms",
        [("vdW", 10, 72), ("Bonds", 8, 64), ("Angles", 6, 104)],
    )
    def test_to_force_field_to_system_parameters(
        self, parsley, ethanol_top, handler_name, n_ff_terms, n_sys_terms
    ):
        import jax

        if handler_name == "Bonds":
            handler, _ = SMIRNOFFBondHandler.from_toolkit(
                bond_handler=parsley["Bonds"],
                topology=ethanol_top,
                constraint_handler=None,
            )
        elif handler_name == "Angles":
            handler = SMIRNOFFAngleHandler.from_toolkit(
                parameter_handler=parsley[handler_name],
                topology=ethanol_top,
            )
        elif handler_name == "vdW":
            handler = SMIRNOFFvdWHandler._from_toolkit(
                parameter_handler=parsley[handler_name],
                topology=ethanol_top,
            )
        else:
            raise NotImplementedError()

        p = handler.get_force_field_parameters()

        assert isinstance(p, jax.interpreters.xla.DeviceArray)
        assert np.prod(p.shape) == n_ff_terms

        q = handler.get_system_parameters()

        assert isinstance(q, jax.interpreters.xla.DeviceArray)
        assert np.prod(q.shape) == n_sys_terms

        assert jax.numpy.allclose(q, handler.parametrize(p))

        param_matrix = handler.get_param_matrix()

        ref_file = get_test_file_path(f"ethanol_param_{handler_name.lower()}.npy")
        ref = jax.numpy.load(ref_file)

        assert jax.numpy.allclose(ref, param_matrix)

        # TODO: Update with other handlers that can safely be assumed to follow 1:1 slot:smirks mapping
        if handler_name in ["vdW", "Bonds", "Angles"]:
            assert np.allclose(
                np.sum(param_matrix, axis=1), np.ones(param_matrix.shape[0])
            )
