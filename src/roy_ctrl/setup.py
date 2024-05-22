# setup.py
from setuptools import setup, find_packages

setup(
    name="roy_ctrl",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click",
    ],
    entry_points={
        'console_scripts': [
            'roy=cli:cli',
        ],
    },
)
