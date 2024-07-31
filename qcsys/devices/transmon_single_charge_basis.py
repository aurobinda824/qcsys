""" Transmon.

TODO: this needs to be updated to work with standard truncation scheme.

"""

from flax import struct
from jax import config
import jaxquantum as jqt
import jax.numpy as jnp
import jax.scipy as jsp

from qcsys.devices.base import Device

config.update("jax_enable_x64", True)


@struct.dataclass
class SingleChargeTransmon(Device):
    """
    Offset-Charge Sensitive Transmon Device, written in single-charge basis.

    Required params:
    - Ec: Charging Energy
    - Ej: Josephson Energy
    - ng: Gate offset charge
    - N_max_charge: Maximum number of charge levels to consider

    """

    N_max_charge: int = struct.field(pytree_node=False)

    @classmethod
    def create(cls, N, N_max_charge, params, label=0, use_linear=False):
        return cls(N, params, label, use_linear, N_max_charge)

    def common_ops(self):
        """
        Operators defined in the single charge basis.
        """
        ops = {}

        # Ensure truncation is valid
        assert self.N <= 2 * self.N_max_charge + 1

        ops["n"] = self.build_n_op()
        ops["cos(φ)"] = self.build_cos_phi_op()
        ops["cos(φ/2)"] = self.build_cos_phi_2_op()
        ops["sin(φ/2)"] = self.build_sin_phi_2_op()
        return ops

    def build_n_op(self):
        # We define n = ∑ₙ n|n⟩⟨n| in the single charge basis. Here n counts electrons, not Cooper pairs.
        return jnp.diag(jnp.arange(-self.N_max_charge, self.N_max_charge + 1))

    def build_cos_phi_op(self):
        # We define cos(φ) = 1/2 * ∑ₙ|n⟩⟨n+2| + h.c. in the single charge basis
        return 0.5 * (
            jnp.eye(2 * self.N_max_charge + 1, k=2)
            + jnp.eye(2 * self.N_max_charge + 1, k=-2)
        )

    def build_cos_phi_2_op(self):
        # We define cos(φ/2) = 1/2 * ∑ₙ|n⟩⟨n+1| + h.c. in the single charge basis
        return 0.5 * (
            jnp.eye(2 * self.N_max_charge + 1, k=1)
            + jnp.eye(2 * self.N_max_charge + 1, k=-1)
        )

    def build_sin_phi_2_op(self):
        # We define sin(φ/2) = i/2 * ∑ₙ|n⟩⟨n+1| + h.c. in the single charge basis
        return 0.5j * (
            jnp.eye(2 * self.N_max_charge + 1, k=1)
            - jnp.eye(2 * self.N_max_charge + 1, k=-1)
        )

    @property
    def phi_zpf(self):
        """Return Phase ZPF"""
        return (2 * self.params["Ec"] / self.params["Ej"]) ** (0.25)

    @property
    def n_zpf(self):
        """Return charge ZPF"""
        return (self.params["Ej"] / (32.0 * self.params["Ec"])) ** (0.25)

    def get_linear_ω(self):
        """Get frequency of linear terms"""
        return jnp.sqrt(8 * self.params["Ec"] * self.params["Ej"])

    def get_H_linear(self):
        raise NotImplemented(
            "No linear oscillator basis for single charge transmon. Set _use_linear = False."
        )

    def get_H_full(self):
        """
        Return full Hamiltonian H = Ec (n - 2ng)² - Ej cos(φ) in the single charge basis. Using Eq. (5.36)
        of Kyle Serniak's thesis, we have H = Ec ∑ₙ(n - 2*ng) |n⟩⟨n| - Ej/2 * ∑ₙ|n⟩⟨n+2| + h.c where now n
        counts the number of electrons, not Cooper pairs.
        """
        # (n - 2*ng)
        n_minus_ng_array = jnp.arange(
            -self.N_max_charge, self.N_max_charge + 1
        ) - 2 * self.params["ng"] * jnp.ones(2 * self.N_max_charge + 1)

        return (
            jnp.diag(self.params["Ec"] * n_minus_ng_array**2)
            - self.params["Ej"] * self.linear_ops["cos(φ)"]
        )

    def get_op_in_H_eigenbasis(self, op):
        """
        We overwrite this function to effectively truncate to the first N levels out of N_max_charge
        """
        evecs = self.eig_systems["vecs"][:, : self.N]
        op = jnp.dot(jnp.conjugate(evecs.transpose()), jnp.dot(op, evecs))
        return op
