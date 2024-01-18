from setuptools import setup

setup(
    name="cocotb-vivdo",
    packages=["cocotb_vivado", "cocotb_vivado.stub"],
    package_dir={"": "src"},
    author="Tomasz Hemperek",
    author_email="themperek@gmail.com",
    description="Limited cocotb/Python interface for Xilinx Vivado Simulator",
    long_description="""
    Enables running cocotb/Python unit tests with Xilinx Vivado simulator (xsim)
    """,
    license="Apache 2.0",
    keywords=["SystemVerilog", "Verilog", "RTL", "cocotb", "Python", "Vivado", "Xilinx", "xsim", "xsi"],
    url="https://github.com/themperek/cocotb-xsim",
    setup_requires=["setuptools_scm"],
    install_requires=["cocotb>=1.7,<=1.8"],
    version="0.0.1",
)
