import pytest
from openff.units import unit

from openff.interchange.drivers.report import EnergyReport
from openff.interchange.testing import _BaseTest

kj_mol = unit.kilojoule / unit.mole


class TestEnergyReport(_BaseTest):
    def test_getitem(self):
        report = EnergyReport(energies={"Bond": 10 * kj_mol})
        assert report["Bond"].units == kj_mol
        assert report["Angle"] is None
        assert "Bond" in str(report)

        with pytest.raises(LookupError, match="type <class 'int'>"):
            report[0]

    def test_sub(self):
        a = EnergyReport(energies={"y": 10 * kj_mol})
        b = EnergyReport(energies={"y": 15 * kj_mol})
        c = EnergyReport(energies={"y": 15 * kj_mol, "z": 10 * kj_mol})

        diff = b - a

        assert diff["y"] == 5 * unit.kilojoule / unit.mol

        with pytest.warns(UserWarning, match="Did not find key z"):
            c - b
