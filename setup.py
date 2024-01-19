from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="cocotb-vivado",
    version="0.0.2",
    install_requires=["cocotb>=1.7,<=1.8"],
    packages=find_packages(where="./src"),
    package_dir={"": "src"},
    author="Tomasz Hemperek",
    author_email="themperek@gmail.com",
    description="Limited cocotb/Python interface for Xilinx Vivado Simulator",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="Apache 2.0",
    keywords=["SystemVerilog", "Verilog", "RTL", "cocotb", "Python", "Vivado", "Xilinx", "xsim", "xsi"],
    url="https://github.com/themperek/cocotb-vivado",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
        "Framework :: cocotb",
    ],
    platforms="any",
)
