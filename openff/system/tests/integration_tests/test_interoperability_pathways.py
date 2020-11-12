import numpy as np
import parmed as pmd
from intermol.gromacs import energies as gmx_energy
from openforcefield.topology import Molecule, Topology
from pkg_resources import resource_filename
from simtk import unit as omm_unit

from openff.system.stubs import ForceField
from openff.system.utils import simtk_to_pint

from ..utils import compare_energies


def openff_openmm_pmd_gmx(
    topology: Topology,
    forcefield: ForceField,
    box: omm_unit.Quantity,
    prefix: str,
) -> None:
    """Pipeline to write GROMACS files from and OpenMM system through ParmEd"""
    topology.box_vectors = box
    omm_sys = forcefield.create_openmm_system(topology)

    struct = pmd.openmm.load_topology(
        system=omm_sys,
        topology=topology.to_openmm(),
        xyz=topology.topology_molecules[0].reference_molecule.conformers[0],
    )

    # Assign dummy residue names, GROMACS will not accept empty strings
    # TODO: Patch upstream?
    for res in struct.residues:
        res.name = "FOO"

    struct.save(prefix + ".gro")
    struct.save(prefix + ".top")


def openff_pmd_gmx(
    topology: Topology,
    forcefield: ForceField,
    box: omm_unit.Quantity,
    prefix: str,
) -> None:
    topology.box_vectors = box
    off_sys = forcefield.create_openff_system(topology=topology)

    off_top_positions = topology.topology_molecules[0].reference_molecule.conformers[0]
    # TODO: Update this when better processing of OFFTop positions is supported
    off_sys.positions = simtk_to_pint(off_top_positions)

    struct = off_sys.to_parmed()

    struct.save(prefix + ".gro")
    struct.save(prefix + ".top")


def test_parmed_openmm(tmpdir):
    tmpdir.chdir()

    parsley = ForceField("openff_unconstrained-1.0.0.offxml")
    mol = Molecule.from_smiles("C")
    mol.generate_conformers(n_conformers=1)
    top = Topology.from_molecules(mol)
    box = 4 * np.eye(3) * omm_unit.nanometer

    openff_openmm_pmd_gmx(
        topology=top,
        forcefield=parsley,
        box=box,
        prefix="methane1",
    )

    openff_pmd_gmx(
        topology=top,
        forcefield=parsley,
        box=box,
        prefix="methane2",
    )

    ener1, ener1_file = gmx_energy(
        top="methane1.top",
        gro="methane1.gro",
        mdp=resource_filename("intermol", "tests/gromacs/grompp.mdp"),
    )

    ener2, ener2_file = gmx_energy(
        top="methane2.top",
        gro="methane2.gro",
        mdp=resource_filename("intermol", "tests/gromacs/grompp.mdp"),
    )

    compare_energies(ener1, ener2)
