from setuptools import setup, Extension
from Cython.Build import cythonize
import os

extensions = [
    Extension("roy_on_ray.roybase", ["src/roy_on_ray/roybase.pyx"]),
    Extension("roy_on_ray.roylist", ["src/roy_on_ray/roylist.pyx"]),
    Extension("roy_on_ray.royset", ["src/roy_on_ray/royset.pyx"]),
    Extension("roy_on_ray.roydict", ["src/roy_on_ray/roydict.pyx"]),
]

setup(
    name='roy_on_ray',
    version='0.0.1b',
    ext_modules=cythonize(
        extensions,
        include_path=[os.path.join(os.getcwd(), 'src', 'roy_on_ray')]
    ),
    package_dir={'': 'src'},
    packages=['roy_on_ray'],
)