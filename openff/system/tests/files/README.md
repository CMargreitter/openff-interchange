Documenting how some of these files were generated


`10_ar.pdb`:
  - ```python3
    >>> import mbuild as mb
    >>> ar = mb.Compound(name='Ar')
    >>> mol = mb.fill_box(ar, 10, box=[2, 2, 2])
    >>> mol.to_parmed().save('10_ar.pdb')
    ```

`parsley.offxml`:
  - This file is a based on a copy of `openff_unconstrained-1.0.0.offxml` (1/4/21)
  - The 1-4 scaling term in the Electrostatics handler is hard-coded to 0.83333 to replicate a bug in the OpenFF Toolkit
    - See https://github.com/openforcefield/opennff-toolkit/issues/408
    - Once this bug is fixed, a mainline force field loaded from the entry point should be used

`water-dimer.pdb`:
  - Taken from the `openmm-tests` repo: https://github.com/choderalab/openmm-tests/blob/5a7d3b7bee753a384c98f4b6f8bb1460c371935c/energy-continuity/water-dimer.pdb

`tip3p.offxml`:
  - Taken from the toolkit, but with a default-looking `<Electrostatics>` tag added.
    - https://github.com/openforcefield/openff-toolkit/blob/d0b768a6d2cd0297b34aab3618197604b81d6e03/openff/toolkit/data/test_forcefields/tip3p.offxml
    - See https://github.com/openforcefield/openff-toolkit/issues/716

`ALA_GLY/ALA_GLY.*`
  - The SDF and PDB files files were prepared by Jeff Wagner
  - The .gro and .top files were prepared by internal exporters 3/26/21

`packed-argon.pdb`
  - Generated via mBuild and ParmEd
  - ```
    import mbuild as mb
    argon = mb.Compound(name='Ar')
    packed_box = mb.fill_box(
        compound=[argon],
        box=mb.Box(lengths=[3, 3, 3]),  # nm
        density=1417,  # kg/m3
    )
    struct = packed_box.to_parmed(residues=['Ar'])
    struct.save('packed-argon.pdb')
    ```

`benzene.sdf`
