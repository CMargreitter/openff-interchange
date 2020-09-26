import tempfile

import numpy as np
import parmed as pmd
from intermol.gromacs import energies as gmx_energy
from openforcefield.topology import Molecule, Topology
from openforcefield.typing.engines.smirnoff.forcefield import ForceField
from pkg_resources import resource_filename
from simtk import unit

from ...system import System


def openff_openmm_pmd_gmx(
    topology: Topology, forcefield: ForceField, prefix: str
) -> None:
    """Pipeline to write GROMACS files from and OpenMM system through ParmEd"""
    omm_sys = forcefield.create_openmm_system(topology)

    struct = pmd.openmm.load_topology(
        system=omm_sys,
        topology=topology.to_openmm(),
        xyz=topology.topology_molecules[0].reference_molecule.conformers[0],
    )

    struct.save(prefix + ".gro")
    struct.save(prefix + ".top")


def openff_pmd_gmx(
    topology: Topology,
    forcefield: ForceField,
    prefix: str,
) -> None:
    off_sys = System.from_toolkit(topology=topology, forcefield=forcefield)

    struct = off_sys.to_parmed()

    struct.save(prefix + ".gro")
    struct.save(prefix + ".top")


def test_parmed_openmm():
    parsley = ForceField("openff_unconstrained-1.0.0.offxml")
    mol = Molecule.from_smiles("C")
    mol.generate_conformers(n_conformers=1)
    top = Topology.from_molecules(mol)
    top.box_vectors = 4 * np.eye(3) * unit.nanometer

    with tempfile.TemporaryDirectory():  # This probably doesn't work
        openff_openmm_pmd_gmx(
            topology=top,
            forcefield=parsley,
            prefix="methane1",
        )

        openff_pmd_gmx(
            topology=top,
            forcefield=parsley,
            prefix="methane2",
        )

        ener1, ener1_file = gmx_energy(
            top="methane1.top",
            gro="methane1.gro",
            mdp=resource_filename("intermol", "tests/gromacs/grompp_vacuum.mdp"),
        )

        ener2, ener2_file = gmx_energy(
            top="methane2.top",
            gro="methane2.gro",
            mdp=resource_filename("intermol", "tests/gromacs/grompp_vacuum.mdp"),
        )

        assert ener1 == ener2
