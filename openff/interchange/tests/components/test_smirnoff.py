import numpy as np
import pytest
from openff.toolkit.tests.utils import get_data_file_path
from openff.toolkit.topology import Molecule, Topology
from openff.toolkit.typing.engines.smirnoff.forcefield import ForceField
from openff.toolkit.typing.engines.smirnoff.parameters import (
    AngleHandler,
    BondHandler,
    ChargeIncrementModelHandler,
    ElectrostaticsHandler,
    ImproperTorsionHandler,
    LibraryChargeHandler,
    ParameterHandler,
    ToolkitAM1BCCHandler,
    VirtualSiteHandler,
)
from openff.units import unit
from openff.utilities.testing import skip_if_missing
from simtk import openmm
from simtk import unit as omm_unit
from simtk import unit as simtk_unit

from openff.interchange.components.interchange import Interchange
from openff.interchange.components.mdtraj import OFFBioTop
from openff.interchange.components.smirnoff import (
    SMIRNOFFAngleHandler,
    SMIRNOFFBondHandler,
    SMIRNOFFConstraintHandler,
    SMIRNOFFElectrostaticsHandler,
    SMIRNOFFImproperTorsionHandler,
    SMIRNOFFPotentialHandler,
    SMIRNOFFvdWHandler,
    SMIRNOFFVirtualSiteHandler,
    library_charge_from_molecule,
)
from openff.interchange.exceptions import InvalidParameterHandlerError
from openff.interchange.models import TopologyKey, VirtualSiteKey
from openff.interchange.tests import BaseTest
from openff.interchange.utils import get_test_file_path


