import os
import pybind11
from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext

class BuildExt(build_ext):
    def build_extensions(self):
        compiler = self.compiler.compiler_type
        if compiler == 'msvc':
            for ext in self.extensions:
                ext.extra_compile_args = ['/std:c++17', '/O2']
        else:
            for ext in self.extensions:
                ext.extra_compile_args = ['-std=c++17', '-O2']
        build_ext.build_extensions(self)

ext_modules = [
    Extension(
        'roylist',
        ['roylist.cpp'],
        include_dirs=[
            pybind11.get_include(),
            pybind11.get_include(user=True),
            # Add Ray include directory if necessary
        ],
        # libraries=['ray'],  # Add Ray library if necessary
        language='c++'
    ),
]

setup(
    name='roylist',
    ext_modules=ext_modules,
    cmdclass={'build_ext': BuildExt},
    zip_safe=False,
)
