"""Domain-specific exceptions raised by the NetArchitect rule engines."""


class NetArchitectError(Exception):
    """Base class for all NetArchitect errors."""


class InvalidParameterError(NetArchitectError):
    """Raised when a preset or custom JSON parameter fails validation."""


class PhysicalDistanceViolationError(NetArchitectError):
    """Raised when a requested medium cannot physically span the requested run.

    Example: Cat6a copper requested for a 150 m run. IEEE 802.3an (10GBASE-T)
    limits a copper channel to 100 m; beyond that insertion loss, NEXT and
    alien crosstalk push the signal below the receiver's SNR floor.
    """


class OpticalBudgetError(NetArchitectError):
    """Raised when no transceiver class can close the optical power budget."""


class AddressSpaceExhaustedError(NetArchitectError):
    """Raised when the VLSM allocator cannot fit a request inside the root prefix."""


class AddressOverlapError(NetArchitectError):
    """Raised when two address blocks (e.g. campus root and cloud VPC) overlap."""
