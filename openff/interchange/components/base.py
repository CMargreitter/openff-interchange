"""
Base models for engine- and force field-agnostic components.
"""
from openff.units import unit
from pydantic import Field
from typing_extensions import Literal

from openff.interchange.components.potentials import PotentialHandler
from openff.interchange.types import FloatQuantity


class BaseBondHandler(PotentialHandler):
    """Base handler for storing generic bond interactions."""

    type: str = "Bonds"
    expression: str = "k/2*(r-length)**2"


class BaseAngleHandler(PotentialHandler):
    """Base handler for storing generic angle interactions."""

    type: str = "Angle"
    expression: str = "k/2*(theta-angle)**2"


class BaseProperTorsionHandler(PotentialHandler):
    """Base handler for storing generic proper torsion interactions."""

    type: str = "ProperTorsions"
    expression: str = "k*(1+cos(periodicity*theta-phase))"


class BaseImproperTorsionHandler(PotentialHandler):
    """Base handler for storing generic improper torsion interactions."""

    type: str = "ImproperTorsions"
    expression: str = "k*(1+cos(periodicity*theta-phase))"


class _BaseNonbondedHandler(PotentialHandler):
    """Base handler for storing generic nonbonded interactions."""

    type: str = "Nonbonded"

    scale_13: float = Field(
        0.0, description="The scaling factor applied to 1-3 interactions"
    )
    scale_14: float = Field(
        0.5, description="The scaling factor applied to 1-4 interactions"
    )
    scale_15: float = Field(
        1.0, description="The scaling factor applied to 1-5 interactions"
    )

    cutoff: FloatQuantity["angstrom"] = Field(  # type: ignore
        10.0 * unit.angstrom,
        description="The distance at which pairwise interactions are truncated",
    )


class BasevdWHandler(_BaseNonbondedHandler):
    """Base handler for storing vdW interactions."""

    type: str = "vdW"

    expression: str = "4*epsilon*((sigma/r)**12-(sigma/r)**6)"

    method: Literal["cutoff", "pme", "no-cutoff"] = Field("cutoff")

    mixing_rule: str = Field(
        "lorentz-berthelot",
        description="The mixing rule (combination rule) used in computing pairwise vdW interactions",
    )


class BaseElectrostaticsHandler(_BaseNonbondedHandler):
    """Base handler for storing vdW interactions."""

    type: str = "Electrostatics"

    expression: str = "coul"

    method: Literal["pme", "cutoff", "reaction-field", "no-cutoff"] = Field("pme")

    @property
    def charges(self):
        """Get the total partial charge on each atom, excluding virtual sites."""
        return {
            topology_key: self.potentials[potential_key].parameters["charge"]
            for topology_key, potential_key in self.slot_map.items()
        }