class TestSMIRNOFFPotentialHandler(BaseTest):
    def test_allowed_parameter_handler_types(self):
        class DummyParameterHandler(ParameterHandler):
            pass

        class DummySMIRNOFFHandler(SMIRNOFFPotentialHandler):
            type = "Bonds"
            expression = "1+1"

            @classmethod
            def allowed_parameter_handlers(cls):
                return [DummyParameterHandler]

            @classmethod
            def supported_parameters(cls):
                return list()

        dummy_handler = DummySMIRNOFFHandler()
        angle_Handler = AngleHandler(version=0.3)

        assert DummyParameterHandler in dummy_handler.allowed_parameter_handlers()
        assert AngleHandler not in dummy_handler.allowed_parameter_handlers()
        assert (
            DummyParameterHandler
            not in SMIRNOFFAngleHandler.allowed_parameter_handlers()
        )

        dummy_handler = DummyParameterHandler(version=0.3)

        with pytest.raises(InvalidParameterHandlerError):
            SMIRNOFFAngleHandler._from_toolkit(
                parameter_handler=dummy_handler,
                topology=Topology(),
            )

        with pytest.raises(InvalidParameterHandlerError):
            DummySMIRNOFFHandler._from_toolkit(
                parameter_handler=angle_Handler,
                topology=Topology(),
            )


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

        from openff.toolkit.typing.engines.smirnoff import ForceField

        forcefield = ForceField()
        forcefield.register_parameter_handler(bond_handler)
        bond_potentials = SMIRNOFFBondHandler._from_toolkit(
            parameter_handler=forcefield["Bonds"],
            topology=top,
        )

        top_key = TopologyKey(atom_indices=(0, 1))
        pot_key = bond_potentials.slot_map[top_key]
        assert pot_key.associated_handler == "Bonds"
        pot = bond_potentials.potentials[pot_key]

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

        forcefield = ForceField()
        forcefield.register_parameter_handler(angle_handler)
        angle_potentials = SMIRNOFFAngleHandler._from_toolkit(
            parameter_handler=forcefield["Angles"],
            topology=top,
        )

        top_key = TopologyKey(atom_indices=(0, 1, 2))
        pot_key = angle_potentials.slot_map[top_key]
        assert pot_key.associated_handler == "Angles"
        pot = angle_potentials.potentials[pot_key]

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

    def test_electrostatics_am1_handler(self):
        top = OFFBioTop.from_molecules(Molecule.from_smiles("C"))

        parameter_handlers = [
            ElectrostaticsHandler(version=0.3),
            ToolkitAM1BCCHandler(version=0.3),
        ]

        electrostatics_handler = SMIRNOFFElectrostaticsHandler._from_toolkit(
            parameter_handlers, top
        )

        np.testing.assert_allclose(
            [charge.m_as(unit.e) for charge in electrostatics_handler.charges.values()],
            [-0.1088, 0.0267, 0.0267, 0.0267, 0.0267],
        )

    def test_electrostatics_library_charges(self):
        top = OFFBioTop.from_molecules(Molecule.from_smiles("C"))

        library_charge_handler = LibraryChargeHandler(version=0.3)
        library_charge_handler.add_parameter(
            {
                "smirks": "[#6X4:1]-[#1:2]",
                "charge1": -0.1 * simtk_unit.elementary_charge,
                "charge2": 0.025 * simtk_unit.elementary_charge,
            }
        )

        parameter_handlers = [
            ElectrostaticsHandler(version=0.3),
            library_charge_handler,
        ]

        electrostatics_handler = SMIRNOFFElectrostaticsHandler._from_toolkit(
            parameter_handlers, top
        )

        np.testing.assert_allclose(
            [charge.m_as(unit.e) for charge in electrostatics_handler.charges.values()],
            [-0.1, 0.025, 0.025, 0.025, 0.025],
        )

    def test_electrostatics_charge_increments(self):
        top = OFFBioTop.from_molecules(Molecule.from_mapped_smiles("[Cl:1][H:2]"))

        charge_increment_handler = ChargeIncrementModelHandler(version=0.3)
        charge_increment_handler.add_parameter(
            {
                "smirks": "[#17:1]-[#1:2]",
                "charge_increment1": 0.1 * simtk_unit.elementary_charge,
                "charge_increment2": -0.1 * simtk_unit.elementary_charge,
            }
        )

        parameter_handlers = [
            ElectrostaticsHandler(version=0.3),
            charge_increment_handler,
        ]

        electrostatics_handler = SMIRNOFFElectrostaticsHandler._from_toolkit(
            parameter_handlers, top
        )

        # AM1-Mulliken charges are [-0.168,  0.168], increments are [0.1, -0.1],
        # sum is [-0.068,  0.068]
        np.testing.assert_allclose(
            [charge.m_as(unit.e) for charge in electrostatics_handler.charges.values()],
            [-0.068, 0.068],
        )

    # TODO: Remove xfail after openff-toolkit 0.10.0
    @pytest.mark.xfail()
    def test_charges_with_virtual_site(self, parsley):
        mol = Molecule.from_smiles("CCl")
        mol.generate_conformers(n_conformers=1)
        mol.partial_charges = simtk_unit.elementary_charge * np.array(
            [0.5, -0.8, 0.1, 0.1, 0.1]
        )

        parsley = ForceField("openff-1.3.1.offxml")
        parsley.deregister_parameter_handler(parsley["ToolkitAM1BCC"])
        parsley.deregister_parameter_handler(parsley["LibraryCharges"])

        library_charge_handler = LibraryChargeHandler(version=0.3)

        library_charge_type = LibraryChargeHandler.LibraryChargeType.from_molecule(mol)
        library_charge_handler.add_parameter(parameter=library_charge_type)

        parsley.register_parameter_handler(library_charge_handler)

        virtual_site_handler = VirtualSiteHandler(version=0.3)

        sigma_type = VirtualSiteHandler.VirtualSiteBondChargeType(
            name="EP",
            smirks="[#6:1]-[#17:2]",
            distance=1.4 * simtk_unit.angstrom,
            type="BondCharge",
            match="once",
            charge_increment1=0.2 * simtk_unit.elementary_charge,
            charge_increment2=0.1 * simtk_unit.elementary_charge,
        )

        virtual_site_handler.add_parameter(parameter=sigma_type)
        parsley.register_parameter_handler(virtual_site_handler)

        out = Interchange.from_smirnoff(force_field=parsley, topology=mol.to_topology())
        out["Electrostatics"]._from_toolkit_virtual_sites(
            parameter_handler=parsley["VirtualSites"], topology=mol.to_topology()
        )

        via_toolkit = parsley.create_openmm_system(mol.to_topology())

        charges = []
        for force in via_toolkit.getForces():
            if type(force) == openmm.NonbondedForce:
                for i in range(6):
                    charges.append(force.getParticleParameters(i)[0]._value)

        # Final charges are
        #   [0.5, -0.8, 0.1, 0.1, 0.1]
        # + [0.2, 0.1, 0.0, 0.0, 0.0, -0.3]
        # = [0.7, -0.7, 0.1, 0.1, 0.1, -0.3]
        np.testing.assert_allclose(
            charges,
            [v.m for v in out["Electrostatics"].charges_with_virtual_sites.values()],
        )

        np.testing.assert_allclose(
            charges[:5], [v.m for v in out["Electrostatics"].charges.values()]
        )


