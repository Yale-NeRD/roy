from setuptools import setup
from Cython.Build import cythonize
import os

lib_name = 'roy_on_ray'
# Ensure the directory exists
os.makedirs(lib_name, exist_ok=True)

setup(
    name=lib_name,
    ext_modules = cythonize([
        "roybase.pyx",
        "roylist.pyx",
        "royset.pyx",
        "roydict.pyx",]),
)
