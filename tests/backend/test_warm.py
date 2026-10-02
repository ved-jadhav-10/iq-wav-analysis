import numpy as np

from backend import warm
from dsp.gf2 import matrix


def test_warm_runs_every_kernel_and_is_cheap_the_second_time() -> None:
    first = warm.warm()
    second = warm.warm()
    # Compiled (or cache-loaded) once, then just run; relative, so load can't flake it.
    assert first > 0 and second < max(3.0, first / 3)
    # The kernels still compute: the weights of a known matrix.
    rows = matrix.pack(np.array([[1, 1, 0, 1], [0, 0, 0, 0]], np.uint8))
    assert matrix.row_weights(rows).tolist() == [3, 0]
