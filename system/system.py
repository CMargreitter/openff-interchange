from typing import Dict, Union

from pydantic import validator, root_validator
import pint

from simtk.unit import Quantity as SimTKQuantity
from simtk.openmm.app import Topology as OpenMMTopology

from openforcefield.typing.engines.smirnoff import ForceField, ParameterHandler
from openforcefield.topology import Topology

from . import unit
from .typing.smirnoff import *
from .utils import simtk_to_pint
from .types import UnitArray


def potential_map_from_terms(collection):
    mapping = dict()

    for key, val in collection.terms.items():
        mapping[key] = val.smirks_map

    return mapping


class ProtoSystem(BaseModel):
    """A primitive object for other System objects to be built off of"""

    topology: Union[Topology, OpenMMTopology]
    positions: UnitArray
    box: UnitArray

    # TODO: I needed to set pre=True to get this to override the Array type. This is bad
    # and instead this attribute should be handled by a custom class that deals with
    # all of the complexity (NumPy/simtk.unit.Quantity/pint.Quantity) and spits out
    # a single thing that plays nicely with things
    @validator("positions", "box", pre=True)
    def validate_in_space(cls, val):
        if isinstance(val, SimTKQuantity):
            val = UnitArray(simtk_to_pint(val))
        if isinstance(val, (pint.Quantity, np.ndarray, UnitArray)):
            val = UnitArray(val)
            if val.dimensionless:
                val *= unit.nm
            if not val.is_compatible_with('nm'):
                raise TypeError  # Make this a custom exception?
            return val
        else:
            raise TypeError

    @validator("box")
    def validate_box(cls, val):
        if val.shape == (3, 3):
            return val
        elif val.shape == (3,):
            return val * np.eye(3)
        else:
            raise ValueError

    @validator("topology", pre=True)
    def validate_topology(cls, val):
        if isinstance(val, Topology):
            return val
        elif isinstance(val, OpenMMTopology):
            return Topology.from_openmm(val)
        else:
            raise TypeError

    class Config:
        arbitrary_types_allowed = True


class System(ProtoSystem):
    """The OpenFF System object."""

    forcefield: Union[ForceField, ParameterHandler] = None
    slot_smirks_map: Dict = dict()
    smirks_potential_map: Dict = dict()
    term_collection: SMIRNOFFTermCollection = None

    @classmethod
    def from_proto_system(cls, proto_system, forcefield=None, slot_smirks_map=dict(), smirks_potential_map=dict(), term_collection=SMIRNOFFTermCollection()):
        return cls(
            topology=proto_system.topology,
            positions=proto_system.positions,
            box=proto_system.box,
            forcefield=forcefield,
            slot_smirks_map=slot_smirks_map,
            smirks_potential_map=smirks_potential_map,
            term_collection=term_collection,
        )

    @root_validator
    def validate_forcefield_data(cls, values):
        # TODO: Replace this messy logic with something cleaner
        if not values['forcefield']:
            if not values['slot_smirks_map'] or not values['smirks_potential_map']:
                pass  # raise TypeError('not given an ff, need maps')
        if values['forcefield']:
            if values['smirks_potential_map'] and values['slot_smirks_map'] and values['term_collection']:
                raise TypeError('ff redundantly specified, will not be used')
            # TODO: Let other typing engines drop in here
            values['slot_smirks_map'] = build_slot_smirks_map(forcefield=values['forcefield'], topology=values['topology'])
            values['term_collection'] = SMIRNOFFTermCollection.from_toolkit_data(
                toolkit_forcefield=values['forcefield'],
                toolkit_topology=values['topology'],
            )
            values['smirks_potential_map'] = potential_map_from_terms(values['term_collection'])
        return values

    # TODO: These valiators pretty much don't do anything now
    @validator("forcefield")
    def validate_forcefield(cls, val):
        if not val:
            return val
        if isinstance(val, ForceField):
            return val
        else:
            raise TypeError

    class Config:
        arbitrary_types_allowed = True

    def apply_single_parameter_handler(self, parameter_handler):
        # TODO: Abstract this away to be SMIRNOFF-agnostic
        if parameter_handler._TAGNAME == 'Electrostatics':
            raise NotImplementedError()

        self.slot_smirks_map[parameter_handler._TAGNAME] = build_slot_smirks_map_term(
            handler=parameter_handler,
            topology=self.topology,
        )

        self.smirks_potential_map[parameter_handler._TAGNAME] = build_smirks_potential_map_term(
            handler=parameter_handler,
            topology=self.topology,
            forcefield=self.forcefield,
        )

        self.term_collection.add_parameter_handler(parameter_handler, topology=self.topology, forcefield=None)

    def to_file(self):
        raise NotImplementedError()

    def from_file(self):
        raise NotImplementedError()

    def to_parmed(self):
        raise NotImplementedError()

    def to_openmm(self):
        raise NotImplementedError()
