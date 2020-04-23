# -*- coding: utf-8 -*-

import pytest
from arom_uploader.skeleton import fib

__author__ = "hayjohnny2000"
__copyright__ = "hayjohnny2000"
__license__ = "mit"


def test_fib():
    assert fib(1) == 1
    assert fib(2) == 1
    assert fib(7) == 13
    with pytest.raises(AssertionError):
        fib(-10)