class TestConstraints:
    @pytest.mark.parametrize(
        ("mol", "n_constraints"),
        [
            ("C", 4),
            ("CC", 6),
        ],
    )
    def test_num_constraints(self, mol, n_constraints):
        force_field = ForceField("openff-1.0.0.offxml")

        bond_handler = force_field["Bonds"]
        constraint_handler = force_field["Constraints"]

        topology = Molecule.from_smiles(mol).to_topology()

        constraints = SMIRNOFFConstraintHandler._from_toolkit(
            parameter_handler=[
                val for val in [bond_handler, constraint_handler] if val is not None
            ],
            topology=topology,
        )

        assert len(constraints.slot_map) == n_constraints


# TODO: Remove xfail after openff-toolkit 0.10.0
@pytest.mark.xfail()
def test_library_charges_from_molecule():
    mol = Molecule.from_mapped_smiles("[Cl:1][C:2]#[C:3][F:4]")

    with pytest.raises(ValueError, match="missing partial"):
        library_charge_from_molecule(mol)

    mol.partial_charges = np.linspace(-0.3, 0.3, 4) * simtk_unit.elementary_charge

    library_charges = library_charge_from_molecule(mol)

    assert isinstance(library_charges, LibraryChargeHandler.LibraryChargeType)
    assert library_charges.smirks == mol.to_smiles(mapped=True)
    assert library_charges.charge == [*mol.partial_charges]


@skip_if_missing("jax")
class TestMatrixRepresentations(BaseTest):
    @pytest.mark.parametrize(
        ("handler_name", "n_ff_terms", "n_sys_terms"),
        [("vdW", 10, 72), ("Bonds", 8, 64), ("Angles", 6, 104)],
    )
    def test_to_force_field_to_system_parameters(
        self, parsley, ethanol_top, handler_name, n_ff_terms, n_sys_terms
    ):
        import jax

        if handler_name == "Bonds":
            handler = SMIRNOFFBondHandler._from_toolkit(
                parameter_handler=parsley["Bonds"],
                topology=ethanol_top,
            )
        elif handler_name == "Angles":
            handler = SMIRNOFFAngleHandler._from_toolkit(
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


class TestSMIRNOFFVirtualSites:
    from openff.toolkit.tests.test_forcefield import TestForceFieldVirtualSites

    @pytest.mark.parametrize(
        ("xml", "mol"),
        [
            (
                TestForceFieldVirtualSites.xml_ff_virtual_sites_bondcharge_match_once,
                "O=O",
            ),
            # TODO: Implement match="once"
            # (
            #     xml_ff_virtual_sites_bondcharge_match_once,
            #     "N#N",
            # ),
            (
                TestForceFieldVirtualSites.xml_ff_virtual_sites_bondcharge_match_all,
                "N#N",
            ),
            # TODO: Implement match="once" with two names
            # (
            #     xml_ff_virtual_sites_bondcharge_match_once_two_names,
            #     "N#N",
            # ),
            (
                TestForceFieldVirtualSites.xml_ff_virtual_sites_bondcharge_match_once,
                "CC=O",
            ),
            (
                TestForceFieldVirtualSites.xml_ff_virtual_sites_divalent_match_all,
                "O",
            ),
            (
                TestForceFieldVirtualSites.xml_ff_virtual_sites_trivalent_match_once,
                "N",
            ),
        ],
    )
    def test_store_bond_charge_virtual_sites(self, xml, mol):
        from openff.toolkit.tests.test_forcefield import create_dinitrogen

        if mol == "N#N":
            top = create_dinitrogen().to_topology()
        else:
            top = Molecule.from_smiles(mol).to_topology()

        forcefield = ForceField(
            get_data_file_path("test_forcefields/test_forcefield.offxml"),
            xml,
        )
        out = Interchange.from_smirnoff(force_field=forcefield, topology=top)
        vdw = out["vdW"]

        vdw._from_toolkit_virtual_sites(
            parameter_handler=forcefield["VirtualSites"], topology=top
        )

        assert _get_n_virtual_sites(vdw) == _get_n_virtual_sites_toolkit(
            force_field=forcefield,
            topology=top,
        )

        coul = out["Electrostatics"]

        coul._from_toolkit_virtual_sites(
            parameter_handler=forcefield["VirtualSites"], topology=top
        )

        assert _get_n_virtual_sites(coul) == _get_n_virtual_sites_toolkit(
            force_field=forcefield,
            topology=top,
        )

    def test_store_trivalent_lone_pair_virtual_site(self):
        from openff.toolkit.tests.test_forcefield import (
            TestForceFieldVirtualSites,
            create_ammonia,
        )

        top = create_ammonia().to_topology()

        file_path = get_data_file_path("test_forcefields/test_forcefield.offxml")
        forcefield = ForceField(
            file_path,
            TestForceFieldVirtualSites.xml_ff_virtual_sites_trivalent_match_once,
        )

        vdw = SMIRNOFFvdWHandler._from_toolkit(
            parameter_handler=forcefield["vdW"], topology=top
        )

        vdw._from_toolkit_virtual_sites(
            parameter_handler=forcefield["VirtualSites"], topology=top
        )

        assert _get_n_virtual_sites(vdw) == _get_n_virtual_sites_toolkit(
            force_field=forcefield,
            topology=top,
        )

    def test_store_tip4p_virtual_site(self):
        from openff.toolkit.tests.test_forcefield import create_water

        top = create_water().to_topology()

        tip4p = ForceField(get_test_file_path("tip4p.offxml"))

        vdw = SMIRNOFFvdWHandler._from_toolkit(
            parameter_handler=tip4p["vdW"], topology=top
        )

        vdw._from_toolkit_virtual_sites(
            parameter_handler=tip4p["VirtualSites"], topology=top
        )

        assert _get_n_virtual_sites(vdw) == _get_n_virtual_sites_toolkit(
            force_field=tip4p,
            topology=top,
        )

        virtual_site_handler = SMIRNOFFVirtualSiteHandler._from_toolkit(
            parameter_handler=tip4p["VirtualSites"], topology=top
        )

        assert len(virtual_site_handler.slot_map) == 1
        assert len(virtual_site_handler.potentials) == 1

    def test_store_tip5p_virtual_site(self):
        from openff.toolkit.tests.test_forcefield import create_water

        top = create_water().to_topology()

        tip5p = ForceField(get_test_file_path("tip5p.offxml"))

        vdw = SMIRNOFFvdWHandler._from_toolkit(
            parameter_handler=tip5p["vdW"], topology=top
        )

        vdw._from_toolkit_virtual_sites(
            parameter_handler=tip5p["VirtualSites"], topology=top
        )

        assert _get_n_virtual_sites(vdw) == _get_n_virtual_sites_toolkit(
            force_field=tip5p,
            topology=top,
        )

        virtual_site_handler = SMIRNOFFVirtualSiteHandler._from_toolkit(
            parameter_handler=tip5p["VirtualSites"], topology=top
        )

        assert len(virtual_site_handler.slot_map) == 2
        assert len(virtual_site_handler.potentials) == 1


def _get_n_virtual_sites(handler: "SMIRNOFFPotentialHandler") -> int:
    """Get the number of TopologyKey objects in a SMIRNOFFvdWHandler that likely
    correspond to virtual sites"""
    return len([key for key in handler.slot_map if type(key) == VirtualSiteKey])


def _get_n_virtual_sites_toolkit(
    force_field: "ForceField", topology: "Topology"
) -> int:
    """Get the number of virtual particles created by ForceField.create_openmm_system"""
    n_atoms = topology.n_topology_atoms
    omm_sys = force_field.create_openmm_system(topology)

    for force in omm_sys.getForces():
        if type(force) == openmm.NonbondedForce:
            n_openmm_particles = force.getNumParticles()
            return n_openmm_particles - n_atoms
